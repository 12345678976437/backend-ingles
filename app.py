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
    "/analizar-audio-real": (60, 3600),
    "/api/assess-reading": (40, 3600),
    "/api/assess-unscripted": (40, 3600),
    "/nueva-frase": (60, 3600),
    "/nuevo-tema-libre": (60, 3600),
    "/nuevo-trabalenguas": (60, 3600),
    "/nuevo-texto-lectura": (30, 3600),
    "/nuevo-dictado": (30, 3600),
    "/api/writing/challenge": (30, 3600),
    "/api/vocabulario/diario": (20, 3600),
    "/api/learning-path/practice": (60, 3600),
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


PASS_THRESHOLD = 60  # puntuación mínima para marcar un tema como completado

# Estructura fija de unidades. El contenido de cada lección (frase, texto, prompt...)
# se genera con IA en el momento, ajustado al tema de la unidad.
LEARNING_UNITS = [
    {
        "code": "everyday_english",
        "order": 1,
        "title": "Everyday English",
        "description": "Greetings, routines, and small talk.",
        "icon": "🏠",
        "xp_required": 0,
        "topics": [
            {"id": "greetings", "title": "Greetings & introductions"},
            {"id": "routines", "title": "Daily routines"},
            {"id": "family", "title": "Family & friends"},
            {"id": "smalltalk", "title": "Small talk"},
            {"id": "numbers_time", "title": "Numbers & time"},
        ],
    },
    {
        "code": "at_the_restaurant",
        "order": 2,
        "title": "At the Restaurant",
        "description": "Order food, talk about flavors, and handle the bill.",
        "icon": "🍽️",
        "xp_required": 150,
        "topics": [
            {"id": "ordering", "title": "Ordering food"},
            {"id": "menu", "title": "Understanding a menu"},
            {"id": "preferences", "title": "Likes & dislikes"},
            {"id": "complaints", "title": "Complaints & requests"},
            {"id": "paying", "title": "Paying the bill"},
        ],
    },
    {
        "code": "travel_and_tourism",
        "order": 3,
        "title": "Travel & Tourism",
        "description": "Airports, hotels, directions, and sightseeing.",
        "icon": "✈️",
        "xp_required": 400,
        "topics": [
            {"id": "airport", "title": "At the airport"},
            {"id": "hotel", "title": "Checking into a hotel"},
            {"id": "directions", "title": "Asking for directions"},
            {"id": "sightseeing", "title": "Sightseeing"},
            {"id": "emergencies", "title": "Travel emergencies"},
        ],
    },
    {
        "code": "work_and_business",
        "order": 4,
        "title": "Work & Business",
        "description": "Meetings, emails, interviews, and office talk.",
        "icon": "💼",
        "xp_required": 700,
        "topics": [
            {"id": "interview", "title": "Job interviews"},
            {"id": "meetings", "title": "Meetings"},
            {"id": "emails", "title": "Writing emails"},
            {"id": "smalltalk_office", "title": "Office small talk"},
            {"id": "presentations", "title": "Presentations"},
        ],
    },
]

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


def record_learning_progress(user_id, unit_code, topic_id, tool, score):
    """Guarda el intento de un tema del Learning Path y calcula si se completó la unidad.
    Devuelve None si no venía asociado a ningún tema del Learning Path (uso normal de la herramienta)."""
    if not unit_code or not topic_id:
        return None
    unit = get_unit(unit_code)
    if not unit:
        return None
    topic = get_topic(unit, topic_id)
    if not topic:
        return None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None

    client = supabase_admin or supabase
    if not client:
        return None

    passed = score >= PASS_THRESHOLD
    already_done = False
    try:
        existing = (
            client.table("learning_progress")
            .select("id,completed,score")
            .eq("user_id", user_id)
            .eq("unit_code", unit_code)
            .eq("topic_id", topic_id)
            .maybe_single()
            .execute()
        )
        row = existing.data
        if row:
            already_done = bool(row.get("completed"))
            best_score = max(score, row.get("score") or 0)
            client.table("learning_progress").update({
                "tool": tool,
                "score": best_score,
                "completed": already_done or passed,
            }).eq("id", row["id"]).execute()
        else:
            client.table("learning_progress").insert({
                "user_id": user_id,
                "unit_code": unit_code,
                "topic_id": topic_id,
                "tool": tool,
                "score": score,
                "completed": passed,
            }).execute()
    except Exception as exc:
        print(f"[LEARNING PROGRESS SAVE] {exc}")
        return None

    newly_completed = passed and not already_done
    if newly_completed:
        award_xp(user_id, 30)

    progress = fetch_learning_progress(user_id)
    total = len(unit["topics"])
    completed_count = sum(1 for t in unit["topics"] if (unit_code, t["id"]) in progress)

    return {
        "passed": passed,
        "newly_completed": newly_completed,
        "unit_completed": completed_count == total,
        "completed_topics": completed_count,
        "total_topics": total,
    }


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
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        raw_result = assess_pronunciation(wav_path, reference or None)
        payload = build_pron_payload(raw_result)
        if payload["transcript"]:
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
UNIT_UNLOCK_PRICES = {"at_the_restaurant": 60, "travel_and_tourism": 120, "work_and_business": 200}
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

    progress = fetch_learning_progress(user.id)
    prev_completed = True
    unit_offers = []
    for u in sorted(LEARNING_UNITS, key=lambda u: u["order"]):
        total = len(u["topics"])
        completed = sum(1 for t in u["topics"] if (u["code"], t["id"]) in progress)
        u_completed = total > 0 and completed == total
        price = UNIT_UNLOCK_PRICES.get(u["code"])
        if price and prev_completed and xp < u["xp_required"] and u["code"] not in already_unlocked:
            unit_offers.append({"unit_code": u["code"], "title": u["title"], "price": price})
        prev_completed = u_completed

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


@app.get("/api/learning-path")
def learning_path():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])

    xp, progress, gem_unlocked = _unit_xp_and_progress(user.id)

    units_out = []
    prev_completed = True
    for unit in sorted(LEARNING_UNITS, key=lambda u: u["order"]):
        total = len(unit["topics"])
        completed = sum(1 for t in unit["topics"] if (unit["code"], t["id"]) in progress)
        unit_completed = total > 0 and completed == total
        unlocked = (xp >= unit["xp_required"] or unit["code"] in gem_unlocked) and prev_completed
        units_out.append({
            "code": unit["code"],
            "order": unit["order"],
            "title": unit["title"],
            "description": unit["description"],
            "icon": unit["icon"],
            "xp_required": unit["xp_required"],
            "total_topics": total,
            "completed_topics": completed,
            "completed": unit_completed,
            "unlocked": unlocked,
        })
        prev_completed = unit_completed

    return jsonify({"ok": True, "xp": xp, "units": units_out})


@app.get("/api/learning-path/<unit_code>")
def learning_path_unit(unit_code):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])

    unit = get_unit(unit_code)
    if not unit:
        return json_error("Unidad no encontrada.", 404)

    xp, progress, gem_unlocked = _unit_xp_and_progress(user.id)

    prev_completed = True
    unlocked = False
    for u in sorted(LEARNING_UNITS, key=lambda u: u["order"]):
        total = len(u["topics"])
        completed = sum(1 for t in u["topics"] if (u["code"], t["id"]) in progress)
        u_completed = total > 0 and completed == total
        u_unlocked = (xp >= u["xp_required"] or u["code"] in gem_unlocked) and prev_completed
        if u["code"] == unit_code:
            unlocked = u_unlocked
            break
        prev_completed = u_completed

    if not unlocked:
        return json_error("Esta unidad todavía está bloqueada.", 403)

    topics_out = []
    for t in unit["topics"]:
        row = progress.get((unit_code, t["id"]))
        topics_out.append({
            "id": t["id"],
            "title": t["title"],
            "completed": bool(row),
            "tool": row.get("tool") if row else None,
            "score": row.get("score") if row else None,
        })

    return jsonify({
        "ok": True,
        "unit": {
            "code": unit["code"],
            "title": unit["title"],
            "description": unit["description"],
            "icon": unit["icon"],
        },
        "topics": topics_out,
    })


@app.post("/api/learning-path/practice")
def learning_path_practice():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])

    body = request.get_json(silent=True) or {}
    unit_code = (body.get("unit_code") or "").strip()
    topic_id = (body.get("topic_id") or "").strip()
    tool = (body.get("tool") or "").strip()

    unit = get_unit(unit_code)
    if not unit:
        return json_error("Unidad no encontrada.", 404)
    topic = get_topic(unit, topic_id)
    if not topic:
        return json_error("Tema no encontrado.", 404)
    if tool not in LEARNING_TOOL_LABELS:
        return json_error("Herramienta no válida.")

    theme_line = f'Topic/context: "{topic["title"]}" (part of the unit "{unit["title"]}").'

    try:
        if tool == "pronunciation":
            data = ai_json(
                "You create a short English sentence for a pronunciation exercise, tied to a specific real-life topic. Return JSON only with exact keys: texto (6-14 words, natural spoken English), nivel (CEFR level).",
                f"{theme_line} Create one natural sentence someone would actually say in this situation.",
            )
        elif tool == "dictado":
            data = ai_json(
                "Create an English dictation sentence for an intermediate learner, tied to a specific real-life topic. Return JSON only with exact keys: texto (12-22 words), nivel (CEFR level).",
                f"{theme_line} Create one natural sentence of 12-22 words for this situation.",
            )
        elif tool == "reading":
            data = ai_json(
                "You create short English reading passages for learners, tied to a specific real-life topic. Return JSON only with exact keys: texto (180-260 words), titulo (short title), nivel (CEFR level).",
                f"{theme_line} Create a passage about this situation.",
            )
        else:  # writing
            data = ai_json(
                "You create English writing prompts for learners, tied to a specific real-life topic. Return JSON only with exact keys: prompt (a one or two sentence writing challenge, in English), nivel (CEFR level).",
                f"{theme_line} Create a writing challenge about this situation.",
            )
        data["unit_code"] = unit_code
        data["topic_id"] = topic_id
        data["topic_title"] = topic["title"]
        data["tool"] = tool
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el ejercicio: {exc}", 500)


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

    xp, streak = 0, 0
    try:
        profile = (
            client.table("profiles")
            .select("xp,streak_days,last_activity_date")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        pdata = profile.data or {}
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

    daily_goal_activities = 3
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
