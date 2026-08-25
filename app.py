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

# Inicialización del cliente global de Gemini
client = None
if GEMINI_KEY:
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        print("Cliente de Gemini AI configurado correctamente.")
    except Exception as e:
        print(f"Error al configurar cliente de Gemini: {e}")
else:
    print("ADVERTENCIA: GEMINI_API_KEY no encontrada.")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase conectado correctamente.")
    except Exception as e:
        print(f"Error al conectar Supabase: {e}")

MODELOS_GEMINI = [
    'gemini-3.6-flash',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.0-flash'
]

def generar_contenido_gemini(prompt):
    """Llama a Gemini probando de forma secuencial los modelos soportados."""
    global client
    if not client:
        return None
    
    for model_name in MODELOS_GEMINI:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            continue
    return None

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

def obtener_usuario_autenticado_y_suscrito():
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

@app.route('/nueva-frase', methods=['GET'])
def nueva_frase():
    return jsonify(random.choice(FRASES_BASE))

@app.route('/analizar-audio-real', methods=['POST'])
def analizar_audio_real():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401

        if 'audio' not in request.files:
            return jsonify({'error': 'No se envió archivo de audio.'}), 400

        audio_file = request.files['audio']
        frase_esperada = request.form.get('frase_esperada', '').strip()

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
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme
            )
            pron_config.enable_miscue = True

            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            pron_config.apply_to(recognizer)

            result = recognizer.recognize_once_async().get()

            del recognizer
            del audio_config

            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation = speechsdk.CancellationDetails(result)
                return jsonify({'error': f'Error Azure: {cancellation.reason} - {cancellation.error_details}'}), 500

            if result.reason == speechsdk.ResultReason.NoMatch:
                return jsonify({
                    'calificacion': 0.0,
                    'puntuacion_global': 0,
                    'precision': 0,
                    'fluidez': 0,
                    'completitud': 0,
                    'analisis': '### ⚠️ No se detectó voz\nAzure Speech no reconoció palabras habladas. Por favor, habla fuerte y claro cerca del micrófono.'
                })

            pron_result = speechsdk.PronunciationAssessmentResult(result)
            precision = round(pron_result.accuracy_score)
            fluidez = round(pron_result.fluency_score)
            completitud = round(pron_result.completeness_score)
            puntuacion_global = round(pron_result.pronunciation_score)
            texto_reconocido = result.text.strip() if result.text else ""

            # Filtro estricto de silencio/ruido de fondo
            if not texto_reconocido or (fluidez < 15 and completitud < 25):
                return jsonify({
                    'calificacion': 0.0,
                    'puntuacion_global': 0,
                    'precision': 0,
                    'fluidez': 0,
                    'completitud': 0,
                    'analisis': '### ⚠️ No se detectó voz\nAzure Speech no detectó suficiente audio claro para realizar la evaluación.'
                })

            # Extracción detallada palabra por palabra de Azure Speech
            palabras_detalle = []
            tabla_palabras_md = "| Palabra | Precisión | Estado Azure |\n| :--- | :---: | :--- |\n"
            
            traduccion_errores = {
                "None": "Correcta",
                "Mispronunciation": "Mal pronunciada ❌",
                "Omission": "Omitida ⚠️",
                "Insertion": "Palabra extra ➕",
                "UnexpectedBreak": "Pausa inesperada ⏸️",
                "MissingBreak": "Falta de pausa ⚡"
            }

            for w in pron_result.words:
                err_raw = str(w.error_type).split('.')[-1]
                estado_esp = traduccion_errores.get(err_raw, err_raw)
                acc_score = round(w.accuracy_score)
                
                tabla_palabras_md += f"| **{w.word}** | {acc_score}% | {estado_esp} |\n"
                
                # SE AGREGA LA CLAVE "puntuacion" PARA COMPATIBILIDAD CON EL FRONTEND
                det_palabra = {
                    "palabra": w.word,
                    "puntuacion": acc_score,
                    "precision": acc_score,
                    "error": err_raw
                }
                
                # Extracción de fonemas si existen
                if hasattr(w, 'phonemes') and w.phonemes:
                    det_palabra["fonemas"] = [
                        {"fonema": p.phoneme, "precision": round(p.accuracy_score)} 
                        for p in w.phonemes
                    ]
                
                palabras_detalle.append(det_palabra)

            calificacion_10 = round(puntuacion_global / 10, 1)

            analisis_base = (
                f"### Métricas Globales (Azure Speech)\n"
                f"* **Puntuación Global:** {puntuacion_global}/100\n"
                f"* **Precisión Fonética:** {precision}%\n"
                f"* **Fluidez:** {fluidez}%\n"
                f"* **Completitud:** {completitud}%\n\n"
                f"### Reporte Detallado por Palabra\n"
                f"{tabla_palabras_md}"
            )

            prompt = f"""
Actúa como un profesor nativo de inglés y experto en fonética.
El alumno debía decir: "{frase_esperada}".

Resultados objetivos del análisis palabra por palabra de Azure Speech:
{json.dumps(palabras_detalle, ensure_ascii=False, indent=2)}

Métricas generales:
- Precisión Fonética: {precision}%
- Fluidez: {fluidez}%
- Completitud: {completitud}%

Instrucciones para la retroalimentación:
1. Explica brevemente qué palabras fueron detectadas con error (Mispronunciation u Omission) según la lista de Azure.
2. Da un consejo técnico puntual sobre la articulación de las palabras que tuvieron menor puntaje.
3. Agrega un tip de enlazamiento (Linking/Connected speech) para mejorar el ritmo de la frase.
Responde en español de forma estructurada con Markdown.
"""
            feedback_profesor = generar_contenido_gemini(prompt)

            if feedback_profesor:
                analisis_final = f"{analisis_base}\n---\n### Explicación Fonética del Profesor\n{feedback_profesor}"
            else:
                analisis_final = analisis_base

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
                'calificacion': calificacion_10,
                'puntuacion_global': puntuacion_global,
                'precision': precision,
                'fluidez': fluidez,
                'completitud': completitud,
                'palabras': palabras_detalle,
                'analisis': analisis_final
            })

        finally:
            if temp_webm_path and os.path.exists(temp_webm_path):
                try:
                    os.remove(temp_webm_path)
                except Exception:
                    pass
            if converted_wav_path and os.path.exists(converted_wav_path):
                try:
                    os.remove(converted_wav_path)
                except Exception:
                    pass

    except Exception as e:
        return jsonify({'error': f'Error procesando audio: {str(e)}'}), 500

@app.route('/analizar-escritura', methods=['POST'])
def analizar_escritura():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401

        data = request.json or {}
        texto = data.get('texto', '').strip()
        if not texto:
            return jsonify({'error': 'Escribe una frase antes de enviar.'}), 400

        prompt = f"""
Actúa como un profesor nativo de inglés. Evalúa esta redacción:
"{texto}"

Instrucciones:
1. Asigna una calificación del 1 al 10 en la primera línea con este formato exacto: "NOTA: X/10".
2. Detalla correcciones de gramática, ortografía y vocabulario.
3. Muestra una versión mejorada y más natural.
Responde en español con formato Markdown.
"""
        res_text = generar_contenido_gemini(prompt)
        if not res_text:
            return jsonify({'error': 'No se pudo conectar con el modelo de IA.'}), 500

        calif = 7.0
        if "NOTA:" in res_text:
            try:
                calif = float(res_text.split("NOTA:")[1].split("/")[0].strip())
            except Exception:
                pass

        return jsonify({'calificacion': calif, 'analisis': res_text})
    except Exception as e:
        return jsonify({'error': f'Error procesando escritura: {str(e)}'}), 500

@app.route('/nuevo-texto-lectura', methods=['GET'])
def nuevo_texto_lectura():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401

        prompt = """
Genera una lectura en inglés de nivel intermedio (30 palabras aprox).
Devuelve ÚNICAMENTE un objeto JSON válido con este formato exacto, sin marcas de código Markdown:
{
  "titulo": "Título",
  "texto": "Texto en inglés",
  "traduccion": "Traducción en español",
  "preguntas": [
    {
      "pregunta": "Pregunta sobre el texto",
      "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"],
      "correcta": 1,
      "explicacion": "Explicación breve"
    }
  ]
}
"""
        res_text = generar_contenido_gemini(prompt)
        if res_text:
            try:
                clean_json = res_text.replace('```json', '').replace('```', '').strip()
                return jsonify(json.loads(clean_json))
            except Exception as e:
                pass

        return jsonify(LECTURA_RESPALDO)
    except Exception as e:
        return jsonify(LECTURA_RESPALDO)

@app.route('/nuevo-dictado', methods=['GET'])
def nuevo_dictado():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401
        return jsonify({'frase': random.choice(FRASES_BASE)['frase']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/evaluar-dictado', methods=['POST'])
def evaluar_dictado():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401

        data = request.json or {}
        original = data.get('original', '').strip().lower()
        usuario = data.get('usuario', '').strip().lower()

        if not usuario:
            return jsonify({'error': 'Escribe lo que escuchaste.'}), 400

        if original == usuario:
            return jsonify({
                'calificacion': 10,
                'analisis': '### ¡Excelente oído!\nEscribiste la frase exactamente como se pronunció.'
            })

        prompt = f"""
El usuario escuchó: "{original}".
Su respuesta escrita fue: "{usuario}".

Compara ambas frases en español:
1. Indica qué palabras omitió, confundió o escribió mal.
2. Proporciona una sugerencia ortográfica o auditiva breve.
Responde en Markdown.
"""
        res_text = generar_contenido_gemini(prompt)
        if res_text:
            return jsonify({'calificacion': 6, 'analisis': res_text})

        return jsonify({
            'calificacion': 5,
            'analisis': f"### Corrección\n* **Texto Correcto:** {original}\n* **Escribiste:** {usuario}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/obtener-historial', methods=['GET'])
def obtener_historial():
    try:
        user_id, err = obtener_usuario_autenticado_y_suscrito()
        if err:
            return jsonify({'error': err}), 401

        if not supabase:
            return jsonify([])

        res = supabase.table('historial_pronunciacion').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(10).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)