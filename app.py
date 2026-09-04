import json
import os
import random
import re
import tempfile

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from supabase import Client, create_client

load_dotenv()

app = Flask(__name__)
CORS(app)

def env(name, default=""):
    return (os.getenv(name) or default).strip()

AZURE_SPEECH_KEY = env("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = env("AZURE_SPEECH_REGION", "westus3")
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = env("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase conectado.")
    except Exception as exc:
        print(f"[WARN] Supabase no pudo conectarse: {exc}")

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

    if require_subscription:
        try:
            profile = (
                supabase.table("profiles")
                .select("is_subscribed")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            data = profile.data or {}
            if not data.get("is_subscribed"):
                return None, ("Tu acceso todavía no está activo.", 403)
        except Exception as exc:
            print(f"[PROFILE] {exc}")
            return None, ("No se pudo comprobar tu acceso.", 500)

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
    if not supabase:
        return
    try:
        supabase.table(table).insert({"user_id": user_id, **payload}).execute()
    except Exception as exc:
        print(f"[HISTORY:{table}] {exc}")


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
            "phonemes": phonemes,
        })

    return {
        "transcript": nbest.get("Display", ""),
        "pronunciation_score": round(float(assessment_raw.get("PronScore", 0) or 0), 1),
        "accuracy_score": round(float(assessment_raw.get("AccuracyScore", 0) or 0), 1),
        "fluency_score": round(float(assessment_raw.get("FluencyScore", 0) or 0), 1),
        "completeness_score": round(float(assessment_raw.get("CompletenessScore", 0) or 0), 1),
        "prosody_score": round(float(assessment_raw.get("ProsodyScore", 0) or 0), 1),
        "words": words,
    }


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "English Academy",
        "ai": bool(ai_client),
        "speech": bool(AZURE_SPEECH_KEY and AZURE_SPEECH_REGION),
        "supabase": bool(supabase),
    })


@app.get("/api/session")
def session_info():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return jsonify({"authenticated": False, "error": error[0]}), error[1]
    return jsonify({"authenticated": True, "user": {"id": user.id, "email": user.email}})


@app.get("/nueva-frase")
def new_phrase():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create one natural English sentence for pronunciation practice. Return JSON with phrase and level.",
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
            "Create a speaking practice topic for an English learner. Return JSON with topic, prompt, and level.",
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
            "Create a short English tongue twister suitable for pronunciation practice. Return JSON with text and difficulty.",
            "Generate one original tongue twister, 8-18 words, challenging but pronounceable.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar el trabalenguas: {exc}", 500)


@app.get("/nuevo-texto-lectura")
def new_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an informational English reading passage for a learner. Return JSON only.",
            "Create 180-260 words about a real-world topic. Include title, level, passage, and 5 useful vocabulary words with brief English definitions. Do not include questions or Spanish translation.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo generar la lectura: {exc}", 500)


@app.get("/nuevo-dictado")
def new_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an English dictation sentence for an intermediate learner. Return JSON only.",
            "Create one natural sentence of 12-22 words. Include text and level.",
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
    reference = (request.form.get("reference") or "").strip()
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        result = assess_pronunciation(wav_path, reference or None)
        if result["transcript"]:
            try:
                coach = ai_json(
                    "You are a supportive English pronunciation coach. Return concise JSON.",
                    f"Transcript: {result['transcript']}\nReference: {reference}\nScores: {json.dumps(result, ensure_ascii=False)}\nGive 3 actionable tips and a short encouraging comment.",
                    temperature=0.4,
                )
                result["coach"] = coach
            except Exception as exc:
                print(f"[AI COACH] {exc}")
        save_history("historial_pronunciacion", user.id, {
            "mode": "guided" if reference else "free",
            "reference_text": reference,
            "transcript": result["transcript"],
            "score": result["pronunciation_score"],
            "details": result,
        })
        return jsonify({"ok": True, **result})
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


@app.post("/analizar-escritura")
def analyze_writing():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if not text:
        return json_error("Escribe algo antes de evaluar.")
    try:
        data = ai_json(
            "You are an expert but encouraging English writing teacher. Return JSON only.",
            f"Analyze this learner text:\n{text}\nReturn score out of 100, CEFR level, corrected version, strengths, errors with corrections and explanations, and 3 next-step recommendations.",
            temperature=0.3,
        )
        save_history("historial_escritura", user.id, {
            "texto": text,
            "score": data.get("score"),
            "resultado": data,
        })
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el texto: {exc}", 500)


@app.post("/evaluar-lectura")
def evaluate_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    passage = (body.get("passage") or "").strip()
    answer = (body.get("answer") or "").strip()
    if not passage or not answer:
        return json_error("Faltan la lectura o tu respuesta.")
    try:
        data = ai_json(
            "You evaluate English reading comprehension. Return JSON only and be constructive.",
            f"Passage:\n{passage}\n\nLearner's explanation in English:\n{answer}\n\nReturn score out of 100, what was understood correctly, missed ideas, language feedback, and a concise model answer.",
            temperature=0.3,
        )
        save_history("historial_lectura", user.id, {
            "score": data.get("score"),
            "resultado": data,
        })
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar la lectura: {exc}", 500)


@app.post("/evaluar-dictado")
def evaluate_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    expected = (body.get("expected") or "").strip()
    answer = (body.get("answer") or "").strip()
    if not expected or not answer:
        return json_error("Faltan el texto esperado o tu respuesta.")
    try:
        data = ai_json(
            "You are an English dictation teacher. Return JSON only.",
            f"Expected sentence:\n{expected}\n\nLearner transcription:\n{answer}\n\nReturn score out of 100, corrected transcription, missing/incorrect words, and 3 brief tips.",
            temperature=0.2,
        )
        save_history("historial_dictado", user.id, {
            "score": data.get("score"),
            "resultado": data,
        })
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el dictado: {exc}", 500)


@app.post("/api/tutor")
def tutor():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    history = body.get("history") or []
    if not message:
        return json_error("Escribe o di algo al tutor.")

    safe_history = []
    for item in history[-8:]:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str):
            safe_history.append({"role": role, "content": content[:2000]})

    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are the English Academy personal English tutor. Speak naturally in English, correct important mistakes gently, ask useful follow-up questions, and adapt to the learner's level. Keep responses concise and conversational.",
                },
                *safe_history,
                {"role": "user", "content": message},
            ],
            temperature=0.7,
        )
        reply = response.choices[0].message.content or "Let's keep practicing. Tell me more."
        save_history("historial_tutor", user.id, {
            "mensaje_usuario": message,
            "respuesta_tutor": reply,
        })
        return jsonify({"ok": True, "reply": reply})
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
    result = {}
    for key, table in tables:
        try:
            rows = (
                supabase.table(table)
                .select("*")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            ).data or []
            result[key] = rows
        except Exception as exc:
            print(f"[HISTORY READ:{table}] {exc}")
            result[key] = []
    return jsonify({"ok": True, **result})


@app.get("/api/progreso")
def progress():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    data = {"pronunciation": [], "writing": [], "reading": [], "dictation": []}
    table_map = {
        "pronunciation": "historial_pronunciacion",
        "writing": "historial_escritura",
        "reading": "historial_lectura",
        "dictation": "historial_dictado",
    }
    for key, table in table_map.items():
        try:
            rows = (
                supabase.table(table)
                .select("created_at,score")
                .eq("user_id", user.id)
                .order("created_at", desc=False)
                .limit(50)
                .execute()
            ).data or []
            data[key] = rows
        except Exception as exc:
            print(f"[PROGRESS:{table}] {exc}")
    return jsonify({"ok": True, **data})


@app.get("/")
def root():
    return jsonify({"ok": True, "service": "English Academy API"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
