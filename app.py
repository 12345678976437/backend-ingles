import json
import os
import random
import re
import tempfile
import threading
import time
import hashlib
import math
import platform
import requests
from collections import defaultdict, deque, OrderedDict
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from openai import OpenAI
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from supabase import Client, create_client

load_dotenv()

app = Flask(__name__)
CORS(app)
# Límite de tamaño de subida (audios): evita que un archivo enorme te cueste procesamiento.
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024


@app.errorhandler(413)
def too_large(_exc):
    return jsonify({"ok": False, "error": "El archivo es demasiado grande."}), 413

def env(name, default=""):
    return (os.getenv(name) or default).strip()

AZURE_SPEECH_KEY = env("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = env("AZURE_SPEECH_REGION", "westus3")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", "")
# Cuentas con acceso al panel de administración (separa varias con comas en ADMIN_EMAIL).
ADMIN_EMAILS = {e.strip().lower() for e in env("ADMIN_EMAIL", "a07077189@tec.mx").split(",") if e.strip()}


def is_admin_user(user):
    return (getattr(user, "email", "") or "").lower() in ADMIN_EMAILS
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = env("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = env("SUPABASE_KEY")
# Service role key: SOLO se usa en el servidor, nunca se envía al frontend.
# Se consigue en Supabase > Project Settings > API > service_role secret.
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase conectado.")
    except Exception as exc:
        print(f"[WARN] Supabase no pudo conectarse: {exc}")

# Cliente "admin": usa la service_role key, que ignora RLS.
# Lo usamos SOLO después de haber verificado la identidad del usuario
# con supabase.auth.get_user(token), así que es seguro consultar por user.id.
supabase_admin: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("[OK] Supabase (admin/service_role) conectado.")
    except Exception as exc:
        print(f"[WARN] Supabase admin no pudo conectarse: {exc}")

ai_client: OpenAI | None = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    try:
        ai_client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/",
        )
        print("[OK] Azure OpenAI configurado.")
    except Exception as exc:
        print(f"[WARN] Azure OpenAI no pudo inicializarse: {exc}")


def json_error(message, status=400, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


def has_active_access(profile_data):
    """True si el usuario pagó, o si sigue dentro de su periodo de prueba de 7 días."""
    if profile_data.get("is_subscribed"):
        return True
    trial_ends_at = profile_data.get("trial_ends_at")
    if not trial_ends_at:
        return False
    try:
        deadline = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) < deadline


# ---------------------------------------------------------------------------
# Límites de uso por usuario (protegen tu crédito de Azure sin costo extra).
# Se guardan en memoria del servidor: gratis y suficientes para un solo servidor.
# Ajusta los números aquí si algún límite se queda corto para tus alumnos.
# ---------------------------------------------------------------------------
RATE_RULES = {
    "/api/tutor": (60, 3600),
    "/api/sintetizar-audio": (120, 3600),
    "/api/transcribir-audio": (60, 3600),
    "/api/resumen-llamada": (10, 3600),
    "/analizar-escritura": (20, 3600),
    "/evaluar-lectura": (30, 3600),
    "/evaluar-dictado": (40, 3600),
    "/analizar-audio-real": (150, 3600),
    "/api/assess-reading": (40, 3600),
    "/api/assess-unscripted": (40, 3600),
    "/nueva-frase": (60, 3600),
    "/nuevo-tema-libre": (60, 3600),
    "/nuevo-trabalenguas": (60, 3600),
    "/nuevo-texto-lectura": (30, 3600),
    "/nuevo-dictado": (30, 3600),
    "/api/writing/challenge": (30, 3600),
    "/api/vocabulario/diario": (20, 3600),
}
DAILY_AI_LIMIT = int(env("DAILY_AI_LIMIT", "400") or 400)   # llamadas de IA por usuario al día
GENERAL_PER_MINUTE = 120                                      # cualquier endpoint, por usuario
_rate_lock = threading.Lock()
_rate_hits = {}
_rate_calls = 0


def _rate_hit(key, limit, window):
    """Registra una llamada. Devuelve (permitida, segundos_para_reintentar)."""
    global _rate_calls
    now = time.time()
    with _rate_lock:
        _rate_calls += 1
        if _rate_calls % 2000 == 0:  # limpieza ocasional para no acumular memoria
            for k in [k for k, q in _rate_hits.items() if not q or now - q[-1] > 86400]:
                _rate_hits.pop(k, None)
        q = _rate_hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False, int(window - (now - q[0])) + 1
        q.append(now)
        return True, 0


def check_rate_limit(user):
    """Devuelve None si todo bien, o un mensaje de error (429)."""
    if is_admin_user(user):
        return None
    uid = getattr(user, "id", "anon")
    ok, wait = _rate_hit((uid, "minuto"), GENERAL_PER_MINUTE, 60)
    if not ok:
        return f"Vas muy rápido. Espera {wait} segundos e inténtalo de nuevo."
    rule = RATE_RULES.get(request.path)
    if rule:
        ok, wait = _rate_hit((uid, request.path), rule[0], rule[1])
        if not ok:
            return f"Alcanzaste el límite de esta actividad por ahora. Vuelve a intentarlo en {max(1, wait // 60)} min."
        try:
            fast_clip = request.path == "/analizar-audio-real" and request.form.get("fast") in ("1", "true")
        except Exception:
            fast_clip = False
        if fast_clip:
            return None  # los audios rápidos de las lecciones no usan IA, así que no cuentan para el límite diario
        ok, wait = _rate_hit((uid, "dia-ia"), DAILY_AI_LIMIT, 86400)
        if not ok:
            return "Alcanzaste el límite diario de práctica con IA. Vuelve mañana."
    return None


def authenticated_user(require_subscription=True):
    if not supabase:
        return None, ("Supabase no está configurado.", 500)

    token = get_bearer_token()
    if not token:
        return None, ("Sesión requerida.", 401)

    try:
        result = supabase.auth.get_user(token)
        user = result.user
    except Exception as exc:
        print(f"[AUTH] {exc}")
        return None, ("Sesión inválida o expirada.", 401)

    if not user:
        return None, ("Sesión inválida.", 401)

    if require_subscription and not is_admin_user(user):
        try:
            client = supabase_admin or supabase
            profile = (
                client.table("profiles")
                .select("is_subscribed,trial_ends_at")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            data = profile.data or {}
            if not has_active_access(data):
                return None, ("Tu acceso todavía no está activo.", 403)
        except Exception as exc:
            print(f"[PROFILE] {exc}")
            return None, ("No se pudo comprobar tu acceso.", 500)

    limited = check_rate_limit(user)
    if limited:
        return None, (limited, 429)

    return user, None


def ai_json(system_prompt, user_prompt, temperature=0.7):
    if not ai_client:
        raise RuntimeError("Azure OpenAI no está configurado en el servidor.")

    response = ai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def save_history(table, user_id, payload):
    client = supabase_admin or supabase
    if not client:
        return
    try:
        client.table(table).insert({"user_id": user_id, **payload}).execute()
    except Exception as exc:
        print(f"[HISTORY:{table}] {exc}")


def award_xp(user_id, amount):
    """Suma XP y gemas, y actualiza la racha de días consecutivos practicando."""
    client = supabase_admin or supabase
    if not client:
        return
    try:
        profile = (
            client.table("profiles")
            .select("xp,streak_days,last_activity_date,gems,streak_freezes")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        data = profile.data or {}
        today = datetime.now(timezone.utc).date()
        last = data.get("last_activity_date")
        streak = data.get("streak_days") or 0
        freezes = data.get("streak_freezes") or 0
        if last:
            last_date = datetime.fromisoformat(last).date()
            if last_date == today:
                pass  # ya contó hoy
            elif last_date == today - timedelta(days=1):
                streak += 1
            elif last_date == today - timedelta(days=2) and freezes > 0:
                # Se saltó exactamente un día, pero tiene una racha congelada guardada.
                freezes -= 1
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        new_xp = (data.get("xp") or 0) + amount
        new_gems = (data.get("gems") or 0) + max(1, amount // 10)
        client.table("profiles").update({
            "xp": new_xp,
            "gems": new_gems,
            "streak_days": streak,
            "streak_freezes": freezes,
            "last_activity_date": today.isoformat(),
        }).eq("id", user_id).execute()
    except Exception as exc:
        print(f"[XP] {exc}")


def speech_config():
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("Azure Speech no está configurado.")
    config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    config.speech_recognition_language = "en-US"
    return config


def convert_audio_to_wav(upload):
    suffix = os.path.splitext(upload.filename or "audio.webm")[1] or ".webm"
    source_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as source:
            upload.save(source.name)
            source_path = source.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav:
            wav_path = wav.name

        audio = AudioSegment.from_file(source_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception:
        if source_path and os.path.exists(source_path):
            os.remove(source_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        raise


def assess_pronunciation(wav_path, reference_text=None):
    config = speech_config()
    if reference_text:
        pronunciation = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation.enable_prosody_assessment()
    else:
        pronunciation = speechsdk.PronunciationAssessmentConfig(
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )

    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
    pronunciation.apply_to(recognizer)
    result = recognizer.recognize_once()

    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        detail = getattr(result, "cancellation_details", None)
        reason = getattr(detail, "reason", "No se reconoció el audio.") if detail else "No se reconoció el audio."
        raise RuntimeError(str(reason))

    raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult, "{}")
    raw = json.loads(raw_json)
    nbest = (raw.get("NBest") or [{}])[0]
    assessment_raw = nbest.get("PronunciationAssessment") or {}

    words = []
    for word in nbest.get("Words") or []:
        wa = word.get("PronunciationAssessment") or {}
        phonemes = []
        for phoneme in word.get("Phonemes") or []:
            pa = phoneme.get("PronunciationAssessment") or {}
            phonemes.append({
                "phoneme": phoneme.get("Phoneme", ""),
                "accuracy": round(float(pa.get("AccuracyScore", 0) or 0), 1),
            })
        words.append({
            "word": word.get("Word", ""),
            "accuracy": round(float(wa.get("AccuracyScore", 0) or 0), 1),
            "error_type": wa.get("ErrorType", "None"),
            "offset": word.get("Offset", 0),
            "duration": word.get("Duration", 0),
            "phonemes": phonemes,
        })

    speaking_rate_wpm = 0
    if words:
        first_offset = words[0].get("offset", 0) or 0
        last_word = words[-1]
        last_end = (last_word.get("offset", 0) or 0) + (last_word.get("duration", 0) or 0)
        speaking_seconds = max(0.1, (last_end - first_offset) / 10_000_000)
        speaking_rate_wpm = round(len(words) / speaking_seconds * 60)

    return {
        "transcript": nbest.get("Display", ""),
        "pronunciation_score": round(float(assessment_raw.get("PronScore", 0) or 0), 1),
        "accuracy_score": round(float(assessment_raw.get("AccuracyScore", 0) or 0), 1),
        "fluency_score": round(float(assessment_raw.get("FluencyScore", 0) or 0), 1),
        "completeness_score": round(float(assessment_raw.get("CompletenessScore", 0) or 0), 1),
        "prosody_score": round(float(assessment_raw.get("ProsodyScore", 0) or 0), 1),
        "speaking_rate_wpm": speaking_rate_wpm,
        "words": words,
    }


ERROR_TYPE_TO_KEY = {
    "Omission": "omisiones",
    "Insertion": "inserciones",
    "Mispronunciation": "pronunciaciones_incoherentes",
    "UnexpectedBreak": "interrupcion_inesperada",
    "MissingBreak": "falta_un_descanso",
    "Monotone": "monotona",
}


def build_pron_payload(result):
    """Convierte el resultado (claves en inglés) al formato en español que usa el frontend."""
    inspeccion = {key: 0 for key in ERROR_TYPE_TO_KEY.values()}
    palabras = []
    for word in result["words"]:
        error_key = ERROR_TYPE_TO_KEY.get(word.get("error_type"))
        if error_key:
            inspeccion[error_key] += 1
        palabras.append({
            "palabra": word.get("word", ""),
            "precision": word.get("accuracy", 0),
            "fonemas": [
                {"fonema": p.get("phoneme", ""), "precision": p.get("accuracy", 0)}
                for p in word.get("phonemes", [])
            ],
        })

    return {
        "transcript": result.get("transcript", ""),
        "puntuacion_global": result.get("pronunciation_score", 0),
        "precision": result.get("accuracy_score", 0),
        "fluidez": result.get("fluency_score", 0),
        "completitud": result.get("completeness_score", 0),
        "prosodia": result.get("prosody_score", 0),
        "velocidad_wpm": result.get("speaking_rate_wpm", 0),
        "palabras": palabras,
        "inspeccion": inspeccion,
    }


PASS_THRESHOLD = 60  # puntuación mínima para aprobar una lección

# ---------------------------------------------------------------------------
#  RUTA DE APRENDIZAJE v2 — currículo fijo (sin costo de IA) + lecciones de varios pasos
# ---------------------------------------------------------------------------
CURRICULUM_TEXT = r'''@unit first_steps|1|A1|🚀|First Steps|Your first words and phrases to survive any introduction.|general
# hello_bye|Hello & goodbye
n Usa "Hi" con amigos y "Hello" en situaciones más formales.
w hello|hola|👋
w goodbye|adiós|👋
w good morning|buenos días|🌅
w good night|buenas noches|🌙
w see you later|hasta luego|🙂
w friend|amigo|🧑‍🤝‍🧑
p Hello, nice to meet you.|Hola, mucho gusto.
p Good morning, how are you?|Buenos días, ¿cómo estás?
p See you tomorrow.|Nos vemos mañana.
d Good morning!|Good morning! How are you?|Goodbye, my friend.|It is blue.
# i_am|I am… / You are…
n En inglés el sujeto es obligatorio: "I am", no solo "am".
w I am|yo soy / estoy
w you are|tú eres / estás
w he is|él es / está
w she is|ella es / está
w we are|nosotros somos
w they are|ellos son
p I am from Mexico.|Soy de México.
p She is my sister.|Ella es mi hermana.
p We are students.|Somos estudiantes.
d Where are you from?|I am from Spain.|She is my sister.|We are tired.
# please_thanks|Please & thank you
n "Excuse me" para llamar la atención; "Sorry" para disculparte.
w please|por favor
w thank you|gracias
w you are welcome|de nada
w sorry|perdón
w excuse me|disculpe
w help|ayuda|🆘
p Thank you very much.|Muchas gracias.
p Excuse me, can you help me?|Disculpe, ¿me puede ayudar?
p I am sorry, I do not understand.|Lo siento, no entiendo.
d Thank you very much!|You are welcome.|Good night.|I am a student.
# yes_no|Yes, no, and questions
w yes|sí
w no|no
w maybe|quizás
w what|qué
w where|dónde
w how much|cuánto
p Do you speak English?|¿Hablas inglés?
p What is your name?|¿Cómo te llamas?
p Can you repeat that, please?|¿Puedes repetirlo, por favor?
d Do you speak English?|A little, but I am learning.|Yes, it is red.|My name is on the table.
# spell_it|Spell your name
n Practica decir tu nombre letra por letra: es lo que te piden en hoteles y bancos.
w name|nombre
w last name|apellido
w letter|letra
w spell|deletrear
w phone number|número de teléfono|📱
w email|correo electrónico|📧
p How do you spell your name?|¿Cómo se deletrea tu nombre?
p My name is Ana Lopez.|Me llamo Ana López.
p Could you spell that, please?|¿Podría deletrearlo, por favor?
d How do you spell your last name?|L-O-P-E-Z.|It is Monday.|I am fine.
@unit everyday_english|2|A1|🏠|Everyday English|Greetings, routines, and small talk.|general
# greetings|Greetings & introductions
n "How are you?" es un saludo; la respuesta corta es "Fine, thanks. And you?".
w nice to meet you|mucho gusto
w how are you|cómo estás
w I am fine|estoy bien
w my name is|me llamo
w where are you from|de dónde eres
w I live in|vivo en
p Hi, my name is Carlos. Nice to meet you.|Hola, me llamo Carlos. Mucho gusto.
p I am fine, thanks. And you?|Estoy bien, gracias. ¿Y tú?
p I live in Monterrey.|Vivo en Monterrey.
d How are you today?|I am fine, thanks. And you?|I live in a house.|My name is Tuesday.
# routines|Daily routines
n La rutina usa presente simple: "I wake up", "she works". Con he/she/it se añade -s.
w wake up|despertarse|⏰
w take a shower|bañarse|🚿
w have breakfast|desayunar|🥣
w go to work|ir al trabajo|🏢
w come home|llegar a casa|🏡
w go to bed|irse a dormir|🛏️
p I wake up at seven every day.|Me despierto a las siete todos los días.
p She goes to work by bus.|Ella va al trabajo en autobús.
p We have dinner at eight.|Cenamos a las ocho.
d What time do you wake up?|I wake up at six.|I am from Chile.|She is my friend.
# family|Family & friends
w mother|madre|👩
w father|padre|👨
w brother|hermano
w sister|hermana
w grandmother|abuela|👵
w cousin|primo / prima
p I have two brothers and one sister.|Tengo dos hermanos y una hermana.
p My grandmother lives with us.|Mi abuela vive con nosotros.
p He is my best friend.|Él es mi mejor amigo.
d Do you have brothers or sisters?|Yes, I have one sister.|I live in a big house.|It is nine o'clock.
# smalltalk|Small talk
n "How is it going?" y "What's up?" son saludos muy comunes y informales.
w weather|clima|⛅
w weekend|fin de semana
w busy|ocupado
w tired|cansado|😴
w by the way|por cierto
w really|de verdad
p How was your weekend?|¿Cómo estuvo tu fin de semana?
p It is a beautiful day, isn't it?|Es un día hermoso, ¿no?
p I am a little tired today.|Estoy un poco cansado hoy.
d How was your weekend?|It was great, thanks for asking.|My name is Peter.|I have a red car.
# numbers_time|Numbers & time
n Para la hora: "It is half past three" = 3:30.
w twenty|veinte
w fifty|cincuenta
w one hundred|cien
w o'clock|en punto
w half past|y media
w quarter to|menos cuarto
p What time is it?|¿Qué hora es?
p It is half past three.|Son las tres y media.
p The meeting is at ten o'clock.|La reunión es a las diez en punto.
d What time is it?|It is a quarter to six.|It is my sister.|I am from Peru.
@unit home_and_city|3|A1|🏙️|Home & City|Talk about your home, your neighborhood, and getting around.|general
# rooms_home|Rooms & furniture
w kitchen|cocina|🍳
w bedroom|recámara|🛏️
w bathroom|baño|🚽
w living room|sala|🛋️
w window|ventana|🪟
w door|puerta|🚪
p My bedroom is upstairs.|Mi recámara está arriba.
p There is a table in the kitchen.|Hay una mesa en la cocina.
p The bathroom is on the left.|El baño está a la izquierda.
d Where is the bathroom?|It is on the left.|I wake up at six.|He is my uncle.
# things_around|Things around you
n "There is" para uno, "there are" para varios.
w table|mesa
w chair|silla|🪑
w phone|teléfono|📱
w key|llave|🔑
w bag|bolsa|👜
w book|libro|📕
p There are three chairs in the room.|Hay tres sillas en el cuarto.
p Where are my keys?|¿Dónde están mis llaves?
p My phone is in my bag.|Mi teléfono está en mi bolsa.
d Where are my keys?|They are on the table.|I am very tired.|It is half past two.
# places_city|Places in the city
w bank|banco|🏦
w supermarket|supermercado|🛒
w park|parque|🌳
w hospital|hospital|🏥
w pharmacy|farmacia|💊
w school|escuela|🏫
p The bank is next to the supermarket.|El banco está junto al supermercado.
p Is there a pharmacy near here?|¿Hay una farmacia cerca de aquí?
p I go to the park on Sundays.|Voy al parque los domingos.
d Is there a pharmacy near here?|Yes, it is on the corner.|I like pizza.|She is a doctor.
# transport|Getting around
w bus|autobús|🚌
w train|tren|🚆
w taxi|taxi|🚕
w subway|metro|🚇
w ticket|boleto|🎫
w stop|parada
p How do I get to the train station?|¿Cómo llego a la estación de tren?
p The bus stops here every ten minutes.|El autobús para aquí cada diez minutos.
p One ticket, please.|Un boleto, por favor.
d How much is a ticket?|It is two dollars.|It is sunny today.|My name is Luis.
# weather|Weather & seasons
n "It is hot" (hace calor): en inglés se usa el verbo "to be", no "to do".
w sunny|soleado|☀️
w rainy|lluvioso|🌧️
w cold|frío|🥶
w hot|caliente / calor|🥵
w windy|con viento|💨
w umbrella|paraguas|☂️
p It is going to rain tomorrow.|Va a llover mañana.
p It is very hot in summer.|Hace mucho calor en verano.
p Take an umbrella, just in case.|Lleva un paraguas, por si acaso.
d What is the weather like today?|It is cold and windy.|I live near the park.|He is my friend.
@unit at_the_restaurant|4|A2|🍽️|At the Restaurant|Order food, talk about flavors, and handle the bill.|travel
# ordering|Ordering food
n "I'd like…" es más cortés que "I want…".
w menu|menú|📋
w waiter|mesero|🧑‍🍳
w appetizer|entrada
w main course|plato fuerte
w dessert|postre|🍰
w drink|bebida|🥤
p I would like the chicken, please.|Quisiera el pollo, por favor.
p Can I see the menu?|¿Puedo ver el menú?
p Could we have some water?|¿Nos podría traer agua?
d Are you ready to order?|Yes, I would like the chicken.|It is on the left.|I live near here.
# menu|Understanding a menu
w grilled|a la parrilla
w fried|frito
w spicy|picante|🌶️
w vegetarian|vegetariano|🥗
w sauce|salsa
w side dish|guarnición
p Does this dish have nuts?|¿Este platillo lleva nueces?
p I am allergic to shellfish.|Soy alérgico a los mariscos.
p What do you recommend?|¿Qué me recomienda?
d What do you recommend?|The grilled fish is excellent.|I am from Peru.|It is five o'clock.
# preferences|Likes & dislikes
n "I'd rather…" = prefiero. "I can't stand…" = no soporto.
w I like|me gusta
w I love|me encanta
w I don't like|no me gusta
w I prefer|prefiero
w delicious|delicioso
w too salty|demasiado salado
p I love Italian food.|Me encanta la comida italiana.
p I do not like spicy food.|No me gusta la comida picante.
p I prefer tea to coffee.|Prefiero el té al café.
d Do you like spicy food?|Not really, I prefer mild food.|Yes, it is on the table.|He is my brother.
# complaints|Complaints & requests
w cold (food)|frío|🥶
w overcooked|pasado de cocción
w mistake|error
w manager|gerente
w refund|reembolso
w replace|reemplazar
p Excuse me, this is not what I ordered.|Disculpe, esto no es lo que pedí.
p The soup is cold. Could you heat it up?|La sopa está fría. ¿Podría calentarla?
p Could I speak to the manager?|¿Podría hablar con el gerente?
d Is everything okay with your meal?|Actually, my soup is cold.|I wake up at seven.|It is windy today.
# paying|Paying the bill
n En Estados Unidos la propina (tip) suele ser del 15 al 20 por ciento.
w bill|cuenta|🧾
w tip|propina
w cash|efectivo|💵
w credit card|tarjeta de crédito|💳
w change|cambio
w receipt|recibo
p Can we have the bill, please?|¿Nos trae la cuenta, por favor?
p Can I pay by card?|¿Puedo pagar con tarjeta?
p Keep the change.|Quédese con el cambio.
d How would you like to pay?|By card, please.|I like pizza.|It is on the left.
@unit shopping_and_money|5|A2|🛍️|Shopping & Money|Buy clothes, ask for prices, and handle returns.|general
# clothes|Clothes
w shirt|camisa|👕
w pants|pantalones|👖
w dress|vestido|👗
w shoes|zapatos|👟
w jacket|chamarra|🧥
w socks|calcetines|🧦
p I am looking for a black jacket.|Busco una chamarra negra.
p Do you have this shirt in blue?|¿Tiene esta camisa en azul?
p These shoes are very comfortable.|Estos zapatos son muy cómodos.
d Can I help you?|Yes, I am looking for a jacket.|I am at home.|She is my cousin.
# sizes_try|Sizes & fitting
w size|talla
w small|chico
w large|grande
w fitting room|probador
w too tight|muy apretado
w too big|muy grande
p Can I try this on?|¿Me lo puedo probar?
p Do you have a larger size?|¿Tiene una talla más grande?
p It fits me perfectly.|Me queda perfecto.
d How does it fit?|It is a little tight. Do you have a larger size?|It is half past six.|My name is Eva.
# prices_pay|Prices & discounts
n "How much is it?" para un precio; "How much are they?" para varios.
w price|precio
w cheap|barato
w expensive|caro
w discount|descuento
w on sale|en oferta
w total|total
p How much is this?|¿Cuánto cuesta esto?
p It is too expensive for me.|Es demasiado caro para mí.
p Is there a discount?|¿Hay algún descuento?
d How much is this bag?|It is forty dollars.|It is very sunny.|I am from Chile.
# returns_refunds|Returns & refunds
w return|devolver
w exchange|cambiar
w receipt|ticket de compra
w broken|roto
w warranty|garantía
w store credit|saldo a favor
p I would like to return this item.|Quisiera devolver este artículo.
p It does not work. Can I exchange it?|No funciona. ¿Puedo cambiarlo?
p Do you have the receipt?|¿Tiene el ticket de compra?
d What seems to be the problem?|It is broken. I would like a refund.|I live in Madrid.|It is a quarter to five.
# online_shop|Shopping online
w cart|carrito|🛒
w order|pedido|📦
w shipping|envío
w delivery|entrega
w track|rastrear
w out of stock|agotado
p When will my order arrive?|¿Cuándo llegará mi pedido?
p This item is out of stock.|Este artículo está agotado.
p Is shipping free?|¿El envío es gratis?
d When will my order arrive?|It should arrive in three days.|I am a student.|It is my sister.
@unit travel_and_tourism|6|A2|✈️|Travel & Tourism|Airports, hotels, directions, and sightseeing.|travel
# airport|At the airport
n "Boarding pass" = pase de abordar; "gate" = puerta de embarque.
w passport|pasaporte|🛂
w boarding pass|pase de abordar
w gate|puerta de embarque
w luggage|equipaje|🧳
w flight|vuelo|✈️
w delayed|retrasado
p Where is the check-in counter?|¿Dónde está el mostrador de registro?
p My flight is delayed.|Mi vuelo está retrasado.
p Do you have anything to declare?|¿Tiene algo que declarar?
d What is the purpose of your visit?|I am here on vacation.|I like tea.|It is cold today.
# hotel|Checking into a hotel
w reservation|reservación
w check in|registrarse
w check out|salir del hotel
w single room|habitación sencilla
w key card|tarjeta llave
w breakfast included|desayuno incluido
p I have a reservation under Lopez.|Tengo una reservación a nombre de López.
p What time is check-out?|¿A qué hora es la salida?
p Is breakfast included?|¿Incluye desayuno?
d Good evening. Do you have a reservation?|Yes, under the name Lopez.|I am a doctor.|It is on the table.
# directions|Asking for directions
n "Go straight" = sigue derecho. "Turn left/right" = da vuelta a la izquierda/derecha.
w turn left|gira a la izquierda|⬅️
w turn right|gira a la derecha|➡️
w go straight|sigue derecho|⬆️
w corner|esquina
w block|cuadra
w far|lejos
p Excuse me, how do I get to the museum?|Disculpe, ¿cómo llego al museo?
p Go straight and turn left at the corner.|Siga derecho y gire a la izquierda en la esquina.
p Is it far from here?|¿Está lejos de aquí?
d How do I get to the museum?|Go straight, then turn left.|I have two brothers.|It costs ten dollars.
# sightseeing|Sightseeing
w museum|museo|🏛️
w tour|recorrido
w guide|guía
w souvenir|recuerdo
w view|vista|🏞️
w entrance fee|costo de entrada
p What time does the tour start?|¿A qué hora empieza el recorrido?
p Can you take a photo of us?|¿Nos puede tomar una foto?
p The view from here is amazing.|La vista desde aquí es increíble.
d Can you take a photo of us?|Sure, smile!|I am from Cuba.|It is a red car.
# emergencies|Travel emergencies
n En Estados Unidos y México el número de emergencias es 911.
w emergency|emergencia|🚨
w police|policía|👮
w lost|perdido
w stolen|robado
w ambulance|ambulancia|🚑
w embassy|embajada
p Help! I lost my passport.|¡Ayuda! Perdí mi pasaporte.
p My wallet was stolen.|Me robaron la cartera.
p Please call an ambulance.|Por favor llame a una ambulancia.
d What happened?|I lost my wallet on the bus.|I like soup.|It is half past nine.
@unit health_and_body|7|A2|🩺|Health & Body|Describe symptoms, visit the doctor, and stay healthy.|personal
# body_parts|Body parts
w head|cabeza
w stomach|estómago
w throat|garganta
w back|espalda
w arm|brazo
w knee|rodilla
p My head hurts.|Me duele la cabeza.
p I have a pain in my back.|Tengo dolor de espalda.
p She hurt her knee.|Ella se lastimó la rodilla.
d What is wrong?|My stomach hurts.|I am from Texas.|It is sunny.
# symptoms|Symptoms
n "I have a headache" (no "I have pain of head").
w fever|fiebre|🤒
w cough|tos
w headache|dolor de cabeza
w sore throat|dolor de garganta
w dizzy|mareado
w sick|enfermo
p I have had a fever since yesterday.|Tengo fiebre desde ayer.
p I feel dizzy and tired.|Me siento mareado y cansado.
p I have a sore throat and a cough.|Tengo dolor de garganta y tos.
d How are you feeling?|I have a fever and a cough.|I am on the bus.|It is my phone.
# pharmacy|At the pharmacy
w medicine|medicina|💊
w prescription|receta médica
w pills|pastillas
w painkiller|analgésico
w allergy|alergia
w side effects|efectos secundarios
p Do I need a prescription for this?|¿Necesito receta para esto?
p Take one pill twice a day.|Tome una pastilla dos veces al día.
p Are there any side effects?|¿Tiene efectos secundarios?
d How often should I take this?|Twice a day after meals.|It is next to the bank.|I like blue.
# doctor_visit|At the doctor
w appointment|cita
w doctor|doctor|🧑‍⚕️
w check-up|revisión médica
w blood test|análisis de sangre
w treatment|tratamiento
w rest|descansar
p I would like to make an appointment.|Quisiera hacer una cita.
p How long have you had these symptoms?|¿Desde cuándo tiene estos síntomas?
p You need to rest and drink water.|Necesita descansar y tomar agua.
d How long have you felt this way?|About three days.|Two brothers.|It is in the kitchen.
# healthy_habits|Healthy habits
w exercise|ejercicio|🏃
w sleep|dormir
w diet|dieta|🥗
w stress|estrés
w water|agua|💧
w healthy|saludable
p I try to exercise three times a week.|Intento hacer ejercicio tres veces por semana.
p You should sleep at least seven hours.|Deberías dormir al menos siete horas.
p Drinking water is good for you.|Tomar agua es bueno para ti.
d How do you stay healthy?|I exercise and sleep well.|I am at the bank.|It is a taxi.
@unit work_and_business|8|B1|💼|Work & Business|Meetings, emails, interviews, and office talk.|work
# interview|Job interviews
n "Tell me about yourself" casi siempre es la primera pregunta: prepara 3 frases.
w experience|experiencia
w strength|fortaleza
w weakness|debilidad
w skills|habilidades
w resume|currículum
w salary|salario|💰
p I have five years of experience in marketing.|Tengo cinco años de experiencia en mercadotecnia.
p My greatest strength is teamwork.|Mi mayor fortaleza es el trabajo en equipo.
p Why do you want to work here?|¿Por qué quiere trabajar aquí?
d Tell me about yourself.|I am a marketing specialist with five years of experience.|I live near the park.|It is half past two.
# meetings|Meetings
w agenda|agenda
w deadline|fecha límite
w schedule|programar
w attend|asistir
w minutes|minuta
w follow up|dar seguimiento
p Let's start with the agenda.|Empecemos con la agenda.
p Could you share your screen, please?|¿Podrías compartir tu pantalla, por favor?
p We need to finish this by Friday.|Necesitamos terminar esto para el viernes.
d Can everyone hear me?|Yes, we can hear you clearly.|I am from Chile.|It is my birthday.
# emails|Writing emails
n "I am writing to…" abre un correo formal. "Best regards" lo cierra.
w attachment|archivo adjunto|📎
w regards|saludos
w reply|responder
w forward|reenviar
w subject|asunto
w urgent|urgente
p I am writing to ask about the project.|Le escribo para preguntar sobre el proyecto.
p Please find the report attached.|Adjunto encontrará el reporte.
p I look forward to hearing from you.|Quedo atento a su respuesta.
d Did you get my email?|Yes, I will reply this afternoon.|It is very cold.|I like Italian food.
# smalltalk_office|Office small talk
w coworker|compañero de trabajo
w coffee break|pausa para el café|☕
w lunch break|hora de comer
w busy week|semana ocupada
w promotion|ascenso
w deadline pressure|presión por entregas
p How was your weekend?|¿Cómo estuvo tu fin de semana?
p Do you want to grab a coffee?|¿Quieres ir por un café?
p It has been a really busy week.|Ha sido una semana muy ocupada.
d Do you want to grab a coffee?|Sure, I need a break.|I am a doctor.|It is on the corner.
# presentations|Presentations
w slide|diapositiva
w audience|audiencia
w topic|tema
w goal|objetivo
w conclusion|conclusión
w questions|preguntas
p Today I will talk about our sales results.|Hoy hablaré sobre nuestros resultados de ventas.
p Let me move on to the next slide.|Paso a la siguiente diapositiva.
p Thank you for listening. Any questions?|Gracias por escuchar. ¿Alguna pregunta?
d Does anyone have questions?|Yes, could you explain the last slide?|I am from Peru.|It is five dollars.
@unit social_life|9|B1|🎉|Social Life|Invite people, share opinions, and tell stories.|personal
# invitations|Invitations
w invite|invitar
w party|fiesta|🎉
w come over|venir a casa
w available|disponible
w busy|ocupado
w RSVP|confirmar asistencia
p Would you like to come to my party?|¿Te gustaría venir a mi fiesta?
p I would love to, but I am busy that day.|Me encantaría, pero ese día estoy ocupado.
p What time should I be there?|¿A qué hora debo llegar?
d Are you free on Saturday?|Yes, I would love to come.|It is a red bag.|I wake up at six.
# hobbies|Hobbies & free time
w hobby|pasatiempo
w hiking|senderismo|🥾
w painting|pintura|🎨
w gym|gimnasio|🏋️
w movie|película|🎬
w in my free time|en mi tiempo libre
p In my free time, I like to read.|En mi tiempo libre me gusta leer.
p I have been playing guitar for two years.|Llevo dos años tocando guitarra.
p What do you do for fun?|¿Qué haces para divertirte?
d What do you do for fun?|I play soccer on weekends.|I live in Mexico.|It is raining.
# opinions|Giving opinions
n "I think that…" y "In my opinion…" son tus mejores amigos para opinar.
w I think|yo pienso
w in my opinion|en mi opinión
w I agree|estoy de acuerdo
w I disagree|no estoy de acuerdo
w maybe|tal vez
w to be honest|para ser honesto
p In my opinion, this movie is great.|En mi opinión, esta película es genial.
p I agree with you completely.|Estoy completamente de acuerdo contigo.
p To be honest, I do not like it.|Para ser honesto, no me gusta.
d What do you think about this idea?|I think it is a good plan.|It is next to the bank.|He is my uncle.
# plans_future|Making plans
n "I am going to" = plan decidido. "I will" = decisión en el momento.
w I am going to|voy a
w next week|la próxima semana
w tomorrow|mañana
w plan|plan
w decide|decidir
w probably|probablemente
p I am going to travel next month.|Voy a viajar el próximo mes.
p We will probably stay home tonight.|Probablemente nos quedemos en casa esta noche.
p What are you doing this weekend?|¿Qué vas a hacer este fin de semana?
d What are your plans for the weekend?|I am going to visit my family.|I was at work yesterday.|It is a blue shirt.
# past_stories|Telling stories
n Pasado simple: "I went", "I saw", "I ate". Muchos verbos son irregulares.
w yesterday|ayer
w last year|el año pasado
w went|fui / fue
w saw|vi / vio
w happened|sucedió
w suddenly|de repente
p Last year I went to Canada.|El año pasado fui a Canadá.
p Suddenly, the lights went out.|De repente, se apagaron las luces.
p I could not believe what happened.|No podía creer lo que sucedió.
d What did you do last weekend?|I went to the beach with my friends.|I am going to sleep.|It is my phone.
@unit fluent_moves|10|B2|🗣️|Fluent Moves|Phone calls, negotiating, and polite disagreement.|work
# phone_calls|Phone calls
n "Hold on" y "Hang on" significan espera un momento.
w hold on|espera un momento
w speak up|hablar más fuerte
w voicemail|buzón de voz
w call back|devolver la llamada
w bad connection|mala conexión
w extension|extensión
p Could you speak a little louder, please?|¿Podría hablar un poco más fuerte, por favor?
p I will call you back in ten minutes.|Te devuelvo la llamada en diez minutos.
p The line is breaking up.|Se está cortando la llamada.
d Hello, may I speak to Mr. Smith?|One moment, please. I will transfer you.|I am from Peru.|It is on the table.
# negotiating|Negotiating
w offer|oferta
w deal|trato
w compromise|llegar a un acuerdo
w budget|presupuesto
w terms|condiciones
w counteroffer|contraoferta
p That is a little higher than our budget.|Eso es un poco más de nuestro presupuesto.
p Could we meet in the middle?|¿Podríamos llegar a un punto medio?
p We have a deal.|Tenemos un trato.
d Can you lower the price?|I can offer a ten percent discount.|I am at the bank.|It is quarter to six.
# disagree_politely|Disagreeing politely
n Suaviza el desacuerdo: "I see your point, but…" suena mucho mejor que "You are wrong".
w I see your point|entiendo tu punto
w however|sin embargo
w on the other hand|por otro lado
w I am not sure|no estoy seguro
w that said|dicho eso
w fair enough|es justo
p I see your point, but I have a different view.|Entiendo tu punto, pero tengo otra opinión.
p On the other hand, it could be expensive.|Por otro lado, podría ser costoso.
p I am not sure that is the best option.|No estoy seguro de que esa sea la mejor opción.
d I think we should cancel the project.|I see your point, but let's give it another week.|I like soup.|It is a taxi.
# describing_problems|Describing problems
w issue|problema
w fix|arreglar
w not working|no funciona
w keeps happening|sigue pasando
w as soon as possible|lo antes posible
w workaround|solución alternativa
p The app keeps crashing every time I open it.|La app se cierra cada vez que la abro.
p Could you look into this as soon as possible?|¿Podría revisarlo lo antes posible?
p We found a temporary workaround.|Encontramos una solución temporal.
d What seems to be the issue?|The system keeps freezing.|I am from Brazil.|It is my sister.
# idioms|Everyday idioms
n Los modismos no se traducen literalmente: "break the ice" = romper el hielo.
w break the ice|romper el hielo|🧊
w piece of cake|pan comido|🍰
w under the weather|enfermo, indispuesto
w hit the books|ponerse a estudiar
w call it a day|dar por terminado el día
w once in a blue moon|muy rara vez
p That exam was a piece of cake.|Ese examen fue pan comido.
p I am feeling a bit under the weather.|Me siento un poco mal.
p Let's call it a day.|Terminemos por hoy.
d How was the test?|It was a piece of cake.|It is on the left.|I live in Cuba.
@unit big_ideas|11|B2|💡|Big Ideas|Discuss technology, the environment, news, and culture.|study
# technology|Technology
w device|dispositivo
w software|programa
w update|actualización
w artificial intelligence|inteligencia artificial|🤖
w privacy|privacidad
w download|descargar
p Technology has changed the way we work.|La tecnología ha cambiado la forma en que trabajamos.
p I always update my apps.|Siempre actualizo mis aplicaciones.
p Privacy online is very important.|La privacidad en línea es muy importante.
d How has technology changed your life?|It helps me learn faster.|It is on the corner.|I am a doctor.
# environment|Environment
w climate change|cambio climático|🌍
w recycle|reciclar|♻️
w pollution|contaminación
w renewable energy|energía renovable
w waste|desperdicio
w sustainable|sustentable
p We should reduce plastic waste.|Deberíamos reducir los desechos de plástico.
p Solar energy is renewable.|La energía solar es renovable.
p Small actions can make a big difference.|Las pequeñas acciones pueden hacer una gran diferencia.
d What can we do to protect the planet?|We can recycle and use less plastic.|I am from Spain.|It is a red car.
# news_media|News & media
w headline|titular
w journalist|periodista
w source|fuente
w fake news|noticias falsas
w broadcast|transmisión
w trend|tendencia
p Did you see the news this morning?|¿Viste las noticias esta mañana?
p You should always check your sources.|Siempre debes verificar tus fuentes.
p That story is trending on social media.|Esa historia es tendencia en redes sociales.
d Did you read the news today?|Yes, the headline was surprising.|I like tea.|It is half past nine.
# culture|Culture & traditions
w tradition|tradición
w festival|festival
w customs|costumbres
w celebrate|celebrar|🎊
w heritage|patrimonio
w local|local
p In my country, we celebrate the Day of the Dead.|En mi país celebramos el Día de Muertos.
p Every culture has its own traditions.|Cada cultura tiene sus propias tradiciones.
p I would love to learn more about your customs.|Me encantaría aprender más sobre tus costumbres.
d What is a tradition in your country?|We celebrate with music and food.|It is a quarter to six.|I am at home.
# future_goals|Goals & the future
w goal|meta
w achieve|lograr
w improve|mejorar
w career|carrera
w dream|sueño
w in the long run|a largo plazo
p My goal is to be fluent in English next year.|Mi meta es hablar inglés con fluidez el próximo año.
p I hope to achieve my dreams.|Espero lograr mis sueños.
p In the long run, practice makes perfect.|A largo plazo, la práctica hace al maestro.
d Where do you see yourself in five years?|I see myself leading a team.|It is raining.|He is my brother.
'''

LEVEL_TO_RANK = {"A1": 0, "A2": 1, "B1": 2, "B2": 3}
PROFILE_LEVEL_RANK = {"beginner": 0, "elementary": 1, "intermediate": 2, "advanced": 3}
GOAL_LABELS = {"work": "Work", "travel": "Travel", "study": "Study", "exams": "Exams", "personal": "Personal growth"}

SECTION_DEFS = [
    {"code": "foundations", "title": "Foundations", "level": "A1", "units": ["first_steps", "everyday_english", "home_and_city"]},
    {"code": "real_life", "title": "Real Life", "level": "A2", "units": ["at_the_restaurant", "shopping_and_money", "travel_and_tourism", "health_and_body"]},
    {"code": "career_social", "title": "Career & Social", "level": "B1", "units": ["work_and_business", "social_life"]},
    {"code": "fluency", "title": "Fluency", "level": "B2", "units": ["fluent_moves", "big_ideas"]},
]


def _parse_curriculum(text):
    units, unit, lesson = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@unit "):
            code, order, level, icon, title, desc, goal = line[6:].split("|")
            unit = {"code": code, "order": int(order), "level": level, "icon": icon, "title": title,
                    "description": desc, "goal": goal, "xp_required": 0, "lessons": []}
            units.append(unit)
            lesson = None
            continue
        tag, _, rest = line.partition(" ")
        f = rest.split("|")
        if tag == "#":
            lesson = {"id": f[0], "title": f[1], "note": "", "words": [], "phrases": [], "dialogs": []}
            unit["lessons"].append(lesson)
        elif tag == "n":
            lesson["note"] = rest
        elif tag == "w":
            lesson["words"].append({"en": f[0], "es": f[1], "emoji": f[2] if len(f) > 2 else ""})
        elif tag == "p":
            lesson["phrases"].append({"en": f[0], "es": f[1]})
        elif tag == "d":
            lesson["dialogs"].append({"q": f[0], "a": f[1], "wrong": f[2:]})
    for si, sec in enumerate(SECTION_DEFS):
        for code in sec["units"]:
            for u in units:
                if u["code"] == code:
                    u["section"] = si
    for u in units:
        # "topics" se conserva por compatibilidad: cada lección es un tema, más el reto final de la unidad.
        u["topics"] = [{"id": l["id"], "title": l["title"]} for l in u["lessons"]]
        u["topics"].append({"id": "challenge", "title": "Unit challenge", "challenge": True})
    return units


LEARNING_UNITS = _parse_curriculum(CURRICULUM_TEXT)

LEARNING_TOOL_LABELS = {
    "pronunciation": "Pronunciation",
    "writing": "Writing",
    "reading": "Reading",
    "dictado": "Listening",
}


def get_unit(code):
    return next((u for u in LEARNING_UNITS if u["code"] == code), None)


def get_topic(unit, topic_id):
    return next((t for t in (unit or {}).get("topics", []) if t["id"] == topic_id), None)


def get_lesson(unit, lesson_id):
    return next((l for l in (unit or {}).get("lessons", []) if l["id"] == lesson_id), None)


def fetch_learning_progress(user_id):
    """Devuelve un dict {(unit_code, topic_id): fila} solo con los temas completados."""
    client = supabase_admin or supabase
    if not client:
        return {}
    try:
        rows = (
            client.table("learning_progress")
            .select("unit_code,topic_id,tool,score,completed")
            .eq("user_id", user_id)
            .execute()
        ).data or []
    except Exception as exc:
        print(f"[LEARNING PROGRESS] {exc}")
        return {}
    return {(r["unit_code"], r["topic_id"]): r for r in rows if r.get("completed")}


def _upsert_progress(client, user_id, unit_code, topic_id, tool, score, passed):
    """Guarda/actualiza el mejor puntaje. Devuelve (ya_estaba_completado, mejor_puntaje).
    OJO: se usa .limit(1) y no .maybe_single(), porque maybe_single devuelve None cuando no hay filas
    y eso hacía que el primer intento de cada tema nunca se guardara."""
    res = (
        client.table("learning_progress").select("id,completed,score")
        .eq("user_id", user_id).eq("unit_code", unit_code).eq("topic_id", topic_id)
        .limit(1).execute()
    )
    rows = getattr(res, "data", None) or []
    if rows:
        row = rows[0]
        already_done = bool(row.get("completed"))
        best = max(score, row.get("score") or 0)
        client.table("learning_progress").update({
            "tool": tool, "score": best, "completed": already_done or passed,
        }).eq("id", row["id"]).execute()
        return already_done, best
    client.table("learning_progress").insert({
        "user_id": user_id, "unit_code": unit_code, "topic_id": topic_id,
        "tool": tool, "score": score, "completed": passed,
    }).execute()
    return False, score


def record_learning_progress(user_id, unit_code, topic_id, tool, score):
    """Compatibilidad con las herramientas sueltas (escritura, lectura...). Devuelve None si no aplica."""
    if not unit_code or not topic_id:
        return None
    unit = get_unit(unit_code)
    if not unit or not get_topic(unit, topic_id):
        return None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None
    client = supabase_admin or supabase
    if not client:
        return None
    passed = score >= PASS_THRESHOLD
    try:
        already_done, _best = _upsert_progress(client, user_id, unit_code, topic_id, tool, score, passed)
    except Exception as exc:
        print(f"[LEARNING PROGRESS SAVE] {exc}")
        return None
    newly_completed = passed and not already_done
    if newly_completed:
        award_xp(user_id, 30)
    progress = fetch_learning_progress(user_id)
    total = len(unit["topics"])
    completed_count = sum(1 for t in unit["topics"] if (unit_code, t["id"]) in progress)
    return {"passed": passed, "newly_completed": newly_completed, "unit_completed": completed_count == total,
            "completed_topics": completed_count, "total_topics": total}


def stars_for(score):
    if score is None:
        return 0
    return 3 if score >= 90 else 2 if score >= 75 else 1 if score >= PASS_THRESHOLD else 0


def daily_target_lessons(minutes):
    try:
        return max(1, min(8, round(int(minutes) / 5)))
    except (TypeError, ValueError):
        return 2


# ---------------------------------------------------------------------------
#  Registro de sesiones (tabla opcional learning_sessions; si no existe, todo sigue funcionando)
# ---------------------------------------------------------------------------
def _log_session(user_id, kind, unit_code, lesson_id, score, stars, xp, mistakes, seconds):
    client = supabase_admin or supabase
    if not client:
        return
    try:
        client.table("learning_sessions").insert({
            "user_id": user_id, "kind": kind, "unit_code": unit_code, "lesson_id": lesson_id,
            "score": score, "stars": stars, "xp": xp, "mistakes": mistakes or [], "seconds": seconds,
        }).execute()
    except Exception as exc:
        print(f"[LEARNING SESSION LOG] {exc}")


def sessions_today(user_id):
    client = supabase_admin or supabase
    if not client:
        return 0
    try:
        start = datetime.now(timezone.utc).date().isoformat()
        rows = (client.table("learning_sessions").select("id").eq("user_id", user_id)
                .gte("created_at", start).limit(50).execute()).data or []
        return len(rows)
    except Exception:
        return 0


def session_days(user_id, since_iso):
    """Fechas (ISO) en las que hubo lecciones, para la racha semanal."""
    client = supabase_admin or supabase
    out = set()
    if not client:
        return out
    try:
        rows = (client.table("learning_sessions").select("created_at").eq("user_id", user_id)
                .gte("created_at", since_iso).limit(500).execute()).data or []
        for r in rows:
            ca = r.get("created_at")
            if ca:
                try:
                    out.add(datetime.fromisoformat(ca.replace("Z", "+00:00")).date().isoformat())
                except Exception:
                    pass
    except Exception:
        pass
    return out


def recent_mistakes(user_id, limit=8):
    """Palabras/frases falladas en las últimas lecciones (las más recientes primero, sin repetir)."""
    client = supabase_admin or supabase
    if not client:
        return []
    try:
        rows = (client.table("learning_sessions").select("mistakes,created_at").eq("user_id", user_id)
                .order("created_at", desc=True).limit(12).execute()).data or []
    except Exception:
        return []
    seen, out = set(), []
    for r in rows:
        for m in (r.get("mistakes") or []):
            if isinstance(m, dict) and m.get("en") and m["en"].lower() not in seen:
                seen.add(m["en"].lower())
                out.append({"en": m["en"], "es": m.get("es", "")})
                if len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------------------
#  Estado de la ruta: qué está abierto, qué sigue, qué se recomienda
# ---------------------------------------------------------------------------
def _profile_for_path(user_id):
    client = supabase_admin or supabase
    out = {"cefr_level": "", "learning_goal": "", "daily_goal_minutes": 10, "xp": 0}
    if not client:
        return out
    try:
        rows = (client.table("profiles").select("cefr_level,learning_goal,daily_goal_minutes,xp")
                .eq("id", user_id).limit(1).execute()).data or []
        if rows:
            r = rows[0]
            out.update({
                "cefr_level": (r.get("cefr_level") or "").lower(),
                "learning_goal": (r.get("learning_goal") or "").lower(),
                "daily_goal_minutes": r.get("daily_goal_minutes") or 10,
                "xp": r.get("xp") or 0,
            })
    except Exception as exc:
        print(f"[LEARNING PATH PROFILE] {exc}")
    return out


def _gem_unlocks(user_id):
    client = supabase_admin or supabase
    if not client:
        return set()
    try:
        rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user_id).execute().data or []
        return {r["unit_code"] for r in rows}
    except Exception as exc:
        print(f"[LEARNING PATH GEM UNLOCKS] {exc}")
        return set()


def compute_path(progress, level_rank, goal, gem_unlocked):
    """Calcula secciones, unidades y lecciones con su estado, y la 'siguiente lección' recomendada."""
    sections_out = []
    prev_pct = 1.0
    unit_by_code = {u["code"]: u for u in LEARNING_UNITS}
    for si, sdef in enumerate(SECTION_DEFS):
        sec_open = si == 0 or si <= level_rank or prev_pct >= 0.6
        units_out = []
        done_total = lesson_total = 0
        for code in sdef["units"]:
            u = unit_by_code[code]
            unit_open = sec_open or code in gem_unlocked
            lessons, prev_done = [], True
            for i, t in enumerate(u["topics"]):
                row = progress.get((code, t["id"]))
                completed = bool(row)
                avail = unit_open and (i == 0 or lessons[i - 1]["completed"])
                lessons.append({
                    "id": t["id"], "title": t["title"], "challenge": bool(t.get("challenge")),
                    "completed": completed, "score": row.get("score") if row else None,
                    "stars": stars_for(row.get("score")) if row else 0,
                    "state": "done" if completed else ("available" if avail else "locked"),
                })
            done = sum(1 for l in lessons if l["completed"])
            done_total += done
            lesson_total += len(lessons)
            units_out.append({
                "code": code, "order": u["order"], "title": u["title"], "description": u["description"],
                "icon": u["icon"], "level": u["level"], "goal": u["goal"], "section": si,
                "total_topics": len(lessons), "completed_topics": done, "completed": done == len(lessons),
                "unlocked": unit_open, "xp_required": 0, "lessons": lessons,
                "recommended": bool(goal and u["goal"] == goal and unit_open and done < len(lessons)),
                "stars": sum(l["stars"] for l in lessons), "max_stars": 3 * len(lessons),
            })
        prev_pct = (done_total / lesson_total) if lesson_total else 0
        sections_out.append({
            "code": sdef["code"], "title": sdef["title"], "level": sdef["level"], "open": sec_open,
            "done": done_total, "total": lesson_total, "units": units_out,
        })

    # Siguiente lección: empieza por la sección que corresponde a su nivel; dentro de la sección,
    # primero las unidades que coinciden con su objetivo; las secciones anteriores quedan como repaso.
    order = list(range(level_rank, len(sections_out))) + list(range(0, level_rank))
    nxt = None
    for si in order:
        sec = sections_out[si]
        if not sec["open"]:
            continue
        units = sorted(sec["units"], key=lambda x: (0 if x["recommended"] else 1, x["order"]))
        for un in units:
            if not un["unlocked"] or un["completed"]:
                continue
            les = next((l for l in un["lessons"] if l["state"] == "available"), None)
            if les:
                if un["recommended"]:
                    reason = "Matches your goal: " + GOAL_LABELS.get(goal, goal.title())
                elif si == level_rank:
                    reason = "Picked for your level"
                else:
                    reason = "Next in your path"
                nxt = {"unit_code": un["code"], "unit_title": un["title"], "icon": un["icon"],
                       "lesson_id": les["id"], "lesson_title": les["title"], "challenge": les["challenge"],
                       "reason": reason}
                break
        if nxt:
            break
    return sections_out, nxt


# ---------------------------------------------------------------------------
#  Generador de ejercicios (determinista a partir de los datos del currículo)
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ'’-]+")


def _tokens(sentence):
    return _TOKEN_RE.findall(sentence)


def _norm(text):
    return " ".join(w.lower().replace("’", "'") for w in _tokens(text))


class _Cycle:
    def __init__(self, items, rng):
        self.items = list(items)
        self.rng = rng
        self.queue = []

    def next(self):
        if not self.items:
            return None
        if not self.queue:
            self.queue = list(self.items)
            self.rng.shuffle(self.queue)
        return self.queue.pop()


def _distractors(rng, answer, pool, n, key=lambda x: x):
    seen = {key(answer).lower()}
    cand = []
    for x in pool:
        k = key(x).lower()
        if k not in seen:
            seen.add(k)
            cand.append(x)
    rng.shuffle(cand)
    return cand[:n]


LESSON_RECIPE = ["pick_meaning", "pick_word", "listen_pick", "pick_meaning", "match", "build", "fill",
                 "speak", "listen_pick", "build", "dialog", "type_listen", "speak", "build"]
CHALLENGE_RECIPE = ["pick_meaning", "listen_pick", "pick_word", "match", "build", "fill", "speak", "dialog",
                    "build", "type_listen", "pick_word", "fill", "dialog", "build", "speak", "listen_pick"]
REVIEW_RECIPE = ["pick_meaning", "listen_pick", "pick_word", "build", "match", "pick_meaning", "type_listen",
                 "fill", "build", "pick_word"]


def build_exercises(unit, lessons, recipe, rng, diff=0, extra_words=None):
    """lessons: lecciones fuente. diff<0 = más fácil, diff>0 = más difícil (el estudiante supera la unidad)."""
    words = [dict(w, lesson=l["id"]) for l in lessons for w in l["words"]]
    phrases = [dict(p, lesson=l["id"]) for l in lessons for p in l["phrases"]]
    dialogs = [dict(d, lesson=l["id"]) for l in lessons for d in l["dialogs"]]
    if extra_words:
        words = [dict(w, lesson="review") for w in extra_words] + words
    unit_words = [w for l in unit["lessons"] for w in l["words"]]
    unit_phrases = [p for l in unit["lessons"] for p in l["phrases"]]
    word_cycle = _Cycle(words, rng)
    phrase_cycle = _Cycle(phrases, rng)
    dialog_cycle = _Cycle(dialogs, rng)
    single_tokens = sorted({t for w in unit_words for t in _tokens(w["en"]) if len(t) >= 3})
    out = []

    for n, kind in enumerate(recipe):
        ex = None
        if kind in ("pick_meaning", "pick_word", "listen_pick"):
            w = word_cycle.next()
            if not w:
                continue
            ref = {"en": w["en"], "es": w["es"]}
            if kind == "pick_word":
                d = _distractors(rng, w, unit_words, 3, key=lambda x: x["en"])
                opts = [w["en"]] + [x["en"] for x in d]
                rng.shuffle(opts)
                ex = {"type": "pick_word", "q": w["es"], "emoji": w.get("emoji", ""), "options": opts,
                      "answer": w["en"], "ref": ref}
            elif kind == "listen_pick":
                d = _distractors(rng, w, unit_words, 3, key=lambda x: x["en"])
                opts = [w["en"]] + [x["en"] for x in d]
                rng.shuffle(opts)
                ex = {"type": "listen_pick", "say": w["en"], "options": opts, "answer": w["en"], "ref": ref}
            else:
                if diff > 0 and n % 2 == 1:
                    ex = {"type": "type_translate", "q": w["es"], "answer": w["en"], "ref": ref}
                else:
                    d = _distractors(rng, w, unit_words, 3, key=lambda x: x["es"])
                    opts = [w["es"]] + [x["es"] for x in d]
                    rng.shuffle(opts)
                    ex = {"type": "pick_meaning", "q": w["en"], "say": w["en"], "emoji": w.get("emoji", ""),
                          "options": opts, "answer": w["es"], "ref": ref}
        elif kind == "match":
            picks = rng.sample(words, min(5, len(words)))
            seen, pairs = set(), []
            for w in picks:
                if w["en"].lower() not in seen and w["es"].lower() not in {p["es"].lower() for p in pairs}:
                    seen.add(w["en"].lower())
                    pairs.append({"en": w["en"], "es": w["es"]})
            if len(pairs) >= 3:
                ex = {"type": "match", "pairs": pairs}
        elif kind in ("build", "fill", "speak", "type_listen"):
            p = phrase_cycle.next()
            if not p:
                continue
            ref = {"en": p["en"], "es": p["es"]}
            if kind == "build":
                ans = _tokens(p["en"])
                extra = 4 if diff > 0 else (1 if diff < 0 else 2)
                low = {t.lower() for t in ans}
                spare = [t for t in single_tokens if t.lower() not in low]
                rng.shuffle(spare)
                bank = ans + spare[:extra]
                rng.shuffle(bank)
                ex = {"type": "build", "q": p["es"], "say": p["en"], "answer": p["en"],
                      "answer_tokens": ans, "bank": bank, "ref": ref}
            elif kind == "fill":
                lesson_tokens = {t.lower() for l in lessons for w in l["words"] for t in _tokens(w["en"]) if len(t) >= 3}
                toks = _tokens(p["en"])
                cands = [t for t in toks if t.lower() in lesson_tokens] or [t for t in toks if len(t) >= 4]
                if not cands:
                    continue
                target = max(cands, key=len)
                spare = [t for t in single_tokens if t.lower() != target.lower() and t.lower() not in {x.lower() for x in toks}]
                rng.shuffle(spare)
                opts = [target] + spare[:3]
                rng.shuffle(opts)
                sentence = p["en"].replace(target, "____", 1)
                ex = {"type": "fill", "sentence": sentence, "es": p["es"], "options": opts, "answer": target,
                      "say": p["en"], "ref": ref}
            elif kind == "speak":
                ex = {"type": "speak", "text": p["en"], "es": p["es"], "ref": ref}
            else:
                ex = {"type": "type_listen", "say": p["en"], "answer": p["en"], "es": p["es"], "ref": ref}
        elif kind == "dialog":
            d = dialog_cycle.next()
            if not d:
                continue
            opts = [d["a"]] + list(d["wrong"][:2])
            rng.shuffle(opts)
            ex = {"type": "dialog", "q": d["q"], "say": d["q"], "options": opts, "answer": d["a"],
                  "ref": {"en": d["a"], "es": ""}}
        if ex:
            ex["id"] = f"e{len(out) + 1}"
            out.append(ex)
    return out


def build_lesson_payload(unit, lesson_id, user_rank, mode="lesson", mistakes=None, seed=None):
    rng = random.Random(seed if seed is not None else time.time_ns())
    unit_rank = LEVEL_TO_RANK.get(unit["level"], 0)
    diff = user_rank - unit_rank
    diff = -1 if diff < 0 else (1 if diff > 0 else 0)
    if mode == "review":
        pool_lessons = [l for l in unit["lessons"]]
        words = []
        for m in (mistakes or [])[:8]:
            if m.get("es"):
                words.append({"en": m["en"], "es": m["es"], "emoji": ""})
        ex = build_exercises(unit, pool_lessons, REVIEW_RECIPE, rng, diff=diff, extra_words=words)
        return {"title": "Review: your tricky words", "note": "", "teach": [], "exercises": ex, "challenge": False}
    if lesson_id == "challenge":
        ex = build_exercises(unit, unit["lessons"], CHALLENGE_RECIPE, rng, diff=diff)
        return {"title": unit["title"] + " — Unit challenge", "note": "", "teach": [], "exercises": ex, "challenge": True}
    lesson = get_lesson(unit, lesson_id)
    ex = build_exercises(unit, [lesson], LESSON_RECIPE, rng, diff=diff)
    return {"title": lesson["title"], "note": lesson.get("note", ""), "teach": lesson["words"],
            "exercises": ex, "challenge": False, "difficulty": ["easy", "normal", "hard"][diff + 1]}


# ---------------------------------------------------------------------------
#  Laboratorio de sonidos (estilo ELSA): sonidos difíciles para hispanohablantes
# ---------------------------------------------------------------------------
SOUND_LAB = {
    "th": {"ipa": "θ", "name": "TH suave", "tip": "Saca la punta de la lengua entre los dientes y sopla aire sin voz. No es 't' ni 's'.",
           "words": ["think", "thank", "three", "thumb", "bath", "month"], "phrase": "Thank you for the three thick books."},
    "dh": {"ipa": "ð", "name": "TH sonora", "tip": "Lengua entre los dientes, pero con voz: debe vibrar. No es 'd'.",
           "words": ["this", "that", "mother", "weather", "they", "brother"], "phrase": "This is my mother and that is my brother."},
    "ih": {"ipa": "ɪ", "name": "I corta", "tip": "Más corta y relajada que la 'i' española. 'Ship' no es 'sheep'.",
           "words": ["sit", "ship", "big", "fish", "live", "bit"], "phrase": "Sit in this big chair."},
    "iy": {"ipa": "iː", "name": "I larga", "tip": "Estira la 'i' con los labios sonriendo. 'Sheep', 'seat'.",
           "words": ["seat", "sheep", "beach", "green", "leave", "feel"], "phrase": "Please leave the green sheep on the beach."},
    "ae": {"ipa": "æ", "name": "A abierta", "tip": "Abre la boca como para una 'a' pero con sonido de 'e'. 'Cat' no es 'ket'.",
           "words": ["cat", "black", "hat", "bad", "man", "apple"], "phrase": "The black cat sat on a flat map."},
    "ah": {"ipa": "ʌ", "name": "A corta", "tip": "Una 'a' corta y relajada desde la garganta. 'Cup' no es 'cop'.",
           "words": ["cup", "bus", "love", "sun", "up", "color"], "phrase": "My brother loves the sun and a cup of juice."},
    "sh": {"ipa": "ʃ", "name": "SH", "tip": "Como pedir silencio: 'shhh'. No es 'ch'.",
           "words": ["ship", "shoe", "fish", "wash", "shop", "nation"], "phrase": "She washes her shoes in the shop."},
    "jh": {"ipa": "dʒ", "name": "J inglesa", "tip": "Como una 'ch' pero con voz. 'Job', 'age'. No es la 'j' española.",
           "words": ["job", "juice", "age", "bridge", "general", "jacket"], "phrase": "Jack has a great job in June."},
    "v": {"ipa": "v", "name": "V", "tip": "Dientes superiores sobre el labio inferior y vibra. No es 'b'.",
          "words": ["very", "voice", "love", "visit", "never", "move"], "phrase": "I never visit Venice in November."},
    "z": {"ipa": "z", "name": "Z", "tip": "Una 's' con vibración en la garganta. 'Zoo', 'easy'.",
          "words": ["zoo", "easy", "busy", "because", "size", "lazy"], "phrase": "The lazy zebra is busy at the zoo."},
    "r": {"ipa": "ɹ", "name": "R inglesa", "tip": "La lengua no toca el paladar ni vibra: enróllala hacia atrás.",
          "words": ["red", "right", "car", "around", "story", "really"], "phrase": "The red car is really around the corner."},
    "h": {"ipa": "h", "name": "H suave", "tip": "Un soplo suave de aire, mucho más suave que la 'j' española.",
          "words": ["house", "happy", "who", "behind", "hello", "high"], "phrase": "Hello, how is your happy house?"},
    "ng": {"ipa": "ŋ", "name": "NG", "tip": "El sonido sale por la nariz; no pronuncies una 'g' fuerte al final.",
           "words": ["sing", "long", "morning", "thing", "young", "king"], "phrase": "Every morning the young king sings a long song."},
    "w": {"ipa": "w", "name": "W", "tip": "Redondea los labios como para decir 'u' y suéltalos rápido.",
          "words": ["water", "would", "we", "away", "window", "week"], "phrase": "We would walk away from the window this week."},
    "uh": {"ipa": "ʊ", "name": "U corta", "tip": "Una 'u' corta y relajada. 'Book', 'good'.",
           "words": ["book", "good", "look", "foot", "put", "cook"], "phrase": "Look at the good book the cook put down."},
    "uw": {"ipa": "uː", "name": "U larga", "tip": "Alarga la 'u' con los labios redondeados. 'Food', 'blue'.",
           "words": ["food", "blue", "moon", "true", "too", "school"], "phrase": "The blue moon is too bright at school."},
    "er": {"ipa": "ɝ", "name": "ER", "tip": "Una 'e' con la lengua curvada hacia atrás. 'Bird', 'work'.",
           "words": ["bird", "work", "learn", "first", "turn", "world"], "phrase": "The first bird learns to turn in the world."},
    "y": {"ipa": "j", "name": "Y suave", "tip": "Una 'i' rápida que se desliza: 'yes' no es 'jes'.",
          "words": ["yes", "you", "yellow", "young", "year", "yet"], "phrase": "Yes, you are young and yellow is your year."},
}
DEFAULT_SOUND_FOCUS = ["th", "ih", "v", "ae", "sh", "dh"]
_IPA_TO_SAPI = {
    "θ": "th", "ð": "dh", "ɪ": "ih", "i": "iy", "iː": "iy", "ʃ": "sh", "æ": "ae", "ʒ": "zh", "ʊ": "uh",
    "u": "uw", "uː": "uw", "tʃ": "ch", "dʒ": "jh", "ŋ": "ng", "ɛ": "eh", "ʌ": "ah", "ə": "ax", "ɔ": "ao",
    "ɑ": "aa", "ɝ": "er", "ɚ": "er", "ɹ": "r", "j": "y", "ɡ": "g", "eɪ": "ey", "oʊ": "ow", "aɪ": "ay",
}


def normalize_phoneme(p):
    p = (p or "").strip().lower()
    return _IPA_TO_SAPI.get(p, p)


def sound_info(sid):
    s = SOUND_LAB.get(sid)
    return {"id": sid, **s} if s else None


def weak_sounds_from_payload(payload, threshold=65):
    """Sonidos con baja precisión en un solo intento (para mostrar consejos al instante)."""
    found = {}
    for w in payload.get("palabras", []):
        for f in w.get("fonemas", []):
            sid = normalize_phoneme(f.get("fonema"))
            if sid in SOUND_LAB and (f.get("precision") or 0) < threshold:
                found[sid] = min(found.get(sid, 100), f.get("precision") or 0)
    return [{"id": s, "ipa": SOUND_LAB[s]["ipa"], "name": SOUND_LAB[s]["name"], "tip": SOUND_LAB[s]["tip"],
             "accuracy": a} for s, a in sorted(found.items(), key=lambda kv: kv[1])][:3]


def phoneme_stats(user_id, limit=40):
    """Promedio de precisión por fonema, leído del historial real de pronunciación."""
    client = supabase_admin or supabase
    stats = {}
    if not client:
        return stats
    try:
        rows = (client.table("historial_pronunciacion").select("detalles_json,created_at")
                .eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()).data or []
    except Exception as exc:
        print(f"[PHONEME STATS] {exc}")
        return stats
    for r in rows:
        d = r.get("detalles_json")
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                d = None
        if not isinstance(d, dict):
            continue
        for w in d.get("palabras", []) or []:
            for f in w.get("fonemas", []) or []:
                sid = normalize_phoneme(f.get("fonema"))
                acc = f.get("precision")
                if sid in SOUND_LAB and isinstance(acc, (int, float)):
                    s = stats.setdefault(sid, [0.0, 0])
                    s[0] += acc
                    s[1] += 1
    return {k: {"avg": round(v[0] / v[1], 1), "samples": v[1]} for k, v in stats.items() if v[1] > 0}


ALLOWED_AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@app.post("/api/perfil")
def update_profile():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    if not (2 <= len(username) <= 30):
        return json_error("El nombre debe tener entre 2 y 30 caracteres.")
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        client.table("profiles").update({"username": username}).eq("id", user.id).execute()
        return jsonify({"ok": True, "username": username})
    except Exception as exc:
        return json_error(f"No se pudo guardar el nombre: {exc}", 500)


@app.post("/api/perfil/avatar")
def upload_avatar():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    file = request.files.get("avatar")
    if not file:
        return json_error("Selecciona una imagen.")
    mime = (file.mimetype or "").lower()
    ext = ALLOWED_AVATAR_TYPES.get(mime)
    if not ext:
        return json_error("Solo se permiten imágenes JPG, PNG o WEBP.")
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        file_bytes = file.read()
        if len(file_bytes) > 4 * 1024 * 1024:
            return json_error("La imagen no debe pesar más de 4 MB.")
        path = f"{user.id}/avatar.{ext}"
        client.storage.from_("avatars").upload(
            path, file_bytes, {"content-type": mime, "upsert": "true"}
        )
        public_url = client.storage.from_("avatars").get_public_url(path)
        public_url = f"{public_url.split('?')[0]}?v={int(datetime.now(timezone.utc).timestamp())}"
        client.table("profiles").update({"avatar_url": public_url}).eq("id", user.id).execute()
        return jsonify({"ok": True, "avatar_url": public_url})
    except Exception as exc:
        return json_error(f"No se pudo subir la foto: {exc}", 500)


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Talvo English",
        "ai": bool(ai_client),
        "speech": bool(AZURE_SPEECH_KEY and AZURE_SPEECH_REGION),
        "supabase": bool(supabase),
    })


CEFR_LEVELS = {"beginner", "elementary", "intermediate", "advanced"}
LEARNING_GOALS = {"work", "travel", "study", "exams", "personal"}


@app.post("/api/onboarding")
def save_onboarding():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    goal = (body.get("learning_goal") or "").strip().lower()
    level = (body.get("cefr_level") or "").strip().lower()
    minutes = body.get("daily_goal_minutes")
    if goal not in LEARNING_GOALS:
        return json_error("Selecciona un objetivo válido.")
    if level not in CEFR_LEVELS:
        return json_error("Selecciona un nivel válido.")
    try:
        minutes = int(minutes)
        if minutes not in (5, 10, 15, 20, 30):
            raise ValueError
    except (TypeError, ValueError):
        return json_error("Selecciona una meta diaria válida.")

    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        client.table("profiles").update({
            "learning_goal": goal,
            "cefr_level": level,
            "daily_goal_minutes": minutes,
            "onboarded": True,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True})
    except Exception as exc:
        return json_error(f"No se pudo guardar tu información: {exc}", 500)


@app.get("/api/session")
def session_info():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return jsonify({"authenticated": False, "error": error[0]}), error[1]

    is_subscribed = False
    trial_dias_restantes = 0
    en_prueba = False
    username = None
    avatar_url = None
    onboarded = False
    cefr_level = None
    learning_goal = None
    daily_goal_minutes = None
    gems = 0
    avatar_frame = None
    client = supabase_admin or supabase
    if client:
        try:
            profile = (
                client.table("profiles")
                .select("is_subscribed,trial_ends_at,username,avatar_url,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems,avatar_frame")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            data = profile.data or {}
            is_paid = bool(data.get("is_subscribed"))
            username = data.get("username")
            avatar_url = data.get("avatar_url")
            onboarded = bool(data.get("onboarded"))
            cefr_level = data.get("cefr_level")
            learning_goal = data.get("learning_goal")
            daily_goal_minutes = data.get("daily_goal_minutes")
            gems = data.get("gems") or 0
            avatar_frame = data.get("avatar_frame")
            trial_ends_at = data.get("trial_ends_at")
            if trial_ends_at:
                try:
                    deadline = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                    remaining = deadline - datetime.now(timezone.utc)
                    if remaining.total_seconds() > 0:
                        en_prueba = True
                        trial_dias_restantes = max(1, round(remaining.total_seconds() / 86400))
                except ValueError:
                    pass
            is_subscribed = is_paid or en_prueba
        except Exception as exc:
            print(f"[SESSION PROFILE] {exc}")

    if is_admin_user(user):
        is_subscribed = True  # el administrador nunca se queda fuera de su propia app
    return jsonify({
        "authenticated": True,
        "is_subscribed": is_subscribed,
        "en_prueba": en_prueba,
        "trial_dias_restantes": trial_dias_restantes,
        "es_admin": is_admin_user(user),
        "user": {
            "id": user.id, "email": user.email, "miembro_desde": getattr(user, "created_at", None),
            "username": username, "avatar_url": avatar_url, "onboarded": onboarded,
            "cefr_level": cefr_level, "learning_goal": learning_goal, "daily_goal_minutes": daily_goal_minutes,
            "gems": gems, "avatar_frame": avatar_frame,
        },
    })


_tts_cache = OrderedDict()
_tts_lock = threading.Lock()


@app.post("/api/sintetizar-audio")
def synthesize_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return json_error("El servicio de voz no está configurado en el servidor.", 500)

    body = request.get_json(silent=True) or {}
    text = (body.get("texto") or body.get("text") or "").strip()
    if not text:
        return json_error("No hay texto para convertir a audio.")
    if len(text) > 600:
        text = text[:600]

    voice = (body.get("voz") or "en-US-AvaMultilingualNeural").strip()
    # Solo voces neuronales estándar en inglés (evita voces HD que cuestan más).
    if not re.fullmatch(r"en-[A-Z]{2}-[A-Za-z]+Neural", voice):
        voice = "en-US-AvaMultilingualNeural"

    cache_key = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()
    with _tts_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
    if cached is not None:
        return Response(cached, mimetype="audio/mpeg")

    config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    config.speech_synthesis_voice_name = voice
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detail = getattr(result, "cancellation_details", None)
        message = detail.error_details if detail else "No se pudo generar el audio."
        return json_error(f"No se pudo generar el audio: {message}", 500)

    audio_bytes = bytes(result.audio_data)
    if len(audio_bytes) <= 200_000:
        with _tts_lock:
            _tts_cache[cache_key] = audio_bytes
            while len(_tts_cache) > 80:
                _tts_cache.popitem(last=False)
    return Response(audio_bytes, mimetype="audio/mpeg")


@app.get("/nueva-frase")
def new_phrase():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create one natural English sentence for pronunciation practice. Return JSON only with exact keys: frase (the English sentence), traduccion (Spanish translation).",
            "Generate a useful sentence between 8 and 18 words. Avoid slang and proper names.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar la frase: {exc}", 500)


@app.get("/nuevo-tema-libre")
def new_free_topic():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create a speaking practice topic for an English learner. Return JSON only with exact keys: tema (the topic, in English), instrucciones (short instructions in Spanish on what to talk about and for how long).",
            "Give a practical topic that encourages 45-90 seconds of speaking.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el tema: {exc}", 500)


@app.get("/nuevo-trabalenguas")
def new_twister():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create a short English tongue twister suitable for pronunciation practice. Return JSON only with exact keys: trabalenguas (the tongue twister, in English), enfoque (short description in Spanish of which sounds it targets).",
            "Generate one original tongue twister, 8-18 words, challenging but pronounceable.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el trabalenguas: {exc}", 500)


READING_LIBRARY = [
    {"id": "ny_day", "title": "A Day in New York", "level": "intermediate", "topic": "a typical day exploring New York City", "minutes": 6},
    {"id": "travel_alone", "title": "Traveling Alone", "level": "beginner", "topic": "the experience of traveling alone for the first time", "minutes": 4},
    {"id": "future_tech", "title": "The Future of Technology", "level": "advanced", "topic": "how technology might change everyday life in the future", "minutes": 8},
    {"id": "healthy_habits", "title": "Healthy Habits", "level": "intermediate", "topic": "building healthy daily habits", "minutes": 5},
    {"id": "power_of_habits", "title": "The Power of Habits", "level": "advanced", "topic": "how small habits shape our lives, in a reflective tone", "minutes": 7},
    {"id": "environment", "title": "Environment and You", "level": "intermediate", "topic": "small everyday actions that help the environment", "minutes": 5},
]


def get_reading_entry(entry_id):
    return next((x for x in READING_LIBRARY if x["id"] == entry_id), None)


@app.get("/api/reading/library")
def reading_library():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    return jsonify({"ok": True, "items": [
        {"id": x["id"], "title": x["title"], "level": x["level"], "minutes": x["minutes"]}
        for x in READING_LIBRARY
    ]})


@app.get("/api/reading/library/<entry_id>")
def reading_library_item(entry_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    entry = get_reading_entry(entry_id)
    if not entry:
        return json_error("Lectura no encontrada.", 404)
    try:
        data = ai_json(
            "Create an informational English reading passage for a learner. Return JSON only with exact keys: texto (the reading passage, in English, 180-260 words), titulo (short title), nivel (CEFR level), vocabulario (array of 5 objects with keys 'palabra' and 'significado', useful vocabulary words with brief English definitions).",
            f"Create 180-260 words about {entry['topic']}, at a {entry['level']} level. Do not include questions or Spanish translation in the passage itself.",
        )
        data["entry_id"] = entry_id
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar la lectura: {exc}", 500)


@app.get("/nuevo-texto-lectura")
def new_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an informational English reading passage for a learner. Return JSON only with exact keys: texto (the reading passage, in English, 180-260 words), titulo (short title), nivel (CEFR level), vocabulario (array of 5 objects with keys 'palabra' and 'significado', useful vocabulary words with brief English definitions).",
            "Create 180-260 words about a real-world topic. Do not include questions or Spanish translation in the passage itself.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar la lectura: {exc}", 500)


LISTENING_LIBRARY = [
    {"id": "daily_conv", "title": "Daily Conversations", "level": "beginner", "topic": "a casual daily conversation between friends"},
    {"id": "restaurant", "title": "At the Restaurant", "level": "intermediate", "topic": "ordering food at a restaurant"},
    {"id": "airport", "title": "At the Airport", "level": "intermediate", "topic": "checking in and going through security at an airport"},
    {"id": "meeting_people", "title": "Meeting New People", "level": "beginner", "topic": "introducing yourself to someone new"},
    {"id": "job_interview", "title": "Job Interview", "level": "advanced", "topic": "answering a question in a job interview"},
    {"id": "business_meeting", "title": "Business Meeting", "level": "advanced", "topic": "a short update given during a business meeting"},
]


def get_listening_entry(entry_id):
    return next((x for x in LISTENING_LIBRARY if x["id"] == entry_id), None)


@app.get("/api/listening/library")
def listening_library():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    return jsonify({"ok": True, "items": [
        {"id": x["id"], "title": x["title"], "level": x["level"]}
        for x in LISTENING_LIBRARY
    ]})


@app.get("/api/listening/library/<entry_id>")
def listening_library_item(entry_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    entry = get_listening_entry(entry_id)
    if not entry:
        return json_error("Audio no encontrado.", 404)
    try:
        data = ai_json(
            "Create an English dictation sentence for a learner. Return JSON only with exact keys: texto (the sentence, in English, 12-22 words), nivel (CEFR level).",
            f"Create one natural sentence of 12-22 words about {entry['topic']}, at a {entry['level']} level.",
        )
        data["entry_id"] = entry_id
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el audio: {exc}", 500)


@app.get("/nuevo-dictado")
def new_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an English dictation sentence for an intermediate learner. Return JSON only with exact keys: texto (the sentence, in English, 12-22 words), nivel (CEFR level).",
            "Create one natural sentence of 12-22 words.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el dictado: {exc}", 500)


@app.post("/analizar-audio-real")
def analyze_real_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    upload = request.files.get("audio")
    reference = (request.form.get("frase_esperada") or request.form.get("reference") or "").strip()
    mode = (request.form.get("modo") or "").strip()
    topic = (request.form.get("topic") or "").strip()
    lp_unit_code = (request.form.get("unit_code") or "").strip()
    lp_topic_id = (request.form.get("topic_id") or "").strip()
    fast = (request.form.get("fast") or "").strip() in ("1", "true")
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        raw_result = assess_pronunciation(wav_path, reference or None)
        payload = build_pron_payload(raw_result)
        payload["weak_sounds"] = weak_sounds_from_payload(payload)
        if payload["transcript"] and not fast:
            try:
                coach = ai_json(
                    "You are a supportive English pronunciation coach. Return concise JSON with keys 'consejos' (array of 3 short tips, in Spanish) and 'comentario' (short encouraging comment, in Spanish).",
                    f"Transcript: {payload['transcript']}\nReference: {reference}\nScores: {json.dumps(payload, ensure_ascii=False)}\nGive 3 actionable tips and a short encouraging comment, all in Spanish.",
                    temperature=0.4,
                )
                payload["coach"] = coach
            except Exception as exc:
                print(f"[AI COACH] {exc}")
            if mode == "habla_libre":
                try:
                    content = ai_json(
                        "You grade the content of unscripted spoken English. Return JSON only with exact keys: grammar_score (0-100 number), vocabulary_score (0-100 number).",
                        f"Topic: {topic}\nTranscript: {payload['transcript']}\nGrade grammar_score and vocabulary_score.",
                        temperature=0.3,
                    )
                    payload["content_assessment"] = content
                    payload["gramatica"] = content.get("grammar_score")
                    payload["vocabulario"] = content.get("vocabulary_score")
                except Exception as exc:
                    print(f"[CONTENT ASSESSMENT] {exc}")
        save_history("historial_pronunciacion", user.id, {
            "frase_esperada": reference,
            "puntuacion_global": payload["puntuacion_global"],
            "precision_fonemas": payload["precision"],
            "fluidez": payload["fluidez"],
            "completitud": payload["completitud"],
            "detalles_json": payload,
        })
        if not fast:
            award_xp(user.id, 15)
            lp_result = record_learning_progress(user.id, lp_unit_code, lp_topic_id, "pronunciation", payload["puntuacion_global"])
            if lp_result:
                payload["learning_path"] = lp_result
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        return json_error(f"No se pudo analizar el audio: {exc}", 500)
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


@app.post("/api/assess-reading")
def assess_reading_audio():
    return analyze_real_audio()


@app.post("/api/assess-unscripted")
def assess_unscripted_audio():
    return analyze_real_audio()


WRITING_LEVEL_LABELS = {
    "easy": "A2 beginner-friendly",
    "intermediate": "B1-B2 intermediate",
    "advanced": "C1 advanced",
}


@app.get("/api/writing/challenge")
def writing_challenge():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    nivel = (request.args.get("nivel") or "intermediate").strip().lower()
    if nivel not in WRITING_LEVEL_LABELS:
        nivel = "intermediate"
    try:
        data = ai_json(
            "You create short, engaging English writing challenges/prompts for language learners. Return JSON only with exact key: prompt (one or two sentences, in English, appropriate for the requested level).",
            f"Create a writing challenge for a {WRITING_LEVEL_LABELS[nivel]} learner. Make it concrete and specific, not generic.",
        )
        return jsonify({"ok": True, "prompt": data.get("prompt"), "nivel": nivel})
    except Exception as exc:
        return json_error(f"No se pudo generar el reto: {exc}", 500)


@app.post("/analizar-escritura")
def analyze_writing():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    text = (body.get("texto") or body.get("text") or "").strip()[:4000]
    lp_unit_code = (body.get("unit_code") or "").strip()
    lp_topic_id = (body.get("topic_id") or "").strip()
    if not text:
        return json_error("Escribe algo antes de evaluar.")
    try:
        data = ai_json(
            "You are an expert but encouraging English writing teacher. Return JSON only with exact keys: puntuacion (0-100 number), gramatica (0-100 number), vocabulario (0-100 number), coherencia (0-100 number), resumen (short summary in Spanish), correcciones (array of short strings in Spanish describing each error and its correction), version_mejorada (corrected version of the text, in English).",
            f"Analyze this learner text:\n{text}",
            temperature=0.3,
        )
        save_history("historial_escritura", user.id, {
            "texto": text,
            "calificacion": data.get("puntuacion"),
            "gramatica": data.get("gramatica"),
            "vocabulario": data.get("vocabulario"),
            "coherencia": data.get("coherencia"),
            "resumen": data.get("resumen"),
            "version_mejorada": data.get("version_mejorada"),
        })
        award_xp(user.id, 20)
        lp_result = record_learning_progress(user.id, lp_unit_code, lp_topic_id, "writing", data.get("puntuacion"))
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el texto: {exc}", 500)


@app.post("/evaluar-lectura")
def evaluate_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    passage = (body.get("texto_original") or body.get("passage") or "").strip()[:6000]
    answer = (body.get("respuesta") or body.get("answer") or "").strip()[:3000]
    if not passage or not answer:
        return json_error("Faltan la lectura o tu respuesta.")
    try:
        data = ai_json(
            "You evaluate English reading comprehension. Return JSON only and be constructive, with exact keys: puntuacion (0-100 overall score), idea_principal (0-100, how well the main idea was understood), detalles (0-100, how well supporting details were understood), vocabulario (0-100, vocabulary usage), claridad (0-100, clarity of the learner's English), resumen (short summary in Spanish), aciertos (array of short strings in Spanish, what was understood correctly), mejoras (array of short strings in Spanish, missed ideas or things to improve), vocabulario_sugerido (array of 3-5 objects with keys 'palabra' and 'significado', useful vocabulary from the passage).",
            f"Passage:\n{passage}\n\nLearner's explanation in English:\n{answer}",
            temperature=0.3,
        )
        data.setdefault("precision", data.get("idea_principal"))
        data.setdefault("calidad_ingles", data.get("claridad"))
        save_history("historial_lectura", user.id, {
            "titulo": passage[:80],
            "calificacion": data.get("puntuacion"),
            "idea_principal": data.get("idea_principal"),
            "detalles": data.get("detalles"),
            "vocabulario": data.get("vocabulario"),
            "claridad": data.get("claridad"),
            "respuesta": answer,
        })
        award_xp(user.id, 20)
        lp_result = record_learning_progress(
            user.id,
            (body.get("unit_code") or "").strip(),
            (body.get("topic_id") or "").strip(),
            "reading",
            data.get("puntuacion"),
        )
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar la lectura: {exc}", 500)


@app.post("/evaluar-dictado")
def evaluate_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    expected = (body.get("texto_original") or body.get("expected") or "").strip()[:2000]
    answer = (body.get("respuesta") or body.get("answer") or "").strip()[:2000]
    if not expected or not answer:
        return json_error("Faltan el texto esperado o tu respuesta.")
    try:
        data = ai_json(
            "You are an English dictation teacher. Return JSON only with exact keys: puntuacion (0-100 number), palabras_correctas (integer count of correctly transcribed words), diferencias (integer count of incorrect/missing words), nivel (CEFR level as a short string), feedback (short feedback in Spanish with 2-3 brief tips).",
            f"Expected sentence:\n{expected}\n\nLearner transcription:\n{answer}",
            temperature=0.2,
        )
        save_history("historial_dictado", user.id, {
            "texto_esperado": expected,
            "respuesta": answer,
            "calificacion": data.get("puntuacion"),
            "palabras_correctas": data.get("palabras_correctas"),
            "diferencias": data.get("diferencias"),
            "nivel": data.get("nivel"),
        })
        award_xp(user.id, 15)
        lp_result = record_learning_progress(
            user.id,
            (body.get("unit_code") or "").strip(),
            (body.get("topic_id") or "").strip(),
            "dictado",
            data.get("puntuacion"),
        )
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el dictado: {exc}", 500)


def estimate_level(user_id):
    """Estima el nivel CEFR del alumno con base en el promedio de sus calificaciones recientes."""
    client = supabase_admin or supabase
    if not client:
        return None
    scores = []
    for table, col in [
        ("historial_escritura", "calificacion"),
        ("historial_lectura", "calificacion"),
        ("historial_dictado", "calificacion"),
        ("historial_pronunciacion", "puntuacion_global"),
    ]:
        try:
            rows = (
                client.table(table)
                .select(col)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ).data or []
            scores.extend(r[col] for r in rows if r.get(col) is not None)
        except Exception as exc:
            print(f"[LEVEL:{table}] {exc}")
    if not scores:
        try:
            profile = client.table("profiles").select("cefr_level").eq("id", user_id).maybe_single().execute()
            self_level = (profile.data or {}).get("cefr_level")
            return {"beginner": "A1", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(self_level)
        except Exception as exc:
            print(f"[LEVEL:self-reported] {exc}")
            return None
    avg = sum(scores) / len(scores)
    if avg >= 90:
        return "C1-C2"
    if avg >= 75:
        return "B2"
    if avg >= 60:
        return "B1"
    if avg >= 40:
        return "A2"
    return "A1"


def recent_tutor_context(user_id, limit=6):
    """Trae un resumen breve de conversaciones anteriores con el tutor, para darle memoria entre sesiones."""
    client = supabase_admin or supabase
    if not client:
        return ""
    try:
        rows = (
            client.table("historial_tutor")
            .select("mensaje_usuario,respuesta_tutor,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data or []
    except Exception as exc:
        print(f"[TUTOR CONTEXT] {exc}")
        return ""
    if not rows:
        return ""
    rows.reverse()
    lines = [f"- Student said: \"{r['mensaje_usuario'][:150]}\" | You replied: \"{r['respuesta_tutor'][:150]}\"" for r in rows]
    return "Summary of earlier sessions with this student (for continuity, do not repeat verbatim):\n" + "\n".join(lines)


@app.post("/api/transcribir-audio")
def transcribe_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    upload = request.files.get("audio")
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        config = speech_config()
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
        result = recognizer.recognize_once()
        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return jsonify({"ok": True, "texto": ""})
        return jsonify({"ok": True, "texto": result.text})
    except Exception as exc:
        return json_error(f"No se pudo transcribir el audio: {exc}", 500)
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


@app.post("/api/resumen-llamada")
def call_summary():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    history = body.get("history") or []
    transcript_lines = []
    for item in history:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            speaker = "Student" if role == "user" else "Tutor"
            transcript_lines.append(f"{speaker}: {content.strip()}")
    if not transcript_lines:
        return json_error("No hay conversación para resumir.")

    try:
        data = ai_json(
            "You are an English teacher reviewing a call-practice transcript between a student and their AI tutor. Return JSON only, in Spanish (except the numeric keys), with exact keys: puntuacion_general (0-100 overall speaking score), fluidez (0-100), gramatica (0-100), vocabulario (0-100), pronunciacion_estimada (0-100, your best estimate of likely pronunciation quality based on word choice and phrasing patterns in the transcript), resumen_general (2-3 sentences), fortalezas (array of short strings), errores_comunes (array of short strings describing recurring mistakes, in Spanish, with a brief English example each), vocabulario_recomendado (array of 3-6 objects with keys 'palabra' and 'significado'), siguiente_paso (1-2 sentences suggesting what to practice next).",
            "\n".join(transcript_lines),
            temperature=0.3,
        )
        save_history("historial_tutor", user.id, {
            "mensaje_usuario": "[Resumen de llamada]",
            "respuesta_tutor": json.dumps(data, ensure_ascii=False),
        })
        award_xp(user.id, 25)
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el resumen: {exc}", 500)


def notify_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5,
        )
    except Exception as exc:
        print(f"[TELEGRAM] {exc}")


@app.post("/api/soporte")
def soporte():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    tipo = (body.get("tipo") or "otro").strip()
    mensaje = (body.get("mensaje") or "").strip()
    if not mensaje:
        return json_error("Escribe tu mensaje antes de enviar.")

    save_history("soporte_mensajes", user.id, {
        "email": user.email,
        "tipo": tipo,
        "mensaje": mensaje,
    })
    notify_telegram(f"🛟 Nuevo mensaje de soporte ({tipo})\nDe: {user.email}\n\n{mensaje}")
    return jsonify({"ok": True})


# =============================================================================
# PANEL DE ADMINISTRACIÓN
# Todos los números salen de tus tablas reales. Si algo no se puede leer, el panel
# lo avisa en "warnings" en lugar de mostrar un 0 engañoso.
# =============================================================================
SERVER_STARTED = time.time()
PRICE_MXN = int(env("PRICE_MXN", "79") or 79)
try:
    LOCAL_TZ = ZoneInfo(env("APP_TIMEZONE", "America/Mexico_City"))
except Exception:
    LOCAL_TZ = timezone.utc

# (tipo, tabla, columna de calificación, columna de vista previa)
ACTIVITY_TABLES = [
    ("pronunciacion", "historial_pronunciacion", "puntuacion_global", "frase_esperada"),
    ("escritura", "historial_escritura", "calificacion", "texto"),
    ("lectura", "historial_lectura", "calificacion", "titulo"),
    ("dictado", "historial_dictado", "calificacion", "texto_esperado"),
    ("tutor", "historial_tutor", None, "mensaje_usuario"),
]
CALL_MARK = "[Resumen de llamada]"
LOG_TABLE = "admin_acciones"   # registro de cada cambio de acceso (ver admin_acciones.sql)


def _parse_ts(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        s = str(v).replace("Z", "+00:00").replace(" ", "T", 1)
        s = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], s)
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _iso(dt):
    return dt.isoformat() if dt else None


def _day(dt):
    return dt.astimezone(LOCAL_TZ).date()


def admin_guard():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return None, json_error(error[0], error[1])
    if not is_admin_user(user):
        return None, json_error("No autorizado.", 403)
    return user, None


def _fetch_all(client, table, columns, order_col="created_at", max_rows=20000):
    rows, start, page = [], 0, 1000
    while len(rows) < max_rows:
        q = client.table(table).select(columns)
        if order_col:
            q = q.order(order_col, desc=True)
        data = q.range(start, start + page - 1).execute().data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return rows


def _list_auth_users(client):
    out, page = [], 1
    while page <= 30:
        batch = client.auth.admin.list_users(page=page, per_page=1000)
        items = list(batch) if isinstance(batch, (list, tuple)) else list(getattr(batch, "users", None) or [])
        out.extend(items)
        if len(items) < 1000:
            break
        page += 1
    return out


def _streak(days, today):
    if today in days:
        cur = today
    elif (today - timedelta(days=1)) in days:
        cur = today - timedelta(days=1)
    else:
        return 0
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def _build_admin_dataset():
    client = supabase_admin or supabase
    if not client:
        raise RuntimeError("Supabase no está configurado en el servidor.")
    warnings = []
    if not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == SUPABASE_KEY:
        warnings.append(
            "Falta la clave service_role (variable SUPABASE_SERVICE_KEY en Render). Sin ella Supabase oculta "
            "los datos de otros usuarios y las cifras salen incompletas."
        )
    now = datetime.now(timezone.utc)

    auth_users = {}
    try:
        for u in _list_auth_users(client):
            uid = str(getattr(u, "id", "") or "")
            if uid:
                auth_users[uid] = {
                    "email": getattr(u, "email", None) or "",
                    "created_at": _parse_ts(getattr(u, "created_at", None)),
                    "last_sign_in": _parse_ts(getattr(u, "last_sign_in_at", None)),
                    "confirmed": bool(getattr(u, "email_confirmed_at", None) or getattr(u, "confirmed_at", None)),
                }
    except Exception as exc:
        warnings.append(f"No se pudo leer la lista de cuentas de acceso ({exc}); se usan solo los perfiles.")

    profiles, ok, err = {}, False, None
    for cols in (
        "id,email,username,is_subscribed,trial_ends_at,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems",
        "id,username,is_subscribed,trial_ends_at,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems",
        "id,is_subscribed,trial_ends_at",
    ):
        try:
            rows = _fetch_all(client, "profiles", cols, order_col=None)
            profiles = {str(r["id"]): r for r in rows if r.get("id")}
            ok = True
            break
        except Exception as exc:
            err = exc
    if not ok:
        warnings.append(f"No se pudo leer la tabla de perfiles ({err}). Estados de pago y prueba no disponibles.")

    events = []
    for tipo, table, score_col, _prev in ACTIVITY_TABLES:
        cols = "user_id,created_at" + (f",{score_col}" if score_col else "") + (",mensaje_usuario" if table == "historial_tutor" else "")
        try:
            rows = _fetch_all(client, table, cols)
        except Exception as exc:
            warnings.append(f"No se pudo leer {table} ({exc}); la actividad de ese tipo sale incompleta.")
            continue
        for r in rows:
            ts, uid = _parse_ts(r.get("created_at")), r.get("user_id")
            if not ts or not uid:
                continue
            t = tipo
            if table == "historial_tutor" and str(r.get("mensaje_usuario") or "").startswith(CALL_MARK):
                t = "llamada"
            sc = r.get(score_col) if score_col else None
            try:
                sc = float(sc) if sc is not None else None
            except (TypeError, ValueError):
                sc = None
            events.append({"uid": str(uid), "tipo": t, "ts": ts, "score": sc})
    events.sort(key=lambda e: e["ts"], reverse=True)

    vocab = defaultdict(int)
    try:
        for r in _fetch_all(client, "vocabulario_usuario", "user_id", order_col=None):
            vocab[str(r.get("user_id"))] += 1
    except Exception as exc:
        warnings.append(f"No se pudo leer vocabulario_usuario ({exc}).")

    # Registro de acciones del admin (si la tabla existe): permite saber cuándo vence cada pago.
    log_ok, ult_accion, ult_pago = True, {}, {}
    try:
        for r in _fetch_all(client, LOG_TABLE, "user_id,created_at,accion,vence_at", max_rows=5000):
            uid = str(r.get("user_id") or "")
            if uid and uid not in ult_accion:          # las filas vienen de la más reciente a la más antigua
                ult_accion[uid] = r.get("accion")
                ult_pago[uid] = _parse_ts(r.get("vence_at"))
    except Exception:
        log_ok = False

    by_user = defaultdict(list)
    for e in events:
        by_user[e["uid"]].append(e)

    today = _day(now)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    users = {}
    for uid in set(auth_users) | set(profiles):
        a, p = auth_users.get(uid, {}), profiles.get(uid, {})
        email = a.get("email") or p.get("email") or ""
        trial_end = _parse_ts(p.get("trial_ends_at"))
        dias = None
        if p.get("is_subscribed"):
            estado = "pagado"
        elif trial_end and trial_end > now:
            estado = "prueba"
            dias = max(1, round((trial_end - now).total_seconds() / 86400))
        else:
            estado = "vencido"
        evs = by_user.get(uid, [])
        vence_pago, dias_renovar = None, None
        if estado == "pagado" and ult_accion.get(uid) in ("activar", "renovar") and ult_pago.get(uid):
            vence_pago = ult_pago[uid]
            dias_renovar = math.ceil((vence_pago - now).total_seconds() / 86400)
        scores = [e["score"] for e in evs if e["score"] is not None]
        tipos = defaultdict(int)
        for e in evs:
            tipos[e["tipo"]] += 1
        users[uid] = {
            "id": uid, "email": email, "username": p.get("username") or "",
            "es_admin": email.lower() in ADMIN_EMAILS,
            "estado": estado, "dias_restantes": dias, "trial_ends_at": trial_end,
            "created_at": a.get("created_at"), "last_sign_in": a.get("last_sign_in"),
            "confirmado": a.get("confirmed"),
            "onboarded": bool(p.get("onboarded")), "cefr_level": p.get("cefr_level") or "",
            "learning_goal": p.get("learning_goal") or "", "daily_goal_minutes": p.get("daily_goal_minutes"),
            "gems": p.get("gems") or 0,
            "total": len(evs), "act_7d": sum(1 for e in evs if e["ts"] >= d7), "act_30d": sum(1 for e in evs if e["ts"] >= d30),
            "last_activity": evs[0]["ts"] if evs else None,
            "prom_score": round(sum(scores) / len(scores), 1) if scores else None,
            "tipos": dict(tipos), "palabras": vocab.get(uid, 0),
            "racha": _streak({_day(e["ts"]) for e in evs}, today),
            "vence_pago": vence_pago, "dias_renovar": dias_renovar,
        }
    return {"now": now, "users": users, "events": events, "warnings": warnings, "log_ok": log_ok}


_admin_cache = {"t": 0.0, "data": None}
_admin_lock = threading.Lock()


def admin_dataset(force=False):
    with _admin_lock:
        if not force and _admin_cache["data"] and time.time() - _admin_cache["t"] < 45:
            return _admin_cache["data"]
        data = _build_admin_dataset()
        _admin_cache["t"], _admin_cache["data"] = time.time(), data
        return data


def _user_json(u):
    return {
        "id": u["id"], "email": u["email"], "username": u["username"], "es_admin": u["es_admin"],
        "estado": u["estado"], "dias_restantes": u["dias_restantes"], "trial_ends_at": _iso(u["trial_ends_at"]),
        "created_at": _iso(u["created_at"]), "last_sign_in": _iso(u["last_sign_in"]), "confirmado": u["confirmado"],
        "onboarded": u["onboarded"], "cefr_level": u["cefr_level"], "learning_goal": u["learning_goal"],
        "daily_goal_minutes": u["daily_goal_minutes"], "gems": u["gems"],
        "total": u["total"], "act_7d": u["act_7d"], "act_30d": u["act_30d"],
        "last_activity": _iso(u["last_activity"]), "prom_score": u["prom_score"],
        "tipos": u["tipos"], "palabras": u["palabras"], "racha": u["racha"],
        "vence_pago": _iso(u["vence_pago"]), "dias_renovar": u["dias_renovar"],
    }


def _soporte_resumen(client, now):
    try:
        try:
            rows = client.table("soporte_mensajes").select("*").order("created_at", desc=True).limit(200).execute().data or []
        except Exception:
            rows = client.table("soporte_mensajes").select("*").limit(200).execute().data or []
    except Exception:
        return None
    sem = now - timedelta(days=7)
    rec = [r for r in rows if (_parse_ts(r.get("created_at")) or now) >= sem]
    return {
        "total_7d": len(rec),
        "pago_7d": sum(1 for r in rec if str(r.get("tipo") or "") == "pago"),
        "recientes": [{"email": r.get("email"), "tipo": r.get("tipo"), "fecha": r.get("created_at"),
                       "mensaje": str(r.get("mensaje") or "")[:140]} for r in rec[:5]],
    }


def _admin_overview(ds):
    now, events = ds["now"], ds["events"]
    users = [u for u in ds["users"].values() if not u["es_admin"]]
    ids = {u["id"] for u in users}
    events = [e for e in events if e["uid"] in ids]
    h15, d1, d7, d30 = now - timedelta(minutes=15), now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)

    def uniq(since):
        return len({e["uid"] for e in events if e["ts"] >= since})

    def nuevos(since):
        return sum(1 for u in users if u["created_at"] and u["created_at"] >= since)

    estados = {"pagado": 0, "prueba": 0, "vencido": 0}
    for u in users:
        estados[u["estado"]] += 1
    por_vencer = sorted(
        [u for u in users if u["estado"] == "prueba" and u["dias_restantes"] is not None and u["dias_restantes"] <= 3],
        key=lambda u: u["dias_restantes"],
    )
    today = _day(now)
    dias = [today - timedelta(days=i) for i in range(13, -1, -1)]
    ev_dia, us_dia, reg_dia = defaultdict(int), defaultdict(set), defaultdict(int)
    for e in events:
        if e["ts"] >= now - timedelta(days=16):
            d = _day(e["ts"])
            ev_dia[d] += 1
            us_dia[d].add(e["uid"])
    for u in users:
        if u["created_at"]:
            reg_dia[_day(u["created_at"])] += 1
    serie = [{"fecha": d.isoformat(), "eventos": ev_dia[d], "usuarios": len(us_dia[d]), "registros": reg_dia[d]} for d in dias]

    t7, t24 = defaultdict(int), defaultdict(int)
    for e in events:
        if e["ts"] >= d7:
            t7[e["tipo"]] += 1
        if e["ts"] >= d1:
            t24[e["tipo"]] += 1

    con_act = sum(1 for u in users if u["total"] > 0)
    elegibles = [u for u in users if u["created_at"] and u["created_at"] <= d7]
    retenidos = sum(1 for u in elegibles if u["act_7d"] > 0)
    niveles, objetivos = defaultdict(int), defaultdict(int)
    for u in users:
        niveles[u["cefr_level"] or "sin definir"] += 1
        objetivos[u["learning_goal"] or "sin definir"] += 1
    top = sorted([u for u in users if u["act_7d"] > 0], key=lambda u: (-u["act_7d"], -u["total"]))[:10]
    sin_act = [u for u in users if u["total"] == 0 and u["created_at"] and u["created_at"] <= now - timedelta(days=3)]

    pagados = [u for u in users if u["estado"] == "pagado"]
    por_renovar = sorted([u for u in pagados if u["dias_renovar"] is not None and u["dias_renovar"] <= 5],
                         key=lambda u: u["dias_renovar"])
    return {
        "ok": True, "generado": _iso(now), "precio_mxn": PRICE_MXN,
        "pagos": {
            "registro_activo": ds.get("log_ok", False),
            "por_renovar": [{"id": u["id"], "email": u["email"], "dias": u["dias_renovar"]} for u in por_renovar[:20]],
            "sin_fecha": sum(1 for u in pagados if u["dias_renovar"] is None),
        },
        "soporte": _soporte_resumen(supabase_admin or supabase, now),
        "usuarios": {
            "total": len(users), "confirmados": sum(1 for u in users if u["confirmado"]),
            "nuevos_24h": nuevos(d1), "nuevos_7d": nuevos(d7), "nuevos_30d": nuevos(d30),
        },
        "actividad": {
            "ahora_15min": uniq(h15), "activos_24h": uniq(d1), "activos_7d": uniq(d7), "activos_30d": uniq(d30),
            "eventos_24h": sum(t24.values()), "eventos_7d": sum(t7.values()),
        },
        "estados": estados, "mrr_estimado": estados["pagado"] * PRICE_MXN,
        "por_vencer": [{"id": u["id"], "email": u["email"], "dias": u["dias_restantes"]} for u in por_vencer[:15]],
        "embudo": [
            {"paso": "Registrados", "n": len(users)},
            {"paso": "Correo confirmado", "n": sum(1 for u in users if u["confirmado"])},
            {"paso": "Terminaron el onboarding", "n": sum(1 for u in users if u["onboarded"])},
            {"paso": "Hicieron ≥1 actividad", "n": con_act},
            {"paso": "Pagan", "n": estados["pagado"]},
        ],
        "retencion_7d": {"elegibles": len(elegibles), "retenidos": retenidos,
                         "pct": round(retenidos / len(elegibles) * 100) if elegibles else None},
        "sin_actividad_3d": len(sin_act),
        "serie_14d": serie, "tipos_7d": dict(t7), "tipos_24h": dict(t24),
        "niveles": dict(niveles), "objetivos": dict(objetivos),
        "top_7d": [{"id": u["id"], "email": u["email"], "act_7d": u["act_7d"], "total": u["total"]} for u in top],
        "warnings": ds["warnings"],
        "nota": "Las cifras no incluyen cuentas de administrador. 'Activos' = usuarios con alguna práctica registrada en esa ventana.",
    }


def _admin_users(ds, q, estado, orden, limit, offset):
    rows = list(ds["users"].values())
    q = (q or "").strip().lower()
    if q:
        rows = [u for u in rows if q in u["email"].lower() or q in (u["username"] or "").lower() or q == u["id"]]
    if estado in ("pagado", "prueba", "vencido"):
        rows = [u for u in rows if u["estado"] == estado]
    elif estado == "inactivo":
        rows = [u for u in rows if u["total"] == 0]
    elif estado == "por_renovar":
        rows = [u for u in rows if u["estado"] == "pagado" and u["dias_renovar"] is not None and u["dias_renovar"] <= 5]
    elif estado == "por_vencer":
        rows = [u for u in rows if u["estado"] == "prueba" and u["dias_restantes"] is not None and u["dias_restantes"] <= 3]
    floor = datetime.min.replace(tzinfo=timezone.utc)
    if orden == "actividad":
        rows.sort(key=lambda u: (-u["act_7d"], -u["total"]))
    elif orden == "registro":
        rows.sort(key=lambda u: u["created_at"] or floor, reverse=True)
    elif orden == "vence":
        rows.sort(key=lambda u: (u["dias_restantes"] is None, u["dias_restantes"] or 0))
    else:
        rows.sort(key=lambda u: u["last_activity"] or u["last_sign_in"] or u["created_at"] or floor, reverse=True)
    return len(rows), [_user_json(u) for u in rows[offset:offset + limit]]


def _recent_events_for(client, uid, per_table=12):
    out, warns = [], []
    for tipo, table, score_col, prev_col in ACTIVITY_TABLES:
        cols = "created_at," + prev_col + (f",{score_col}" if score_col else "")
        try:
            rows = client.table(table).select(cols).eq("user_id", uid).order("created_at", desc=True).limit(per_table).execute().data or []
        except Exception as exc:
            warns.append(f"{table}: {exc}")
            continue
        for r in rows:
            prev = str(r.get(prev_col) or "")
            t = "llamada" if table == "historial_tutor" and prev.startswith(CALL_MARK) else tipo
            sc = r.get(score_col) if score_col else None
            out.append({"tipo": t, "fecha": r.get("created_at"), "score": sc, "detalle": prev[:140]})
    out.sort(key=lambda e: e.get("fecha") or "", reverse=True)
    return out[:30], warns


@app.get("/api/admin/resumen")
def admin_resumen():
    _u, err = admin_guard()
    if err:
        return err
    try:
        return jsonify(_admin_overview(admin_dataset(force=request.args.get("fresh") == "1")))
    except Exception as exc:
        print(f"[ADMIN resumen] {exc}")
        return json_error(f"No se pudo calcular el resumen: {exc}", 500)


@app.get("/api/admin/usuarios")
def admin_usuarios():
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset(force=request.args.get("fresh") == "1")
        limit = max(1, min(int(request.args.get("limit", 30) or 30), 100))
        offset = max(0, int(request.args.get("offset", 0) or 0))
        total, rows = _admin_users(ds, request.args.get("q"), request.args.get("estado", "todos"),
                                   request.args.get("orden", "reciente"), limit, offset)
        return jsonify({"ok": True, "total": total, "usuarios": rows, "warnings": ds["warnings"]})
    except Exception as exc:
        print(f"[ADMIN usuarios] {exc}")
        return json_error(f"No se pudo cargar la lista de usuarios: {exc}", 500)


@app.get("/api/admin/usuario/<uid>")
def admin_usuario(uid):
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset()
        u = ds["users"].get(uid)
        if not u:
            return json_error("Usuario no encontrado.", 404)
        client = supabase_admin or supabase
        recientes, warns = _recent_events_for(client, uid)
        palabras = []
        try:
            palabras = client.table("vocabulario_usuario").select("palabra,significado").eq("user_id", uid).limit(12).execute().data or []
        except Exception as exc:
            warns.append(f"vocabulario_usuario: {exc}")
        soporte = []
        if u["email"]:
            try:
                soporte = client.table("soporte_mensajes").select("*").eq("email", u["email"]).limit(10).execute().data or []
            except Exception as exc:
                warns.append(f"soporte_mensajes: {exc}")
        acciones = []
        if ds.get("log_ok"):
            try:
                acciones = (client.table(LOG_TABLE).select("created_at,accion,dias,vence_at,nota,admin_email")
                            .eq("user_id", uid).order("created_at", desc=True).limit(10).execute().data or [])
            except Exception as exc:
                warns.append(f"{LOG_TABLE}: {exc}")
        return jsonify({"ok": True, "usuario": _user_json(u), "recientes": recientes, "palabras": palabras,
                        "soporte": soporte, "acciones": acciones, "registro_activo": ds.get("log_ok", False),
                        "warnings": warns})
    except Exception as exc:
        print(f"[ADMIN usuario] {exc}")
        return json_error(f"No se pudo cargar el usuario: {exc}", 500)


@app.post("/api/admin/usuario/<uid>/acceso")
def admin_acceso(uid):
    """Activa, renueva o quita el acceso de pago, o extiende la prueba. Siempre deja registro."""
    admin, err = admin_guard()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if body.get("confirmar") is not True:
        return json_error("Falta confirmar la acción.", 400)
    accion = (body.get("accion") or "").strip()
    if accion not in ("activar", "renovar", "desactivar", "extender_prueba"):
        return json_error("Acción no válida.", 400)
    try:
        dias = int(body.get("dias") or 30)
    except (TypeError, ValueError):
        dias = 30
    dias = max(1, min(dias, 365))
    nota = str(body.get("nota") or "")[:200]
    client = supabase_admin or supabase
    if not client or not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == SUPABASE_KEY:
        return json_error("Falta la clave service_role en el servidor (SUPABASE_SERVICE_KEY): sin ella no se pueden cambiar accesos.", 500)
    try:
        res = client.table("profiles").select("id,is_subscribed,trial_ends_at").eq("id", uid).limit(1).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return json_error("Ese usuario no tiene perfil en la base de datos.", 404)
        perfil = rows[0]
        now = datetime.now(timezone.utc)
        vence, payload = None, {}
        if accion in ("activar", "renovar"):
            base = now
            prev = (admin_dataset().get("users", {}).get(uid) or {}).get("vence_pago")
            if accion == "renovar" and prev and prev > now:
                base = prev                      # renovar a tiempo suma días al vencimiento actual
            vence = base + timedelta(days=dias)
            payload = {"is_subscribed": True}
        elif accion == "desactivar":
            payload = {"is_subscribed": False}
        else:
            actual = _parse_ts(perfil.get("trial_ends_at"))
            base = actual if actual and actual > now else now
            payload = {"trial_ends_at": (base + timedelta(days=dias)).isoformat()}
        upd = client.table("profiles").update(payload).eq("id", uid).execute()
        if not (getattr(upd, "data", None) or []):
            return json_error("No se pudo actualizar el perfil (no se modificó ninguna fila).", 500)

        correo = (admin_dataset().get("users", {}).get(uid) or {}).get("email") or ""
        aviso = None
        try:
            client.table(LOG_TABLE).insert({
                "admin_email": (getattr(admin, "email", "") or "").lower(), "user_id": uid, "user_email": correo,
                "accion": accion, "dias": dias if accion != "desactivar" else None,
                "vence_at": vence.isoformat() if vence else None, "nota": nota or None,
            }).execute()
        except Exception as exc:
            aviso = ("El cambio se aplicó, pero no se pudo guardar el registro de la acción. "
                     f"Crea la tabla {LOG_TABLE} con admin_acciones.sql ({exc}).")
        try:
            notify_telegram(f"🔧 Admin {getattr(admin, 'email', '')}: {accion} → {correo or uid}"
                            + (f" ({dias} días)" if accion != "desactivar" else ""))
        except Exception:
            pass
        ds = admin_dataset(force=True)
        u = ds["users"].get(uid)
        textos = {"activar": f"Acceso de pago activado por {dias} días.", "renovar": f"Pago renovado: +{dias} días.",
                  "desactivar": "Acceso de pago quitado.", "extender_prueba": f"Prueba extendida +{dias} días."}
        return jsonify({"ok": True, "mensaje": textos[accion], "usuario": _user_json(u) if u else None, "aviso": aviso})
    except Exception as exc:
        print(f"[ADMIN acceso] {exc}")
        return json_error(f"No se pudo aplicar el cambio: {exc}", 500)


@app.get("/api/admin/actividad")
def admin_activity():
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset()
        client = supabase_admin or supabase
        tipo_f = (request.args.get("tipo") or "").strip()
        limit = max(10, min(int(request.args.get("limit", 100) or 100), 200))
        emails = {uid: u["email"] for uid, u in ds["users"].items()}
        events, warns = [], []
        for tipo, table, score_col, prev_col in ACTIVITY_TABLES:
            if tipo_f and tipo_f not in (tipo, "llamada") :
                continue
            if tipo_f and tipo_f != tipo and table != "historial_tutor":
                continue
            cols = "user_id,created_at," + prev_col + (f",{score_col}" if score_col else "")
            try:
                rows = client.table(table).select(cols).order("created_at", desc=True).limit(limit).execute().data or []
            except Exception as exc:
                warns.append(f"No se pudo leer {table}: {exc}")
                continue
            for r in rows:
                prev = str(r.get(prev_col) or "")
                t = "llamada" if table == "historial_tutor" and prev.startswith(CALL_MARK) else tipo
                if tipo_f and t != tipo_f:
                    continue
                uid = str(r.get("user_id") or "")
                events.append({"tipo": t, "uid": uid, "email": emails.get(uid) or uid[:8],
                               "fecha": r.get("created_at"), "score": r.get(score_col) if score_col else None,
                               "detalle": prev[:120]})
        events.sort(key=lambda e: e.get("fecha") or "", reverse=True)
        ov = _admin_overview(ds)
        return jsonify({"ok": True, "eventos": events[:limit], "warnings": ds["warnings"] + warns,
                        "total_usuarios": ov["usuarios"]["total"], "en_prueba": ov["estados"]["prueba"],
                        "pagados": ov["estados"]["pagado"]})
    except Exception as exc:
        print(f"[ADMIN actividad] {exc}")
        return json_error(f"No se pudo cargar la actividad: {exc}", 500)


@app.get("/api/admin/soporte")
def admin_soporte():
    _u, err = admin_guard()
    if err:
        return err
    client = supabase_admin or supabase
    try:
        try:
            rows = client.table("soporte_mensajes").select("*").order("created_at", desc=True).limit(50).execute().data or []
        except Exception:
            rows = client.table("soporte_mensajes").select("*").limit(50).execute().data or []
        return jsonify({"ok": True, "mensajes": rows})
    except Exception as exc:
        print(f"[ADMIN soporte] {exc}")
        return json_error(f"No se pudieron leer los mensajes de soporte: {exc}", 500)


@app.get("/api/admin/sistema")
def admin_sistema():
    _u, err = admin_guard()
    if err:
        return err
    checks = []
    client = supabase_admin or supabase
    service_ok = bool(SUPABASE_SERVICE_KEY) and SUPABASE_SERVICE_KEY != SUPABASE_KEY
    checks.append({"nombre": "Clave service_role de Supabase", "ok": service_ok,
                   "detalle": "Configurada." if service_ok else "NO configurada: define SUPABASE_SERVICE_KEY en Render o el panel verá datos incompletos."})
    try:
        t0 = time.time()
        client.table("profiles").select("id").limit(1).execute()
        ms = round((time.time() - t0) * 1000)
        checks.append({"nombre": "Base de datos (Supabase)", "ok": True, "detalle": f"Responde en {ms} ms."})
    except Exception as exc:
        checks.append({"nombre": "Base de datos (Supabase)", "ok": False, "detalle": f"Error: {exc}"})
    try:
        client.auth.admin.list_users(page=1, per_page=1)
        checks.append({"nombre": "Lista de cuentas de acceso", "ok": True, "detalle": "Se pueden leer correos y fechas de registro."})
    except Exception as exc:
        checks.append({"nombre": "Lista de cuentas de acceso", "ok": False, "detalle": f"Error: {exc}. Se usarán los perfiles."})
    try:
        client.table(LOG_TABLE).select("id").limit(1).execute()
        checks.append({"nombre": "Registro de pagos (tabla admin_acciones)", "ok": True,
                       "detalle": "Activa: cada cambio de acceso queda guardado y se calcula cuándo vence cada pago."})
    except Exception:
        checks.append({"nombre": "Registro de pagos (tabla admin_acciones)", "ok": False,
                       "detalle": "No existe. Los botones funcionan, pero no se sabrá cuándo vence cada pago. Ejecuta admin_acciones.sql en el SQL Editor de Supabase."})
    checks.append({"nombre": "Azure OpenAI (tutor y correcciones)", "ok": bool(ai_client),
                   "detalle": "Configurado." if ai_client else "No configurado: el tutor y las evaluaciones no funcionarán."})
    checks.append({"nombre": "Azure Speech (voz y pronunciación)", "ok": bool(AZURE_SPEECH_KEY),
                   "detalle": f"Configurado (región {AZURE_SPEECH_REGION})." if AZURE_SPEECH_KEY else "No configurado."})
    checks.append({"nombre": "Cuentas de administrador", "ok": bool(ADMIN_EMAILS),
                   "detalle": f"{len(ADMIN_EMAILS)} configurada(s)."})
    checks.append({"nombre": "Avisos por Telegram (opcional)", "ok": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
                   "detalle": "Configurado." if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else "No configurado (no es obligatorio)."})
    up = int(time.time() - SERVER_STARTED)
    with _rate_lock:
        claves = len(_rate_hits)
    with _tts_lock:
        tts = len(_tts_cache)
    return jsonify({
        "ok": True, "checks": checks,
        "servidor": {
            "encendido_desde": datetime.fromtimestamp(SERVER_STARTED, timezone.utc).isoformat(),
            "uptime_seg": up, "python": platform.python_version(), "zona_horaria": str(LOCAL_TZ),
            "precio_mxn": PRICE_MXN, "limite_ia_diario": DAILY_AI_LIMIT, "limite_general_min": GENERAL_PER_MINUTE,
            "audios_en_cache": tts, "contadores_de_limite": claves,
            "cache_panel_seg": int(time.time() - _admin_cache["t"]) if _admin_cache["data"] else None,
        },
    })


@app.post("/api/tutor")
def tutor():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    message = (body.get("mensaje") or body.get("message") or "").strip()[:1500]
    history = body.get("history") or []
    modo = (body.get("modo") or "").strip()
    categoria = (body.get("categoria") or "").strip()
    if not message:
        return json_error("Escribe o di algo al tutor.")

    safe_history = []
    for item in history[-14:]:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str):
            safe_history.append({"role": role, "content": content[:2000]})

    level = estimate_level(user.id)
    level_line = f"Estimated student level: {level} (adapt vocabulary and grammar complexity to this level)." if level else "Student level unknown yet: keep it accessible (around B1) and adjust as you learn more from their messages."
    prior_context = recent_tutor_context(user.id)

    call_line = (
        "\n\nThis is a LIVE VOICE CALL, not a text chat: reply in 1-3 short spoken sentences, "
        "no lists, no markdown, no emojis — just natural words that sound good read aloud."
        if modo == "llamada" else ""
    )
    category_lines = {
        "grammar": "\n\nFocus this session on grammar: naturally work grammar points into the conversation, invite the student to build full sentences, and be a bit more explicit (but still kind) when correcting grammar patterns.",
        "vocabulary": "\n\nFocus this session on vocabulary: introduce a couple of useful new English words naturally in context each reply, and check that the student understood them.",
        "pronunciation": "\n\nFocus this session on pronunciation: ask the student to say or type short phrases, and since you cannot hear audio, give general tips on how tricky words or sounds in their message are typically pronounced.",
        "free": "\n\nThis is free-form conversation: follow the student's lead on whatever topic they bring up.",
    }
    category_line = category_lines.get(categoria, "")

    system_prompt = (
        "You are Palanqueta, the friendly hen mascot and personal English conversation tutor at Talvo English. "
        "You can make a light, natural hen-themed joke or expression once in a while (e.g. comparing progress to 'hatching' a new skill), but never overdo it — you are a real tutor first, a character second. "
        "Your job is to have a real, engaging conversation in English — not to interrogate or lecture. "
        "Style: warm, encouraging, a little informal, like a good friend who happens to be a great teacher. Keep replies short (2-4 sentences), never a wall of text.\n\n"
        "How to correct mistakes: never list errors or break character to give a grammar lecture. "
        "Instead, use natural 'recasting' — if the student makes a mistake, weave the corrected form naturally into your own next sentence, the way a native speaker would casually rephrase, without pointing it out directly. "
        "Only explicitly flag a mistake if it is a significant, repeated pattern, and even then do it briefly and kindly, then move on.\n\n"
        "Conversation flow: always end your reply with one genuine follow-up question that keeps the conversation going and invites the student to speak more.\n\n"
        f"{level_line}\n\n"
        f"{prior_context}"
        f"{call_line}"
        f"{category_line}"
    )

    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                *safe_history,
                {"role": "user", "content": message},
            ],
            temperature=0.8,
        )
        reply = response.choices[0].message.content or "Let's keep practicing. Tell me more."
        save_history("historial_tutor", user.id, {
            "mensaje_usuario": message,
            "respuesta_tutor": reply,
        })
        return jsonify({"ok": True, "respuesta": reply})
    except Exception as exc:
        return json_error(f"El tutor no pudo responder: {exc}", 500)


@app.get("/obtener-historial")
def history():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    tables = [
        ("pronunciation", "historial_pronunciacion"),
        ("writing", "historial_escritura"),
        ("reading", "historial_lectura"),
        ("dictation", "historial_dictado"),
        ("tutor", "historial_tutor"),
    ]
    SCORE_COLUMN = {
        "pronunciation": "puntuacion_global",
        "writing": "calificacion",
        "reading": "calificacion",
        "dictation": "calificacion",
    }
    client = supabase_admin or supabase
    combined = []
    for key, table in tables:
        try:
            rows = (
                client.table(table)
                .select("*")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            ).data or []
            score_col = SCORE_COLUMN.get(key)
            for row in rows:
                row["tipo"] = key
                if score_col and row.get(score_col) is not None:
                    row["puntuacion"] = row[score_col]
            combined.extend(rows)
        except Exception as exc:
            print(f"[HISTORY READ:{table}] {exc}")
    combined.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return jsonify({"ok": True, "historial": combined[:30]})


@app.get("/api/vocabulario/diario")
def vocab_daily():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        existing = (
            client.table("vocabulario_usuario")
            .select("id,palabra,significado,ejemplo,aprendida")
            .eq("user_id", user.id)
            .eq("origen", "diario")
            .eq("fecha", today)
            .execute()
        ).data or []
        if existing:
            return jsonify({"ok": True, "palabras": existing})

        level = estimate_level(user.id) or "B1"
        data = ai_json(
            "You create a short daily English vocabulary list for a learner. Return JSON only with exact key: palabras, an array of exactly 5 objects each with keys 'palabra' (the English word), 'significado' (short definition in Spanish), 'ejemplo' (one example sentence in English using the word).",
            f"Student level: {level}. Give 5 useful, varied everyday words appropriate for this level.",
            temperature=0.6,
        )
        words = data.get("palabras", [])[:5]
        inserted = []
        for w in words:
            row = {
                "user_id": user.id,
                "palabra": w.get("palabra", ""),
                "significado": w.get("significado", ""),
                "ejemplo": w.get("ejemplo", ""),
                "origen": "diario",
                "fecha": today,
            }
            try:
                res = client.table("vocabulario_usuario").insert(row).execute()
                inserted.append((res.data or [row])[0])
            except Exception as exc:
                print(f"[VOCAB INSERT] {exc}")
                inserted.append(row)
        return jsonify({"ok": True, "palabras": inserted})
    except Exception as exc:
        return json_error(f"No se pudieron generar las palabras del día: {exc}", 500)


@app.post("/api/vocabulario/guardar")
def vocab_save():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    palabra = (body.get("palabra") or "").strip()
    if not palabra:
        return json_error("Falta la palabra.")
    save_history("vocabulario_usuario", user.id, {
        "palabra": palabra,
        "significado": (body.get("significado") or "").strip(),
        "ejemplo": (body.get("ejemplo") or "").strip(),
        "origen": body.get("origen") or "manual",
    })
    return jsonify({"ok": True})


@app.post("/api/vocabulario/marcar")
def vocab_mark():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    word_id = body.get("id")
    aprendida = bool(body.get("aprendida"))
    if not word_id:
        return json_error("Falta el identificador de la palabra.")
    client = supabase_admin or supabase
    try:
        client.table("vocabulario_usuario").update({"aprendida": aprendida}).eq("id", word_id).eq("user_id", user.id).execute()
        return jsonify({"ok": True})
    except Exception as exc:
        return json_error(f"No se pudo actualizar: {exc}", 500)


def _unit_xp_and_progress(user_id):
    client = supabase_admin or supabase
    xp = 0
    gem_unlocked = set()
    if client:
        try:
            profile = client.table("profiles").select("xp").eq("id", user_id).maybe_single().execute()
            xp = (profile.data or {}).get("xp") or 0
        except Exception as exc:
            print(f"[LEARNING PATH XP] {exc}")
        try:
            rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user_id).execute().data or []
            gem_unlocked = {r["unit_code"] for r in rows}
        except Exception as exc:
            print(f"[LEARNING PATH GEM UNLOCKS] {exc}")
    return xp, fetch_learning_progress(user_id), gem_unlocked


AVATAR_FRAMES = {
    "gold": {"name": "Gold", "price": 100, "gradient": "linear-gradient(135deg,#f5c542,#ffb37a)"},
    "fire": {"name": "Fire", "price": 80, "gradient": "linear-gradient(135deg,#ff6b4a,#ff3d6e)"},
    "ocean": {"name": "Ocean", "price": 80, "gradient": "linear-gradient(135deg,#4ad0ff,#7180ff)"},
}
UNIT_UNLOCK_PRICES = {
    "at_the_restaurant": 60, "shopping_and_money": 60, "travel_and_tourism": 60, "health_and_body": 60,
    "work_and_business": 120, "social_life": 120,
    "fluent_moves": 200, "big_ideas": 200,
}
STREAK_FREEZE_PRICE = 50


def get_wallet(client, user_id):
    profile = (
        client.table("profiles")
        .select("gems,streak_freezes,avatar_frame,owned_frames")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return profile.data or {}


@app.get("/api/shop")
def shop_catalog():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    wallet = get_wallet(client, user.id)
    gems = wallet.get("gems") or 0
    owned_frames = wallet.get("owned_frames") or []

    xp = 0
    try:
        p = client.table("profiles").select("xp").eq("id", user.id).maybe_single().execute()
        xp = (p.data or {}).get("xp") or 0
    except Exception as exc:
        print(f"[SHOP XP] {exc}")

    already_unlocked = set()
    try:
        rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user.id).execute().data or []
        already_unlocked = {r["unit_code"] for r in rows}
    except Exception as exc:
        print(f"[SHOP UNLOCKS] {exc}")

    unit_offers = []
    try:
        prof, level_rank, _prog, gems_open, sections, _nx = _path_for_user(user.id)
        closed = next((sec for sec in sections if not sec["open"]), None)
        if closed:
            for un in closed["units"]:
                price = UNIT_UNLOCK_PRICES.get(un["code"])
                if price and un["code"] not in gems_open:
                    unit_offers.append({"unit_code": un["code"], "title": un["title"], "price": price})
    except Exception as exc:
        print(f"[SHOP OFFERS] {exc}")

    frames = [{"id": k, "name": v["name"], "price": v["price"], "gradient": v["gradient"], "owned": k in owned_frames} for k, v in AVATAR_FRAMES.items()]

    return jsonify({
        "ok": True,
        "gems": gems,
        "streak_freezes": wallet.get("streak_freezes") or 0,
        "avatar_frame": wallet.get("avatar_frame"),
        "streak_freeze_price": STREAK_FREEZE_PRICE,
        "frames": frames,
        "unit_offers": unit_offers,
    })


@app.post("/api/shop/buy")
def shop_buy():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    item = (body.get("item") or "").strip()
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    wallet = get_wallet(client, user.id)
    gems = wallet.get("gems") or 0

    if item == "streak_freeze":
        if gems < STREAK_FREEZE_PRICE:
            return json_error("No tienes suficientes gemas.")
        client.table("profiles").update({
            "gems": gems - STREAK_FREEZE_PRICE,
            "streak_freezes": (wallet.get("streak_freezes") or 0) + 1,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems - STREAK_FREEZE_PRICE})

    if item.startswith("frame:"):
        frame_id = item.split(":", 1)[1]
        frame = AVATAR_FRAMES.get(frame_id)
        if not frame:
            return json_error("Marco no encontrado.", 404)
        owned = wallet.get("owned_frames") or []
        if frame_id not in owned:
            if gems < frame["price"]:
                return json_error("No tienes suficientes gemas.")
            owned = owned + [frame_id]
            gems -= frame["price"]
        client.table("profiles").update({
            "gems": gems,
            "owned_frames": owned,
            "avatar_frame": frame_id,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems, "avatar_frame": frame_id})

    if item.startswith("unlock_unit:"):
        unit_code = item.split(":", 1)[1]
        unit = get_unit(unit_code)
        price = UNIT_UNLOCK_PRICES.get(unit_code)
        if not unit or not price:
            return json_error("Unidad no disponible para desbloquear con gemas.", 404)
        if gems < price:
            return json_error("No tienes suficientes gemas.")
        try:
            client.table("gem_unit_unlocks").insert({"user_id": user.id, "unit_code": unit_code}).execute()
        except Exception as exc:
            return json_error(f"No se pudo desbloquear la unidad: {exc}", 500)
        client.table("profiles").update({"gems": gems - price}).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems - price})

    return json_error("Artículo no reconocido.")


def _clean_mistakes(raw):
    out = []
    for m in (raw or [])[:12]:
        if isinstance(m, dict):
            en = str(m.get("en") or "").strip()[:140]
            es = str(m.get("es") or "").strip()[:140]
            if en:
                out.append({"en": en, "es": es})
    return out


def _save_mistakes_as_vocab(user_id, mistakes):
    """Las palabras que fallaste pasan a tu vocabulario para repasarlas con repetición espaciada."""
    client = supabase_admin or supabase
    if not client:
        return
    for m in mistakes[:5]:
        if not m.get("es") or len(_tokens(m["en"])) > 4:
            continue
        try:
            exists = (client.table("vocabulario_usuario").select("id").eq("user_id", user_id)
                      .eq("palabra", m["en"]).limit(1).execute()).data or []
            if not exists:
                client.table("vocabulario_usuario").insert({
                    "user_id": user_id, "palabra": m["en"], "significado": m["es"], "ejemplo": "",
                    "origen": "ruta",
                }).execute()
        except Exception as exc:
            print(f"[LESSON VOCAB] {exc}")


def _path_for_user(user_id):
    prof = _profile_for_path(user_id)
    level_rank = PROFILE_LEVEL_RANK.get(prof["cefr_level"], 0)
    progress = fetch_learning_progress(user_id)
    gems = _gem_unlocks(user_id)
    sections, nxt = compute_path(progress, level_rank, prof["learning_goal"], gems)
    return prof, level_rank, progress, gems, sections, nxt


@app.get("/api/learning-path")
def learning_path():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    prof, level_rank, progress, gems, sections, nxt = _path_for_user(user.id)
    units_flat = [u for s in sections for u in s["units"]]
    total_done = sum(s["done"] for s in sections)
    total = sum(s["total"] for s in sections)
    stars = sum(u["stars"] for u in units_flat)
    stats = phoneme_stats(user.id)
    weak = sorted([(v["avg"], k) for k, v in stats.items() if v["samples"] >= 3 and v["avg"] < 80])
    focus_ids = [k for _a, k in weak[:3]] or DEFAULT_SOUND_FOCUS[:3]
    mistakes = recent_mistakes(user.id)
    today = sessions_today(user.id)
    return jsonify({
        "ok": True, "xp": prof["xp"], "sections": sections, "units": units_flat, "next": nxt,
        "profile": {"level": prof["cefr_level"] or "beginner", "goal": prof["learning_goal"],
                    "goal_label": GOAL_LABELS.get(prof["learning_goal"], ""),
                    "daily_minutes": prof["daily_goal_minutes"]},
        "today": {"lessons": today, "target": daily_target_lessons(prof["daily_goal_minutes"])},
        "totals": {"done": total_done, "total": total, "stars": stars,
                   "max_stars": sum(u["max_stars"] for u in units_flat)},
        "review": {"available": bool(mistakes) or total_done > 0, "mistakes": len(mistakes)},
        "sounds": {"personalized": bool(weak), "focus": [sound_info(s) for s in focus_ids]},
    })


@app.get("/api/learning-path/sounds")
def learning_path_sounds():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    stats = phoneme_stats(user.id)
    progress = fetch_learning_progress(user.id)
    items = []
    for sid, info in SOUND_LAB.items():
        st = stats.get(sid)
        avg = st["avg"] if st and st["samples"] >= 3 else None
        status = "new" if avg is None else ("weak" if avg < 75 else "ok")
        row = progress.get(("sound_lab", sid))
        items.append({"id": sid, **info, "avg": avg, "samples": st["samples"] if st else 0, "status": status,
                      "best": row.get("score") if row else None})
    personalized = any(i["status"] == "weak" for i in items)

    def sort_key(i):
        if i["status"] == "weak":
            return (0, i["avg"])
        if personalized:
            return (2 if i["status"] == "ok" else 1, 0)
        d = DEFAULT_SOUND_FOCUS.index(i["id"]) if i["id"] in DEFAULT_SOUND_FOCUS else 99
        return (1, d)
    items.sort(key=sort_key)
    return jsonify({"ok": True, "personalized": personalized, "sounds": items})


@app.get("/api/learning-path/lesson/<unit_code>/<lesson_id>")
def learning_path_lesson(unit_code, lesson_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    unit = get_unit(unit_code)
    if not unit:
        return json_error("Unidad no encontrada.", 404)
    mode = (request.args.get("mode") or "lesson").strip()
    prof, level_rank, progress, gems, sections, _nxt = _path_for_user(user.id)
    if mode == "review":
        mistakes = [m for m in recent_mistakes(user.id) if m.get("es")]
        data = build_lesson_payload(unit, "review", level_rank, mode="review", mistakes=mistakes)
    else:
        if lesson_id != "challenge" and not get_lesson(unit, lesson_id):
            return json_error("Lección no encontrada.", 404)
        lesson_state = None
        for s in sections:
            for u in s["units"]:
                if u["code"] == unit_code:
                    lesson_state = next((l for l in u["lessons"] if l["id"] == lesson_id), None)
        if not lesson_state or lesson_state["state"] == "locked":
            return json_error("Esta lección todavía está bloqueada. Completa la anterior primero.", 403)
        data = build_lesson_payload(unit, lesson_id, level_rank)
        data["replay"] = lesson_state["completed"]
        data["best_score"] = lesson_state["score"]
    data.update({"unit_code": unit_code, "unit_title": unit["title"], "icon": unit["icon"], "lesson_id": lesson_id, "mode": mode})
    if not data["exercises"]:
        return json_error("No se pudo preparar la lección.", 500)
    return jsonify({"ok": True, **data})


@app.post("/api/learning-path/review")
def learning_path_review_alias():
    return json_error("Usa /api/learning-path/lesson con mode=review.", 404)


@app.post("/api/learning-path/complete")
def learning_path_complete():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    kind = (body.get("kind") or "lesson").strip()
    if kind not in ("lesson", "review", "sound"):
        return json_error("Tipo de sesión no válido.")
    try:
        seconds = max(0, min(7200, int(body.get("seconds") or 0)))
        correct = int(body.get("correct") or 0)
        total = int(body.get("total") or 0)
    except (TypeError, ValueError):
        return json_error("Datos de la lección no válidos.")
    mistakes = _clean_mistakes(body.get("mistakes"))
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    unit_code = (body.get("unit_code") or "").strip()
    lesson_id = (body.get("lesson_id") or "").strip()
    unit = None
    if kind == "sound":
        sid = (body.get("sound_id") or "").strip()
        if sid not in SOUND_LAB:
            return json_error("Sonido no encontrado.", 404)
        try:
            score = max(0.0, min(100.0, float(body.get("score") or 0)))
        except (TypeError, ValueError):
            score = 0.0
        unit_code, lesson_id = "sound_lab", sid
    else:
        total = max(1, min(40, total))
        correct = max(0, min(total, correct))
        score = round(100 * correct / total, 1)
        if kind == "lesson":
            unit = get_unit(unit_code)
            if not unit or (lesson_id != "challenge" and not get_lesson(unit, lesson_id)):
                return json_error("Lección no encontrada.", 404)
            prof, level_rank, progress_before, gems, sections, _n = _path_for_user(user.id)
            st = None
            for s in sections:
                for u in s["units"]:
                    if u["code"] == unit_code:
                        st = next((l for l in u["lessons"] if l["id"] == lesson_id), None)
            if not st or st["state"] == "locked":
                return json_error("Esta lección todavía está bloqueada.", 403)

    passed = score >= PASS_THRESHOLD
    stars = stars_for(score)
    first_time = False
    xp = 0
    unit_bonus = 0
    unit_completed = False
    best = score
    if kind in ("lesson", "sound"):
        try:
            already, best = _upsert_progress(client, user.id, unit_code, lesson_id,
                                             "lesson" if kind == "lesson" else "sound", score, passed)
        except Exception as exc:
            print(f"[LEARNING COMPLETE SAVE] {exc}")
            return json_error("No se pudo guardar tu progreso. Inténtalo de nuevo.", 500)
        first_time = passed and not already
        if seconds >= 15 and passed:
            if kind == "lesson":
                xp = (15 + 5 * stars) if first_time else 8
            else:
                xp = 12 if first_time else 5
        if kind == "lesson" and first_time and unit:
            progress_after = fetch_learning_progress(user.id)
            unit_completed = all((unit_code, t["id"]) in progress_after for t in unit["topics"])
            if unit_completed:
                unit_bonus = 30
                xp += unit_bonus
    else:  # review
        if seconds >= 15 and total >= 6:
            xp = 10

    if xp:
        award_xp(user.id, xp)
    _log_session(user.id, kind, unit_code or None, lesson_id or None, score, stars, xp, mistakes, seconds)
    if kind != "sound":
        _save_mistakes_as_vocab(user.id, mistakes)

    next_step = None
    try:
        next_step = _path_for_user(user.id)[5]
    except Exception as exc:
        print(f"[LEARNING NEXT] {exc}")
    return jsonify({
        "ok": True, "kind": kind, "score": score, "best": best, "stars": stars, "passed": passed,
        "first_time": first_time, "xp": xp, "unit_bonus": unit_bonus, "unit_completed": unit_completed,
        "mistakes": len(mistakes), "next": next_step,
    })


@app.get("/api/vocabulario")
def vocab_list():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    try:
        rows = (
            client.table("vocabulario_usuario")
            .select("id,palabra,significado,ejemplo,origen,aprendida,created_at")
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        ).data or []
        learned = sum(1 for r in rows if r.get("aprendida"))
        return jsonify({"ok": True, "palabras": rows, "total": len(rows), "aprendidas": learned})
    except Exception as exc:
        return json_error(f"No se pudo cargar tu vocabulario: {exc}", 500)


@app.get("/api/achievements")
def achievements():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase

    streak = 0
    try:
        profile = (
            client.table("profiles")
            .select("streak_days")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        streak = (profile.data or {}).get("streak_days") or 0
    except Exception as exc:
        print(f"[ACHIEVEMENTS PROFILE] {exc}")

    counts = {}
    bests = {}
    for key, (table, col) in {
        "pronunciacion": ("historial_pronunciacion", "puntuacion_global"),
        "escritura": ("historial_escritura", "calificacion"),
        "lectura": ("historial_lectura", "calificacion"),
        "dictado": ("historial_dictado", "calificacion"),
        "tutor": ("historial_tutor", None),
    }.items():
        try:
            select_cols = col if col else "id"
            rows = (
                client.table(table)
                .select(select_cols)
                .eq("user_id", user.id)
                .execute()
            ).data or []
            counts[key] = len(rows)
            if col:
                vals = [r[col] for r in rows if r.get(col) is not None]
                bests[key] = max(vals) if vals else 0
        except Exception as exc:
            print(f"[ACHIEVEMENTS:{table}] {exc}")
            counts[key] = 0
            bests[key] = 0

    total = sum(counts.get(k, 0) for k in ["pronunciacion", "escritura", "lectura", "dictado"])

    def pct(value, target):
        return min(100, round(value / target * 100)) if target else 0

    items = [
        {"code": "first_lesson", "title": "First Lesson", "icon": "🏆",
         "unlocked": total >= 1, "progress": pct(total, 1)},
        {"code": "streak_7", "title": "7 Day Streak", "icon": "🔥",
         "unlocked": streak >= 7, "progress": pct(streak, 7)},
        {"code": "streak_30", "title": "30 Day Streak", "icon": "🎯",
         "unlocked": streak >= 30, "progress": pct(streak, 30)},
        {"code": "first_conversation", "title": "First Conversation", "icon": "🗣️",
         "unlocked": counts.get("tutor", 0) >= 1, "progress": pct(counts.get("tutor", 0), 1)},
        {"code": "writing_master", "title": "Writing Master", "icon": "✍️",
         "unlocked": counts.get("escritura", 0) >= 10 or bests.get("escritura", 0) >= 90,
         "progress": max(pct(counts.get("escritura", 0), 10), pct(bests.get("escritura", 0), 90))},
        {"code": "listening_pro", "title": "Listening Pro", "icon": "🎧",
         "unlocked": counts.get("dictado", 0) >= 10, "progress": pct(counts.get("dictado", 0), 10)},
        {"code": "reading_explorer", "title": "Reading Explorer", "icon": "📖",
         "unlocked": counts.get("lectura", 0) >= 10, "progress": pct(counts.get("lectura", 0), 10)},
        {"code": "speaking_star", "title": "Speaking Star", "icon": "⭐",
         "unlocked": counts.get("pronunciacion", 0) >= 10 or bests.get("pronunciacion", 0) >= 90,
         "progress": max(pct(counts.get("pronunciacion", 0), 10), pct(bests.get("pronunciacion", 0), 90))},
    ]

    return jsonify({"ok": True, "achievements": items, "unlocked_count": sum(1 for i in items if i["unlocked"])})


@app.get("/api/dashboard")
def dashboard():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase

    xp, streak, daily_minutes = 0, 0, 10
    try:
        profile = (
            client.table("profiles")
            .select("xp,streak_days,last_activity_date,daily_goal_minutes")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        pdata = profile.data or {}
        daily_minutes = pdata.get("daily_goal_minutes") or 10
        xp = pdata.get("xp") or 0
        streak = pdata.get("streak_days") or 0
        last = pdata.get("last_activity_date")
        if last:
            last_date = datetime.fromisoformat(last).date()
            today = datetime.now(timezone.utc).date()
            if last_date < today - timedelta(days=1):
                streak = 0  # la racha se rompió, aunque el contador guardado aún no lo refleje
    except Exception as exc:
        print(f"[DASHBOARD PROFILE] {exc}")

    xp_per_level = 150
    level = xp // xp_per_level + 1
    xp_into_level = xp % xp_per_level

    skill_tables = {
        "speaking": ("historial_pronunciacion", "puntuacion_global"),
        "listening": ("historial_dictado", "calificacion"),
        "reading": ("historial_lectura", "calificacion"),
        "writing": ("historial_escritura", "calificacion"),
    }
    skills = {}
    today_count = 0
    today_str = datetime.now(timezone.utc).date().isoformat()
    for key, (table, col) in skill_tables.items():
        try:
            rows = (
                client.table(table)
                .select(f"{col},created_at")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ).data or []
            vals = [r[col] for r in rows if r.get(col) is not None]
            skills[key] = round(sum(vals) / len(vals)) if vals else 0
            today_count += sum(1 for r in rows if (r.get("created_at") or "").startswith(today_str))
        except Exception as exc:
            print(f"[DASHBOARD:{table}] {exc}")
            skills[key] = 0

    today_count += sessions_today(user.id)  # las lecciones de la Ruta también cuentan para la meta diaria
    daily_goal_activities = max(2, daily_target_lessons(daily_minutes))
    daily_goal_pct = min(100, round(today_count / daily_goal_activities * 100))

    today_date = datetime.now(timezone.utc).date()
    week_start = today_date - timedelta(days=6)
    active_days = set()
    for table, _col in skill_tables.values():
        try:
            rows_week = (
                client.table(table)
                .select("created_at")
                .eq("user_id", user.id)
                .gte("created_at", week_start.isoformat())
                .execute()
            ).data or []
            for r in rows_week:
                ca = r.get("created_at")
                if not ca:
                    continue
                try:
                    active_days.add(datetime.fromisoformat(ca.replace("Z", "+00:00")).date().isoformat())
                except Exception:
                    pass
        except Exception as exc:
            print(f"[DASHBOARD WEEK:{table}] {exc}")
    active_days |= session_days(user.id, week_start.isoformat())
    week = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "active": d.isoformat() in active_days,
            "is_today": d == today_date,
        })

    return jsonify({
        "week": week,
        "ok": True,
        "xp": xp,
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_per_level": xp_per_level,
        "streak_days": streak,
        "skills": skills,
        "daily_goal_pct": daily_goal_pct,
        "today_activities": today_count,
    })


@app.get("/api/progreso")
def progress():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    table_map = {
        "pronunciacion": ("historial_pronunciacion", "puntuacion_global"),
        "escritura": ("historial_escritura", "calificacion"),
        "lectura": ("historial_lectura", "calificacion"),
        "dictado": ("historial_dictado", "calificacion"),
    }
    client = supabase_admin or supabase
    counts = {}
    all_rows = []
    for key, (table, score_col) in table_map.items():
        try:
            rows = (
                client.table(table)
                .select(f"created_at,{score_col}")
                .eq("user_id", user.id)
                .order("created_at", desc=False)
                .limit(50)
                .execute()
            ).data or []
            counts[key] = len(rows)
            for row in rows:
                all_rows.append({"created_at": row.get("created_at"), "score": row.get(score_col)})
        except Exception as exc:
            print(f"[PROGRESS:{table}] {exc}")
            counts[key] = 0

    all_rows.sort(key=lambda r: r.get("created_at") or "")
    scores = [r.get("score") for r in all_rows[-20:] if r.get("score") is not None]

    return jsonify({
        "ok": True,
        "total_actividades": sum(counts.values()),
        "pronunciacion": counts.get("pronunciacion", 0),
        "escritura": counts.get("escritura", 0),
        "lectura": counts.get("lectura", 0),
        "puntuaciones_recientes": scores,
    })


@app.get("/")
def root():
    return jsonify({"ok": True, "service": "Talvo English API"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
