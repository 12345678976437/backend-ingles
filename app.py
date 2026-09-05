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
            client = supabase_admin or supabase
            profile = (
                client.table("profiles")
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
    client = supabase_admin or supabase
    if not client:
        return
    try:
        client.table(table).insert({"user_id": user_id, **payload}).execute()
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
        "palabras": palabras,
        "inspeccion": inspeccion,
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

    is_subscribed = False
    client = supabase_admin or supabase
    if client:
        try:
            profile = (
                client.table("profiles")
                .select("is_subscribed")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            is_subscribed = bool((profile.data or {}).get("is_subscribed"))
        except Exception as exc:
            print(f"[SESSION PROFILE] {exc}")

    return jsonify({
        "authenticated": True,
        "is_subscribed": is_subscribed,
        "user": {"id": user.id, "email": user.email},
    })


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


@app.post("/analizar-escritura")
def analyze_writing():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    text = (request.get_json(silent=True) or {}).get("texto", "") or (request.get_json(silent=True) or {}).get("text", "")
    text = text.strip()
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
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el texto: {exc}", 500)


@app.post("/evaluar-lectura")
def evaluate_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    passage = (body.get("texto_original") or body.get("passage") or "").strip()
    answer = (body.get("respuesta") or body.get("answer") or "").strip()
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
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar la lectura: {exc}", 500)


@app.post("/evaluar-dictado")
def evaluate_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    expected = (body.get("texto_original") or body.get("expected") or "").strip()
    answer = (body.get("respuesta") or body.get("answer") or "").strip()
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
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(f"No se pudo evaluar el dictado: {exc}", 500)


@app.post("/api/tutor")
def tutor():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    message = (body.get("mensaje") or body.get("message") or "").strip()
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
    return jsonify({"ok": True, "service": "English Academy API"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
