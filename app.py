import os
import json
import random
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURACIÓN
# ============================================================
AZURE_SPEECH_KEY = (os.getenv("AZURE_SPEECH_KEY") or "").strip()
AZURE_SPEECH_REGION = (os.getenv("AZURE_SPEECH_REGION") or "").strip()

AZURE_OPENAI_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")
AZURE_OPENAI_KEY = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
AZURE_OPENAI_DEPLOYMENT = (os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o").strip()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_KEY") or "").strip()

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado correctamente.")
    except Exception as e:
        print(f"Error al conectar Supabase: {e}")

ai_client: OpenAI | None = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY:
    try:
        ai_client = OpenAI(
            api_key=AZURE_OPENAI_KEY,
            base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/"
        )
        print(f"Azure OpenAI configurado. Deployment: {AZURE_OPENAI_DEPLOYMENT}")
    except Exception as e:
        print(f"Error al configurar Azure OpenAI: {e}")

# ============================================================
# RESPALDOS
# ============================================================
FRASES_BASE = [
    {"frase": "Today was a beautiful day. We had a great time taking a long walk outside in the morning.",
     "traduccion": "Hoy fue un día hermoso. Nos la pasamos genial dando un largo paseo por la mañana."},
    {"frase": "I usually start my day with a cup of coffee and a short walk.",
     "traduccion": "Normalmente empiezo mi día con una taza de café y una caminata corta."},
    {"frase": "Learning a little every day can make a big difference over time.",
     "traduccion": "Aprender un poco cada día puede marcar una gran diferencia con el tiempo."},
]

LECTURA_RESPALDO = {
    "titulo": "Why Urban Trees Matter",
    "texto": (
        "Trees in cities do more than make streets look attractive. They provide shade, "
        "reduce heat, improve air quality, and create small habitats for birds and insects. "
        "Researchers also study how green spaces can make neighborhoods more comfortable."
    ),
    "nivel": "B1-B2",
    "tema": "Environment"
}

# ============================================================
# IA
# ============================================================
def generar_texto_ia(prompt, temperature=0.4):
    if not ai_client:
        print("Azure OpenAI no está configurado.")
        return None
    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the AI engine of English Academy. "
                        "Be precise, encouraging, concise and pedagogical. "
                        "When the user asks for JSON, return only valid JSON."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR AZURE OPENAI] {e}")
        return None


def generar_json_ia(prompt, fallback=None):
    if not ai_client:
        return fallback
    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an English-learning content engine. "
                        "Return JSON only. Do not use Markdown fences."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1800,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        return json.loads(text)
    except Exception as e:
        print(f"[ERROR JSON AZURE OPENAI] {e}")
        return fallback


# ============================================================
# AUTENTICACIÓN
# ============================================================
def obtener_usuario_autenticado_y_suscrito():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Debes iniciar sesión para continuar."

    token = auth_header.split(" ", 1)[1].strip()
    if not token or not supabase:
        return None, "La sesión no está disponible."

    try:
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            return None, "Sesión inválida o expirada."

        user_id = user_res.user.id
        res = supabase.table("profiles").select("is_subscribed").eq("id", user_id).execute()
        activo = bool(res.data and res.data[0].get("is_subscribed", False))

        if not activo:
            return None, "Tu cuenta todavía no tiene acceso activo."

        return user_id, None
    except Exception as e:
        print(f"[ERROR AUTH] {e}")
        return None, "No fue posible validar tu sesión."


# ============================================================
# CONTENIDO
# ============================================================
@app.route("/nueva-frase", methods=["GET"])
def nueva_frase():
    prompt = """
    Create one natural everyday English sentence for an A2-B2 learner.
    Return JSON:
    {"frase":"...", "traduccion":"..."}
    """
    data = generar_json_ia(prompt, random.choice(FRASES_BASE))
    return jsonify(data)


@app.route("/nuevo-texto-lectura", methods=["GET"])
def nuevo_texto_lectura():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    prompt = """
    Create a short authentic-looking informational English reading for a B1-B2 learner.
    Topics: science, technology, history, nature, psychology, culture, travel or society.
    Length: 90-140 words.
    Do NOT provide a Spanish translation.
    Return JSON exactly:
    {
      "titulo": "...",
      "texto": "...",
      "nivel": "B1-B2",
      "tema": "..."
    }
    """
    data = generar_json_ia(prompt, LECTURA_RESPALDO)
    return jsonify(data)


@app.route("/evaluar-lectura", methods=["POST"])
def evaluar_lectura():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    data = request.json or {}
    titulo = str(data.get("titulo", "")).strip()
    texto = str(data.get("texto", "")).strip()
    respuesta = str(data.get("respuesta", "")).strip()

    if not texto or not respuesta:
        return jsonify({"error": "Escribe primero lo que entendiste del texto."}), 400

    prompt = f"""
    You are an expert English teacher.

    Original informational text:
    {texto}

    Student title:
    {titulo}

    Student wrote this in English to explain what they understood:
    {respuesta}

    Evaluate comprehension, not whether the student copied exact sentences.
    Return JSON exactly:
    {{
      "calificacion": 0,
      "idea_principal": 0,
      "detalles": 0,
      "vocabulario": 0,
      "claridad": 0,
      "nivel_estimado": "B1",
      "resumen_evaluacion": "...",
      "aciertos": ["..."],
      "faltantes": ["..."],
      "vocabulario_util": [
        {{"palabra":"...", "significado":"...", "ejemplo":"..."}}
      ],
      "recomendacion": "..."
    }}

    Scores must be 0-100. calificacion is 0-10.
    Respond in Spanish except for English examples.
    """

    result = generar_json_ia(prompt)
    if not result:
        return jsonify({"error": "Nuestra inteligencia no pudo completar el análisis. Inténtalo de nuevo."}), 500

    # Guardado opcional si el usuario ya creó esta tabla.
    if supabase:
        try:
            supabase.table("historial_lectura").insert({
                "user_id": user_id,
                "titulo": titulo,
                "calificacion": result.get("calificacion", 0),
                "idea_principal": result.get("idea_principal", 0),
                "detalles": result.get("detalles", 0),
                "vocabulario": result.get("vocabulario", 0),
                "claridad": result.get("claridad", 0),
                "respuesta": respuesta,
            }).execute()
        except Exception as e:
            print(f"[INFO] Historial de lectura no guardado: {e}")

    return jsonify(result)


@app.route("/nuevo-trabalenguas", methods=["GET"])
def nuevo_trabalenguas():
    fallback = {
        "trabalenguas": "Peter Piper picked a peck of pickled peppers.",
        "traduccion": "Peter Piper recogió un bocado de pimientos encurtidos.",
        "enfoque": "Sonido /p/"
    }
    prompt = """
    Create a challenging but clear English tongue twister for pronunciation practice.
    Return JSON:
    {"trabalenguas":"...", "traduccion":"...", "enfoque":"..."}
    """
    return jsonify(generar_json_ia(prompt, fallback))


@app.route("/nuevo-tema-libre", methods=["GET"])
def nuevo_tema_libre():
    fallback = {
        "tema": "What are your goals for learning English?",
        "instrucciones": "Speak naturally for 20 to 30 seconds. Give examples.",
        "traduccion": "¿Cuáles son tus objetivos al aprender inglés?"
    }
    prompt = """
    Create one natural conversation prompt for an A2-B2 English learner.
    Return JSON:
    {"tema":"...", "instrucciones":"...", "traduccion":"..."}
    """
    return jsonify(generar_json_ia(prompt, fallback))


@app.route("/nuevo-dictado", methods=["GET"])
def nuevo_dictado():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    prompt = """
    Create one natural English dictation sentence for an intermediate learner.
    7-14 words. Return JSON: {"frase":"..."}
    """
    fallback = {"frase": "The meeting was moved to Friday because of the weather."}
    return jsonify(generar_json_ia(prompt, fallback))


# ============================================================
# PRONUNCIACIÓN
# ============================================================
def convertir_audio(request_file):
    temp_webm_path = None
    converted_wav_path = None

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    request_file.save(temp.name)
    temp.close()
    temp_webm_path = temp.name

    converted_wav_path = temp_webm_path + "_16k.wav"
    sound = AudioSegment.from_file(temp_webm_path)
    sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    sound.export(converted_wav_path, format="wav")

    return temp_webm_path, converted_wav_path


def limpiar_archivos(*paths):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


@app.route("/analizar-audio-real", methods=["POST"])
@app.route("/api/assess-reading", methods=["POST"])
def analizar_audio_lectura():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    if "audio" not in request.files:
        return jsonify({"error": "No se recibió audio."}), 400

    frase_esperada = request.form.get(
        "frase_esperada",
        request.form.get("reference_text", "")
    ).strip()

    if not frase_esperada:
        return jsonify({"error": "No hay una frase de referencia."}), 400

    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return jsonify({"error": "El servicio de análisis de voz no está configurado."}), 500

    temp_webm_path = converted_wav_path = None

    try:
        temp_webm_path, converted_wav_path = convertir_audio(request.files["audio"])

        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        speech_config.speech_recognition_language = "en-US"

        audio_config = speechsdk.audio.AudioConfig(filename=converted_wav_path)
        pron_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=frase_esperada,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True
        )
        pron_config.enable_prosody_assessment()

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        pron_config.apply_to(recognizer)

        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation = speechsdk.CancellationDetails(result)
            return jsonify({"error": "No fue posible analizar el audio."}), 500

        if result.reason == speechsdk.ResultReason.NoMatch:
            return jsonify({"error": "No se detectó voz clara. Habla un poco más cerca del micrófono."}), 400

        pron_result = speechsdk.PronunciationAssessmentResult(result)

        precision = round(pron_result.accuracy_score)
        fluidez = round(pron_result.fluency_score)
        completitud = round(pron_result.completeness_score)
        prosodia = round(pron_result.prosody_score)
        puntuacion_global = round(pron_result.pronunciation_score)

        json_str = result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        azure_json = json.loads(json_str) if json_str else {}
        nbest = azure_json.get("NBest", [{}])[0]
        words_detail_json = nbest.get("Words", [])

        inspeccion = {
            "omisiones": 0,
            "pronunciaciones_incoherentes": 0,
            "inserciones": 0,
            "interrupcion_inesperada": 0,
            "falta_un_descanso": 0,
            "monotona": 0
        }

        palabras_detalle = []

        for w in words_detail_json:
            word_text = w.get("Word", "")
            pa = w.get("PronunciationAssessment", {})
            error_type = pa.get("ErrorType", "None")
            acc_score = round(pa.get("AccuracyScore", 0))

            feedback = pa.get("Feedback", {})
            prosody_feedback = feedback.get("Prosody", {})
            break_errors = prosody_feedback.get("Break", {})
            intonation_errors = prosody_feedback.get(
                "Intonation", {}
            ).get("ErrorTypes", [])

            if error_type == "Omission":
                inspeccion["omisiones"] += 1
            elif error_type == "Mispronunciation":
                inspeccion["pronunciaciones_incoherentes"] += 1
            elif error_type == "Insertion":
                inspeccion["inserciones"] += 1

            if "UnexpectedBreak" in break_errors:
                inspeccion["interrupcion_inesperada"] += 1
            if "MissingBreak" in break_errors:
                inspeccion["falta_un_descanso"] += 1
            if "Monotone" in intonation_errors:
                inspeccion["monotona"] += 1

            fonemas = []
            for p in w.get("Phonemes", []):
                p_pa = p.get("PronunciationAssessment", {})
                fonemas.append({
                    "fonema": p.get("Phoneme", ""),
                    "precision": round(p_pa.get("AccuracyScore", 0))
                })

            palabras_detalle.append({
                "palabra": word_text,
                "puntuacion": acc_score,
                "precision": acc_score,
                "error_type": error_type,
                "fonemas": fonemas
            })

        if prosodia < 60 and inspeccion["monotona"] == 0:
            inspeccion["monotona"] = 1

        if supabase:
            try:
                supabase.table("historial_pronunciacion").insert({
                    "frase_esperada": frase_esperada,
                    "precision_fonemas": precision,
                    "fluidez": fluidez,
                    "completitud": completitud,
                    "puntuacion_global": puntuacion_global,
                    "user_id": user_id
                }).execute()
            except Exception as e:
                print(f"[INFO] No se pudo guardar pronunciación: {e}")

        return jsonify({
            "calificacion": round(puntuacion_global / 10, 1),
            "puntuacion_global": puntuacion_global,
            "precision": precision,
            "fluidez": fluidez,
            "completitud": completitud,
            "prosodia": prosodia,
            "inspeccion": inspeccion,
            "palabras": palabras_detalle
        })

    except Exception as e:
        print(f"[ERROR PRONUNCIACIÓN] {e}")
        return jsonify({"error": "Ocurrió un problema al procesar tu audio."}), 500
    finally:
        limpiar_archivos(temp_webm_path, converted_wav_path)


@app.route("/api/assess-unscripted", methods=["POST"])
def assess_unscripted():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    if "audio" not in request.files:
        return jsonify({"error": "No se recibió audio."}), 400

    topic = request.form.get("topic", "General Conversation").strip()

    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return jsonify({"error": "El servicio de análisis de voz no está configurado."}), 500

    temp_webm_path = converted_wav_path = None

    try:
        temp_webm_path, converted_wav_path = convertir_audio(request.files["audio"])

        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        speech_config.speech_recognition_language = "en-US"

        audio_config = speechsdk.audio.AudioConfig(filename=converted_wav_path)

        json_config = {
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "EnableMiscue": False
        }

        pron_config = speechsdk.PronunciationAssessmentConfig(
            json_string=json.dumps(json_config)
        )
        pron_config.enable_prosody_assessment()
        pron_config.enable_content_assessment_with_topic(topic)

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        pron_config.apply_to(recognizer)

        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.Canceled:
            return jsonify({"error": "No fue posible analizar el audio."}), 500

        if result.reason == speechsdk.ResultReason.NoMatch:
            return jsonify({"error": "No se detectó voz clara."}), 400

        pron_result = speechsdk.PronunciationAssessmentResult(result)
        content_result = pron_result.content_assessment_result

        return jsonify({
            "transcription": result.text,
            "pronunciation_score": round(pron_result.pronunciation_score),
            "accuracy_score": round(pron_result.accuracy_score),
            "fluency_score": round(pron_result.fluency_score),
            "prosody_score": round(pron_result.prosody_score),
            "content_assessment": {
                "grammar_score": round(content_result.grammar_score)
                if content_result and content_result.grammar_score is not None else None,
                "vocabulary_score": round(content_result.vocabulary_score)
                if content_result and content_result.vocabulary_score is not None else None,
                "topic_score": round(content_result.topic_score)
                if content_result and content_result.topic_score is not None else None
            }
        })

    except Exception as e:
        print(f"[ERROR HABLA LIBRE] {e}")
        return jsonify({"error": "Ocurrió un problema al procesar tu audio."}), 500
    finally:
        limpiar_archivos(temp_webm_path, converted_wav_path)


# ============================================================
# ESCRITURA / DICTADO
# ============================================================
@app.route("/analizar-escritura", methods=["POST"])
def analizar_escritura():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    data = request.json or {}
    texto = str(data.get("texto", "")).strip()

    if not texto:
        return jsonify({"error": "Escribe algo antes de enviarlo."}), 400

    prompt = f"""
    Evaluate this English writing as a professional English teacher:

    STUDENT TEXT:
    {texto}

    Return JSON exactly:
    {{
      "calificacion": 0,
      "gramatica": 0,
      "vocabulario": 0,
      "claridad": 0,
      "naturalidad": 0,
      "analisis": "...",
      "correcciones": [
        {{"original":"...", "corregido":"...", "explicacion":"..."}}
      ],
      "version_natural": "...",
      "siguiente_paso": "..."
    }}

    Scores are 0-10. Respond in Spanish except English examples.
    """
    result = generar_json_ia(prompt)

    if not result:
        return jsonify({"error": "Nuestra inteligencia no pudo completar el análisis."}), 500

    return jsonify(result)


@app.route("/evaluar-dictado", methods=["POST"])
def evaluar_dictado():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    data = request.json or {}
    original = str(data.get("original", "")).strip()
    usuario = str(data.get("usuario", "")).strip()

    if not usuario:
        return jsonify({"error": "Escribe lo que escuchaste."}), 400

    prompt = f"""
    Compare the original dictation sentence with the student's answer.

    ORIGINAL:
    {original}

    STUDENT:
    {usuario}

    Return JSON exactly:
    {{
      "calificacion": 0,
      "aciertos": ["..."],
      "errores": ["..."],
      "analisis": "...",
      "consejo": "..."
    }}

    Score 0-10. Respond in Spanish.
    """
    result = generar_json_ia(prompt)

    if not result:
        return jsonify({"error": "Nuestra inteligencia no pudo completar el análisis."}), 500

    return jsonify(result)


@app.route("/api/tutor", methods=["POST"])
def tutor():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    data = request.json or {}
    message = str(data.get("message", "")).strip()
    history = data.get("history", [])
    pronunciation_score = data.get("pronunciation_score", "N/A")

    if not message:
        return jsonify({"error": "Escribe un mensaje."}), 400

    safe_history = []
    if isinstance(history, list):
        for item in history[-8:]:
            if isinstance(item, dict):
                safe_history.append({
                    "role": item.get("role", "user"),
                    "content": str(item.get("content", ""))[:1200]
                })

    messages = [{
        "role": "system",
        "content": (
            "You are English Academy's personal English tutor. "
            "Speak mainly in English. Adapt vocabulary and sentence complexity "
            "to the learner. Keep the conversation natural; do not turn every "
            "message into a grammar lecture. Correct only one or two important "
            "mistakes when useful, using a short correction after your natural reply. "
            "Ask a follow-up question so the conversation continues. "
            "Be encouraging and never shame the learner. "
            f"The learner's latest pronunciation score, if available, is {pronunciation_score}/100."
        )
    }]
    messages.extend(safe_history)
    messages.append({"role": "user", "content": message})

    if not ai_client:
        return jsonify({"error": "El tutor no está configurado todavía."}), 500

    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"[ERROR TUTOR] {e}")
        return jsonify({"error": "No fue posible responder en este momento."}), 500

# ============================================================
# HISTORIAL
# ============================================================
@app.route("/obtener-historial", methods=["GET"])
def obtener_historial():
    user_id, err = obtener_usuario_autenticado_y_suscrito()
    if err:
        return jsonify({"error": err}), 401

    if not supabase:
        return jsonify([])

    try:
        res = (
            supabase.table("historial_pronunciacion")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return jsonify(res.data or [])
    except Exception as e:
        print(f"[ERROR HISTORIAL] {e}")
        return jsonify([])


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "ai_configured": bool(ai_client),
        "speech_configured": bool(AZURE_SPEECH_KEY and AZURE_SPEECH_REGION),
        "supabase_configured": bool(supabase)
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
