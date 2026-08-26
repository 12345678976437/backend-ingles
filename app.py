import os
import json
import random
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from google import genai
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
CORS(app)

# Sanitización de variables de entorno
AZURE_KEY = (os.getenv("AZURE_SPEECH_KEY") or "").strip()
AZURE_REGION = (os.getenv("AZURE_SPEECH_REGION") or "").strip()
GEMINI_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_KEY") or "").strip()

# Cliente Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado correctamente.")
    except Exception as e:
        print(f"Error al conectar Supabase: {e}")

# Cliente Gemini AI
client = None
if GEMINI_KEY:
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        print("Cliente de Gemini AI configurado correctamente.")
    except Exception as e:
        print(f"Error al configurar cliente de Gemini: {e}")

MODELOS_GEMINI = [

    'gemini-3.6-flash',

    'gemini-3.1-pro-preview'

]

# Frases y lecturas de respaldo en caso de desconexión con Gemini
FRASES_BASE = [
    {"frase": "Can I check out late today?", "traduccion": "¿Puedo salir más tarde hoy?"},
    {"frase": "Where is the nearest train station?", "traduccion": "¿Dónde está la estación de tren más cercana?"},
    {"frase": "Could you please bring me the check?", "traduccion": "¿Me trae la cuenta, por favor?"},
    {"frase": "I would like to order a cup of coffee.", "traduccion": "Me gustaría pedir una taza de café."}
]

LECTURA_RESPALDO = {
    "titulo": "The Importance of Routine",
    "texto": "Establishing a morning routine helps clear your mind and boosts productivity. Successful people often spend their first hour reading or planning their daily goals.",
    "traduccion": "Establecer una rutina matutina ayuda a despejar la mente y aumenta la productividad. Las personas exitosas suelen pasar su primera hora leyendo o planificando sus metas diarias.",
    "preguntas": [
        {
            "pregunta": "¿Qué beneficio aporta la rutina matutina según el texto?",
            "opciones": ["Ganar dinero rápido", "Despejar la mente y aumentar la productividad", "Dormir más tiempo", "Evitar hacer ejercicio"],
            "correcta": 1,
            "explicacion": "El texto menciona 'helps clear your mind and boosts productivity'."
        }
    ]
}

def generar_contenido_gemini(prompt):
    """Genera respuesta de Gemini usando la lista de modelos configurados."""
    if not GEMINI_KEY or not client:
        return None
    for model_name in MODELOS_GEMINI:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                return response.text
        except Exception:
            continue
    return None

def obtener_usuario_autenticado_y_suscrito():
    """Valida token JWT de Supabase y verífica suscripción VIP activa."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, "Acceso denegado: Token no proporcionado."
    token = auth_header.split(" ")[1]
    if not supabase:
        return None, "Error: Supabase no está configurado."
    try:
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            return None, "Sesión inválida o expirada."
        user_id = user_res.user.id
        res = supabase.table('profiles').select('is_subscribed').eq('id', user_id).execute()
        if res.data and len(res.data) > 0 and res.data[0].get('is_subscribed', False):
            return user_id, None
        return None, "Acceso restringido: Tu cuenta no tiene una suscripción VIP activa."
    except Exception as e:
        return None, f"Error de autenticación: {str(e)}"

# =============================================================
# RUTAS DE GENERACIÓN INFINITA DE CONTENIDO (GEMINI)
# =============================================================

@app.route('/nueva-frase', methods=['GET'])
def nueva_frase():
    """Genera frases cortas y útiles infinitas sin repetición."""
    prompt = """Genera una frase cotidiana en inglés para estudiantes (nivel A2-B2) con su traducción al español.
    Devuelve ÚNICAMENTE un JSON válido con este formato exacto, sin etiquetas markdown:
    {"frase": "English sentence here", "traduccion": "Traducción en español aquí"}"""
    
    res = generar_contenido_gemini(prompt)
    if res:
        try:
            clean_json = res.replace('```json', '').replace('```', '').strip()
            return jsonify(json.loads(clean_json))
        except Exception:
            pass
    return jsonify(random.choice(FRASES_BASE))

@app.route('/nuevo-texto-lectura', methods=['GET'])
def nuevo_texto_lectura():
    """Genera un texto de lectura intermedio único con preguntas de comprensión."""
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401
        
        prompt = """Genera un texto de lectura en inglés de nivel intermedio (aprox 35-45 palabras) sobre temas variados (tecnología, viajes, cultura, ciencia, estilo de vida).
        Devuelve ÚNICAMENTE un objeto JSON válido con este formato exacto, sin marcas de código Markdown:
        {"titulo": "Título corto", "texto": "Texto en inglés", "traduccion": "Traducción en español", "preguntas": [{"pregunta": "Pregunta sobre el texto", "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"], "correcta": 0, "explicacion": "Explicación breve"}]}"""
        
        res_text = generar_contenido_gemini(prompt)
        if res_text:
            try:
                clean_json = res_text.replace('```json', '').replace('```', '').strip()
                return jsonify(json.loads(clean_json))
            except Exception:
                pass
        return jsonify(LECTURA_RESPALDO)
    except Exception:
        return jsonify(LECTURA_RESPALDO)

@app.route('/nuevo-trabalenguas', methods=['GET'])
def nuevo_trabalenguas():
    """Genera trabalenguas en inglés únicos para practicar fonética."""
    prompt = """Genera un trabalenguas (tongue twister) en inglés desafiante pero claro para practicar pronunciación y articulación.
    Devuelve ÚNICAMENTE un objeto JSON válido sin formato Markdown:
    {"trabalenguas": "Sentence here", "traduccion": "Traducción al español", "enfoque": "Fonema o sonido clave a practicar (ej: /s/ and /ʃ/)"}"""
    
    res = generar_contenido_gemini(prompt)
    if res:
        try:
            clean_json = res.replace('```json', '').replace('```', '').strip()
            return jsonify(json.loads(clean_json))
        except Exception:
            pass
    return jsonify({
        "trabalenguas": "Peter Piper picked a peck of pickled peppers.",
        "traduccion": "Peter Piper recogió un bocado de pimientos encurtidos.",
        "enfoque": "Sonido consonántico /p/"
    })

@app.route('/nuevo-tema-libre', methods=['GET'])
def nuevo_tema_libre():
    """Genera temas de conversación para el modo habla libre."""
    prompt = """Genera una consigna o pregunta en inglés para una práctica de habla libre (Unscripted speech).
    Devuelve ÚNICAMENTE un JSON válido sin markdown:
    {"tema": "Describe your favorite childhood memory.", "instrucciones": "Habla durante 20 a 30 segundos explicando los detalles.", "traduccion": "Describe tu recuerdo favorito de la infancia."}"""
    
    res = generar_contenido_gemini(prompt)
    if res:
        try:
            clean_json = res.replace('```json', '').replace('```', '').strip()
            return jsonify(json.loads(clean_json))
        except Exception:
            pass
    return jsonify({
        "tema": "Talk about your favorite hobbies and why you enjoy them.",
        "instrucciones": "Habla libremente en inglés sobre tus pasatiempos.",
        "traduccion": "Habla sobre tus pasatiempos favoritos y por qué los disfrutas."
    })

@app.route('/nuevo-dictado', methods=['GET'])
def nuevo_dictado():
    """Genera frase única para ejercicio de dictado."""
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401
        
        prompt = """Genera una frase auditiva en inglés de nivel intermedio (6 a 12 palabras).
        Devuelve ÚNICAMENTE un JSON con este formato: {"frase": "Sentence in English"}"""
        
        res = generar_contenido_gemini(prompt)
        if res:
            try:
                clean_json = res.replace('```json', '').replace('```', '').strip()
                return jsonify(json.loads(clean_json))
            except Exception:
                pass
        return jsonify({'frase': random.choice(FRASES_BASE)['frase']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================
# EVALUACIÓN DE PRONUNCIACIÓN DE AZURE SPEECH (3 MODOS)
# =============================================================

@app.route('/analizar-audio-real', methods=['POST'])
@app.route('/api/assess-reading', methods=['POST'])
def analizar_audio_lectura():
    """Modo 1 y 3: Evaluación de lectura guiada y trabalenguas."""
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401

        if 'audio' not in request.files:
            return jsonify({'error': 'No se envió archivo de audio.'}), 400

        audio_file = request.files['audio']
        frase_esperada = request.form.get('frase_esperada', request.form.get('reference_text', '')).strip()

        if not AZURE_KEY or not AZURE_REGION:
            return jsonify({'error': 'Claves de Azure Speech no configuradas.'}), 500

        temp_webm_path = None
        converted_wav_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
                audio_file.save(temp_webm.name)
                temp_webm_path = temp_webm.name

            converted_wav_path = temp_webm_path + "_16k.wav"
            sound = AudioSegment.from_file(temp_webm_path)
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            sound.export(converted_wav_path, format="wav")

            speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
            speech_config.speech_recognition_language = "en-US"
            audio_config = speechsdk.audio.AudioConfig(filename=converted_wav_path)

            pron_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=frase_esperada,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True
            )
            pron_config.enable_prosody_assessment()

            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            pron_config.apply_to(recognizer)

            result = recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation = speechsdk.CancellationDetails(result)
                return jsonify({'error': f'Error Azure: {cancellation.reason} {cancellation.error_details}'}), 500

            if result.reason == speechsdk.ResultReason.NoMatch:
                return jsonify({'error': 'No se detectó voz. Habla claro y cerca del micrófono.'}), 400

            pron_result = speechsdk.PronunciationAssessmentResult(result)

            precision = round(pron_result.accuracy_score)
            fluidez = round(pron_result.fluency_score)
            completitud = round(pron_result.completeness_score)
            prosodia = round(pron_result.prosody_score)
            puntuacion_global = round(pron_result.pronunciation_score)

            json_str = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
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
                intonation_errors = prosody_feedback.get("Intonation", {}).get("ErrorTypes", [])

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
                    registro = {
                        'frase_esperada': frase_esperada,
                        'precision_fonemas': precision,
                        'fluidez': fluidez,
                        'completitud': completitud,
                        'puntuacion_global': puntuacion_global,
                        'user_id': user_id
                    }
                    supabase.table('historial_pronunciacion').insert(registro).execute()
                except Exception as e:
                    print(f"Error al guardar en Supabase: {e}")

            return jsonify({
                'calificacion': round(puntuacion_global / 10.0, 1),
                'puntuacion_global': puntuacion_global,
                'precision': precision,
                'fluidez': fluidez,
                'completitud': completitud,
                'prosodia': prosodia,
                'inspeccion': inspeccion,
                'palabras': palabras_detalle
            })

        finally:
            if temp_webm_path and os.path.exists(temp_webm_path):
                try: os.remove(temp_webm_path)
                except: pass
            if converted_wav_path and os.path.exists(converted_wav_path):
                try: os.remove(converted_wav_path)
                except: pass

    except Exception as e:
        return jsonify({'error': f'Error procesando audio: {str(e)}'}), 500

@app.route('/api/assess-unscripted', methods=['POST'])
def assess_unscripted():
    """Modo 2: Evaluación de Habla Libre (Pronunciación + Gramática, Vocabulario y Coherencia)."""
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401

        if 'audio' not in request.files:
            return jsonify({'error': 'No se envió archivo de audio.'}), 400

        audio_file = request.files['audio']
        topic = request.form.get('topic', 'General Conversation').strip()

        if not AZURE_KEY or not AZURE_REGION:
            return jsonify({'error': 'Claves de Azure Speech no configuradas.'}), 500

        temp_webm_path = None
        converted_wav_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
                audio_file.save(temp_webm.name)
                temp_webm_path = temp_webm.name

            converted_wav_path = temp_webm_path + "_16k.wav"
            sound = AudioSegment.from_file(temp_webm_path)
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            sound.export(converted_wav_path, format="wav")

            speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
            speech_config.speech_recognition_language = "en-US"
            audio_config = speechsdk.audio.AudioConfig(filename=converted_wav_path)

            json_config = {
                "GradingSystem": "HundredMark",
                "Granularity": "Phoneme",
                "EnableMiscue": False
            }
            pron_config = speechsdk.PronunciationAssessmentConfig(json_string=json.dumps(json_config))
            pron_config.enable_prosody_assessment()
            pron_config.enable_content_assessment_with_topic(topic)

            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            pron_config.apply_to(recognizer)

            result = recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation = speechsdk.CancellationDetails(result)
                return jsonify({'error': f'Error Azure: {cancellation.reason} {cancellation.error_details}'}), 500

            if result.reason == speechsdk.ResultReason.NoMatch:
                return jsonify({'error': 'No se detectó voz clara.'}), 400

            pron_result = speechsdk.PronunciationAssessmentResult(result)
            content_result = pron_result.content_assessment_result

            response = {
                "transcription": result.text,
                "pronunciation_score": round(pron_result.pronunciation_score),
                "accuracy_score": round(pron_result.accuracy_score),
                "fluency_score": round(pron_result.fluency_score),
                "prosody_score": round(pron_result.prosody_score),
                "content_assessment": {
                    "grammar_score": round(content_result.grammar_score) if content_result and content_result.grammar_score is not None else None,
                    "vocabulary_score": round(content_result.vocabulary_score) if content_result and content_result.vocabulary_score is not None else None,
                    "topic_score": round(content_result.topic_score) if content_result and content_result.topic_score is not None else None
                }
            }
            return jsonify(response)

        finally:
            if temp_webm_path and os.path.exists(temp_webm_path):
                try: os.remove(temp_webm_path)
                except: pass
            if converted_wav_path and os.path.exists(converted_wav_path):
                try: os.remove(converted_wav_path)
                except: pass

    except Exception as e:
        return jsonify({'error': f'Error procesando habla libre: {str(e)}'}), 500

# =============================================================
# EVALUACIÓN DE ESCRITURA Y DICTADO
# =============================================================

@app.route('/analizar-escritura', methods=['POST'])
def analizar_escritura():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401
        
        data = request.json or {}
        texto = data.get('texto', '').strip()
        if not texto: return jsonify({'error': 'Escribe una frase antes de enviar.'}), 400

        prompt = f"""Actúa como un profesor nativo de inglés. Evalúa esta redacción: "{texto}"
        Instrucciones:
        1. Asigna una calificación del 1 al 10 en la primera línea con este formato exacto: "NOTA: x/10".
        2. Detalla correcciones de gramática, ortografía y vocabulario.
        3. Muestra una versión mejorada y más natural.
        Responde en español con formato Markdown."""

        res_text = generar_contenido_gemini(prompt)
        if not res_text: return jsonify({'error': 'No se pudo conectar con el modelo de IA.'}), 500

        calif = 7.0
        if "NOTA:" in res_text:
            try: calif = float(res_text.split("NOTA:")[1].split("/")[0].strip())
            except: pass

        return jsonify({'calificacion': calif, 'analisis': res_text})
    except Exception as e:
        return jsonify({'error': f'Error procesando escritura: {str(e)}'}), 500

@app.route('/evaluar-dictado', methods=['POST'])
def evaluar_dictado():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401

        data = request.json or {}
        original = data.get('original', '').strip().lower()
        usuario = data.get('usuario', '').strip().lower()

        if not usuario: return jsonify({'error': 'Escribe lo que escuchaste.'}), 400

        if original == usuario:
            return jsonify({'calificacion': 10, 'analisis': '### ¡Excelente oído!\nEscribiste la frase exactamente como se pronunció.'})

        prompt = f"""El usuario escuchó: "{original}". Su respuesta escrita fue: "{usuario}".
        Compara ambas frases en español:
        1. Indica qué palabras omitió, confundió o escribió mal.
        2. Proporciona una sugerencia ortográfica o auditiva breve.
        Responde en Markdown."""

        res_text = generar_contenido_gemini(prompt)
        if res_text:
            return jsonify({'calificacion': 6, 'analisis': res_text})
        return jsonify({'calificacion': 5, 'analisis': f"**Texto Correcto:** {original}\n**Escribiste:** {usuario}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/obtener-historial', methods=['GET'])
def obtener_historial():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err: return jsonify({'error': err}), 401
        if not supabase: return jsonify([])

        res = supabase.table('historial_pronunciacion').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(10).execute()
        return jsonify(res.data if res.data else [])
    except Exception:
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)