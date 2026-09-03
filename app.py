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
        print("[ERROR SUPABASE]", exc)

ai_client: OpenAI | None = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    try:
        ai_client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/",
        )
        print(f"[OK] Azure OpenAI configurado: {AZURE_OPENAI_DEPLOYMENT}")
    except Exception as exc:
        print("[ERROR OPENAI]", exc)

FRASES_BASE = [
    {"frase": "I usually take a short walk after dinner.", "traduccion": "Normalmente doy un paseo corto después de cenar."},
    {"frase": "She decided to study English before starting her new job.", "traduccion": "Ella decidió estudiar inglés antes de comenzar su nuevo trabajo."},
    {"frase": "We had an interesting conversation about technology.", "traduccion": "Tuvimos una conversación interesante sobre tecnología."},
    {"frase": "Learning a language takes practice, patience, and curiosity.", "traduccion": "Aprender un idioma requiere práctica, paciencia y curiosidad."},
]
TOPICS = [
    "What are your goals for learning English?",
    "Describe a place you would love to visit.",
    "Tell me about a skill you want to improve.",
    "What makes a good friend?",
    "Describe your ideal workday.",
]
TWISTERS = [
    {"trabalenguas": "Peter Piper picked a peck of pickled peppers.", "enfoque": "/p/"},
    {"trabalenguas": "She sells seashells by the seashore.", "enfoque": "/s/ and /ʃ/"},
    {"trabalenguas": "Fresh fried fish, fish fresh fried.", "enfoque": "/f/ and /r/"},
    {"trabalenguas": "How much wood would a woodchuck chuck?", "enfoque": "/w/ and /tʃ/"},
]

def clean_json(raw):
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))

def ai_json(system, user, fallback=None):
    if not ai_client:
        if fallback is not None:
            return fallback
        raise RuntimeError("El servicio de IA no está configurado.")
    response = ai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    return clean_json(response.choices[0].message.content or "{}")

def bearer():
    value = request.headers.get("Authorization", "")
    if not value.lower().startswith("bearer "):
        return None
    return value.split(" ", 1)[1].strip() or None

def authenticated_user(required=True):
    if not supabase:
        return None, "Supabase no está configurado."
    token = bearer()
    if not token:
        return None, "Sesión requerida."
    try:
        result = supabase.auth.get_user(token)
        user = getattr(result, "user", None)
        if not user:
            return None, "La sesión no es válida o ha expirado."
        if required:
            profile = (
                supabase.table("profiles")
                .select("is_subscribed")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            if not profile.data or not profile.data.get("is_subscribed", False):
                return None, "Tu cuenta todavía no tiene acceso activo."
        return user, None
    except Exception as exc:
        print("[ERROR AUTH]", exc)
        return None, f"No fue posible validar la sesión: {exc}"

def err(message, status=400):
    return jsonify({"error": message}), status

def speech_config():
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("El servicio de voz no está configurado.")
    cfg = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    cfg.speech_recognition_language = "en-US"
    return cfg

def convert_audio(upload):
    webm = wav = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp:
        upload.save(temp.name)
        webm = temp.name
    try:
        wav = webm + "_16k.wav"
        audio = AudioSegment.from_file(webm)
        audio.set_frame_rate(16000).set_channels(1).set_sample_width(2).export(wav, format="wav")
        return webm, wav
    except Exception:
        cleanup(webm, wav)
        raise

def cleanup(*paths):
    for path in paths:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass

def word_details(result):
    raw = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
    payload = json.loads(raw) if raw else {}
    words = ((payload.get("NBest") or [{}])[0]).get("Words") or []
    inspection = {
        "omisiones": 0, "pronunciaciones_incoherentes": 0, "inserciones": 0,
        "interrupcion_inesperada": 0, "falta_un_descanso": 0, "monotona": 0,
    }
    details = []
    for item in words:
        pa = item.get("PronunciationAssessment") or {}
        error_type = pa.get("ErrorType", "None")
        score = round(float(pa.get("AccuracyScore", 0) or 0))
        if error_type == "Omission": inspection["omisiones"] += 1
        elif error_type == "Mispronunciation": inspection["pronunciaciones_incoherentes"] += 1
        elif error_type == "Insertion": inspection["inserciones"] += 1
        prosody = (pa.get("Feedback") or {}).get("Prosody") or {}
        breaks = prosody.get("Break") or {}
        errors = ((prosody.get("Intonation") or {}).get("ErrorTypes") or [])
        if "UnexpectedBreak" in breaks: inspection["interrupcion_inesperada"] += 1
        if "MissingBreak" in breaks: inspection["falta_un_descanso"] += 1
        if "Monotone" in errors: inspection["monotona"] += 1
        phonemes = []
        for p in item.get("Phonemes") or []:
            ppa = p.get("PronunciationAssessment") or {}
            phonemes.append({"fonema": p.get("Phoneme", ""), "precision": round(float(ppa.get("AccuracyScore", 0) or 0))})
        details.append({
            "palabra": item.get("Word", ""),
            "precision": score,
            "puntuacion": score,
            "error_type": error_type,
            "fonemas": phonemes,
        })
    return inspection, details

def assess_audio(wav, reference=None):
    recognizer_cfg = speech_config()
    audio_cfg = speechsdk.audio.AudioConfig(filename=wav)
    pa_cfg = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=bool(reference),
    )
    try:
        pa_cfg.enable_prosody_assessment()
    except Exception:
        pass
    recognizer = speechsdk.SpeechRecognizer(speech_config=recognizer_cfg, audio_config=audio_cfg)
    pa_cfg.apply_to(recognizer)
    result = recognizer.recognize_once_async().get()
    if result.reason == speechsdk.ResultReason.Canceled:
        details = speechsdk.CancellationDetails(result)
        raise RuntimeError(details.error_details or str(details.reason))
    if result.reason == speechsdk.ResultReason.NoMatch:
        raise ValueError("No se detectó una voz clara. Habla cerca del micrófono.")
    pr = speechsdk.PronunciationAssessmentResult(result)
    data = {
        "transcription": result.text or "",
        "puntuacion_global": round(float(pr.pronunciation_score or 0)),
        "pronunciation_score": round(float(pr.pronunciation_score or 0)),
        "precision": round(float(pr.accuracy_score or 0)),
        "accuracy_score": round(float(pr.accuracy_score or 0)),
        "fluidez": round(float(pr.fluency_score or 0)),
        "fluency_score": round(float(pr.fluency_score or 0)),
        "completitud": round(float(pr.completeness_score or 0)),
        "prosodia": round(float(pr.prosody_score or 0)),
    }
    if reference:
        data["inspeccion"], data["palabras"] = word_details(result)
    else:
        data["inspeccion"], data["palabras"] = {}, []
    return data

def save_pron_history(user_id, phrase, data):
    if not supabase:
        return
    try:
        supabase.table("historial_pronunciacion").insert({
            "user_id": user_id,
            "frase_esperada": phrase,
            "precision_fonemas": int(data.get("precision", 0)),
            "fluidez": int(data.get("fluidez", 0)),
            "completitud": int(data.get("completitud", 0)),
            "puntuacion_global": int(data.get("puntuacion_global", 0)),
        }).execute()
    except Exception as exc:
        print("[WARN HISTORY]", exc)

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "ai_configured": bool(ai_client),
        "speech_configured": bool(AZURE_SPEECH_KEY and AZURE_SPEECH_REGION),
        "supabase_configured": bool(supabase),
    })

@app.get("/api/session")
def api_session():
    user, error = authenticated_user(False)
    if error:
        return jsonify({"authenticated": False, "error": error})
    profile = supabase.table("profiles").select("is_subscribed").eq("id", user.id).maybe_single().execute()
    return jsonify({
        "authenticated": True,
        "email": user.email,
        "user_id": user.id,
        "is_subscribed": bool(profile.data and profile.data.get("is_subscribed")),
    })

@app.get("/nueva-frase")
def nueva_frase():
    fallback = random.choice(FRASES_BASE)
    try:
        return jsonify(ai_json(
            "Create useful English learning content. Return JSON only.",
            'Generate one everyday English sentence for an A2-B2 learner. Return {"frase":"English sentence","traduccion":"Spanish translation"}.',
            fallback,
        ))
    except Exception:
        return jsonify(fallback)

@app.get("/nuevo-tema-libre")
def nuevo_tema():
    fallback = {"tema": random.choice(TOPICS), "instrucciones": "Habla durante 20 a 30 segundos y desarrolla al menos tres ideas."}
    try:
        return jsonify(ai_json(
            "Create concise English speaking prompts. Return JSON only.",
            'Generate one natural speaking prompt. Return {"tema":"English prompt","instrucciones":"Short practice instructions"}.',
            fallback,
        ))
    except Exception:
        return jsonify(fallback)

@app.get("/nuevo-trabalenguas")
def nuevo_trabalenguas():
    fallback = random.choice(TWISTERS)
    try:
        return jsonify(ai_json(
            "Create concise pronunciation practice. Return JSON only.",
            'Generate one English tongue twister and its target sound. Return {"trabalenguas":"Sentence","enfoque":"Sound"}.',
            fallback,
        ))
    except Exception:
        return jsonify(fallback)

@app.get("/nuevo-texto-lectura")
def nuevo_texto_lectura():
    _, error = authenticated_user()
    if error: return err(error, 401)
    fallback = {
        "titulo": "Why small habits matter",
        "texto": "Small daily habits can have a surprising effect on long-term goals. A few minutes of reading, exercise, or language practice may seem insignificant, but repeating those actions creates steady progress over time.",
    }
    try:
        return jsonify(ai_json(
            "You are an English reading teacher. Create informative real-world style material for an intermediate learner. Never include a Spanish translation or questions. Return JSON only.",
            'Generate a 70-110 word informative English text about technology, travel, science, culture, work, environment, or everyday life. Return {"titulo":"Short title","texto":"English text"}.',
            fallback,
        ))
    except Exception:
        return jsonify(fallback)

@app.get("/nuevo-dictado")
def nuevo_dictado():
    _, error = authenticated_user()
    if error: return err(error, 401)
    fallback = {"frase": random.choice(FRASES_BASE)["frase"]}
    try:
        return jsonify(ai_json(
            "Create short listening practice. Return JSON only.",
            'Generate one natural English sentence of 7-14 words. Return {"frase":"English sentence"}.',
            fallback,
        ))
    except Exception:
        return jsonify(fallback)

@app.post("/analizar-audio-real")
@app.post("/api/assess-reading")
def analizar_audio_real():
    user, error = authenticated_user()
    if error: return err(error, 401)
    upload = request.files.get("audio")
    phrase = (request.form.get("frase_esperada") or request.form.get("reference_text") or "").strip()
    if not upload: return err("No se recibió el audio.")
    if not phrase: return err("Falta la frase de referencia.")
    webm = wav = None
    try:
        webm, wav = convert_audio(upload)
        data = assess_audio(wav, phrase)
        save_pron_history(user.id, phrase, data)
        return jsonify({"calificacion": round(data["puntuacion_global"] / 10, 1), **data})
    except ValueError as exc: return err(str(exc), 400)
    except Exception as exc:
        print("[ERROR PRON]", exc)
        return err(f"No fue posible analizar el audio: {exc}", 500)
    finally: cleanup(webm, wav)

@app.post("/api/assess-unscripted")
def assess_unscripted():
    _, error = authenticated_user()
    if error: return err(error, 401)
    upload = request.files.get("audio")
    topic = (request.form.get("topic") or request.form.get("tema") or "General conversation").strip()
    if not upload: return err("No se recibió el audio.")
    webm = wav = None
    try:
        webm, wav = convert_audio(upload)
        speech = assess_audio(wav, None)
        report = ai_json(
            "You are a supportive native English speaking coach. Analyze grammar, vocabulary and relevance from the transcript. Return JSON only.",
            json.dumps({"topic": topic, "transcript": speech["transcription"]}, ensure_ascii=False),
            {"grammar_score": 0, "vocabulary_score": 0, "topic_score": 0, "grammar_feedback": "", "vocabulary_feedback": "", "topic_feedback": "", "next_step": "Keep practicing."},
        ) if ai_client and speech["transcription"] else {}
        return jsonify({
            **speech,
            "content_assessment": report,
            "gramatica": int(report.get("grammar_score", 0) or 0),
            "vocabulario": int(report.get("vocabulary_score", 0) or 0),
            "coherencia": int(report.get("topic_score", 0) or 0),
        })
    except Exception as exc:
        print("[ERROR FREE TALK]", exc)
        return err(f"No fue posible analizar tu conversación: {exc}", 500)
    finally: cleanup(webm, wav)

@app.post("/analizar-escritura")
def analizar_escritura():
    _, error = authenticated_user()
    if error: return err(error, 401)
    text = ((request.get_json(silent=True) or {}).get("texto") or "").strip()
    if not text: return err("Escribe primero tu texto.")
    fallback = {"calificacion": 5, "gramatica": 5, "vocabulario": 5, "naturalidad": 5, "analisis": "", "correcciones": [], "version_natural": text, "siguiente_paso": "Add more detail."}
    try:
        report = ai_json(
            "You are a professional English teacher. Evaluate writing precisely and kindly. Return JSON only in Spanish with scores from 0 to 10.",
            json.dumps({"texto": text, "required_fields": ["calificacion","gramatica","vocabulario","naturalidad","analisis","correcciones","version_natural","siguiente_paso"]}, ensure_ascii=False),
            fallback,
        )
        return jsonify(report)
    except Exception as exc:
        return err(f"No fue posible evaluar tu escritura: {exc}", 500)

@app.post("/evaluar-lectura")
def evaluar_lectura():
    user, error = authenticated_user()
    if error: return err(error, 401)
    data = request.get_json(silent=True) or {}
    title = (data.get("titulo") or "").strip()
    text = (data.get("texto") or "").strip()
    answer = (data.get("respuesta") or "").strip()
    if not text or not answer: return err("Necesitamos el texto y tu explicación en inglés.")
    fallback = {"calificacion": 5, "idea_principal": 50, "detalles": 50, "vocabulario": 50, "nivel_estimado": "B1", "resumen_evaluacion": "", "aciertos": [], "faltantes": [], "vocabulario_util": [], "recomendacion": "Include the main idea and two supporting details."}
    try:
        report = ai_json(
            "You are an English reading-comprehension teacher. The learner explains the text in English from memory. Evaluate comprehension, not memorization. Return JSON only.",
            json.dumps({"titulo": title, "texto": text, "respuesta_del_estudiante": answer}, ensure_ascii=False),
            fallback,
        )
        try:
            supabase.table("historial_lectura").insert({
                "user_id": user.id, "titulo": title, "texto": text, "respuesta": answer,
                "calificacion": float(report.get("calificacion", 0) or 0),
                "nivel_estimado": report.get("nivel_estimado"), "reporte": report,
            }).execute()
        except Exception as exc:
            print("[WARN READING HISTORY]", exc)
        return jsonify(report)
    except Exception as exc:
        return err(f"No fue posible evaluar tu comprensión: {exc}", 500)

@app.post("/evaluar-dictado")
def evaluar_dictado():
    _, error = authenticated_user()
    if error: return err(error, 401)
    data = request.get_json(silent=True) or {}
    original = (data.get("original") or "").strip()
    student = (data.get("usuario") or "").strip()
    if not original or not student: return err("Escribe primero lo que escuchaste.")
    normalize = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    if normalize(original) == normalize(student):
        return jsonify({"calificacion": 10, "analisis": "¡Excelente! Escribiste la frase correctamente.", "aciertos": ["La frase coincide con el audio."], "errores": [], "consejo": "Try it again at a natural speed."})
    try:
        return jsonify(ai_json(
            "You are a listening teacher. Compare the original English sentence with the student's transcription. Return JSON only.",
            json.dumps({"original": original, "student": student}, ensure_ascii=False),
            {"calificacion": 5, "analisis": "Hay diferencias.", "aciertos": [], "errores": ["Revisa las palabras que cambiaron."], "consejo": "Listen again."},
        ))
    except Exception as exc:
        return err(f"No fue posible evaluar el dictado: {exc}", 500)

@app.get("/obtener-historial")
def historial():
    user, error = authenticated_user()
    if error: return err(error, 401)
    try:
        result = supabase.table("historial_pronunciacion").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(30).execute()
        return jsonify(result.data or [])
    except Exception as exc:
        return err(f"No fue posible cargar tu progreso: {exc}", 500)

@app.get("/api/progreso")
def progreso():
    user, error = authenticated_user()
    if error: return err(error, 401)
    rows = supabase.table("historial_pronunciacion").select("precision_fonemas,fluidez,completitud,puntuacion_global,created_at").eq("user_id", user.id).order("created_at", desc=True).limit(100).execute().data or []
    if not rows:
        return jsonify({"sesiones":0,"promedio":0,"mejor":0,"precision_promedio":0,"fluidez_promedio":0,"completitud_promedio":0,"evolucion":[]})
    avg = lambda key: round(sum(float(x.get(key,0) or 0) for x in rows)/len(rows))
    return jsonify({
        "sesiones": len(rows),
        "promedio": avg("puntuacion_global"),
        "mejor": max(int(x.get("puntuacion_global",0) or 0) for x in rows),
        "precision_promedio": avg("precision_fonemas"),
        "fluidez_promedio": avg("fluidez"),
        "completitud_promedio": avg("completitud"),
        "evolucion": [{"fecha":x.get("created_at"),"score":int(x.get("puntuacion_global",0) or 0)} for x in reversed(rows[:20])],
    })

@app.post("/api/tutor")
def tutor():
    user, error = authenticated_user()
    if error: return err(error, 401)
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    score = data.get("pronunciation_score")
    if not message: return err("Escribe o di algo para comenzar.")
    safe = [{"role":x.get("role"),"content":str(x.get("content",""))[:1500]} for x in history[-10:] if x.get("role") in {"user","assistant"}]
    try:
        report = ai_json(
            """You are the English Academy conversation coach.
Keep the conversation natural, encourage the learner to speak, adapt to level,
correct only the most useful error gently, and ask one clear follow-up question.
Never mention internal services or implementation. Return JSON only:
{"reply":"...","correction":"...","next_question":"..."}""",
            json.dumps({"message":message,"history":safe,"pronunciation_score":score}, ensure_ascii=False),
        )
        reply = str(report.get("reply") or "Tell me more.")
        correction = str(report.get("correction") or "").strip()
        question = str(report.get("next_question") or "").strip()
        combined = reply + (f"\n\nSmall correction: {correction}" if correction else "") + (f"\n\n{question}" if question else "")
        try:
            supabase.table("historial_tutor").insert({"user_id":user.id,"mensaje_usuario":message,"respuesta_tutor":combined,"pronunciation_score":score}).execute()
        except Exception as exc:
            print("[WARN TUTOR HISTORY]", exc)
        return jsonify({"reply": combined})
    except Exception as exc:
        return err(f"No fue posible continuar la conversación: {exc}", 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=False)
