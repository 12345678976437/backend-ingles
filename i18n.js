/* Talvo · idioma de la interfaz (EN / ES)
   Solo traduce menús, botones y avisos. El tutor y los textos de práctica
   siguen en inglés. La traducción es por texto exacto, así que nunca toca
   contenido que viene del servidor (títulos de lecturas, frases, etc.). */
(function(){
'use strict';
var PAIRS=[
/* navegación */
['Home','Inicio'],['Path','Ruta'],['Speak','Hablar'],['Tutor','Tutor'],['Menu','Menú'],
['Learn','Aprender'],['Practice','Practicar'],['Progress','Progreso'],['Account','Cuenta'],
['Learning Path','Ruta de aprendizaje'],['Pronunciation','Pronunciación'],['Writing','Escritura'],['Reading','Lectura'],['Listening','Escucha'],['Vocabulary','Vocabulario'],
['AI Tutor','Tutor IA'],['Call','Llamada'],['My Progress','Mi progreso'],['Achievements','Logros'],['Shop','Tienda'],['Admin','Admin'],
['My account','Mi cuenta'],['Notifications','Notificaciones'],['Settings','Ajustes'],['Support','Soporte'],
['Speak with confidence','Habla con confianza'],['Speak with confidence.','Habla con confianza.'],
['Not signed in','Sin sesión'],['Ready','Listo'],['Sign in','Iniciar sesión'],['Sign out','Cerrar sesión'],['Sign in to practice','Inicia sesión para practicar'],
['Close menu','Cerrar menú'],['Open menu','Abrir menú'],['Main navigation','Navegación principal'],
/* bienvenida y onboarding */
['✨ 7-day free trial, no strings attached','✨ 7 días de prueba gratis, sin compromiso'],
['Practice pronunciation, writing, reading, listening and real conversation with an AI tutor — all in one place.','Practica pronunciación, escritura, lectura, escucha y conversación real con un tutor de IA, todo en un solo lugar.'],
['🗣️ Speaking','🗣️ Hablar'],['✍️ Writing','✍️ Escritura'],['🎧 Listening','🎧 Escucha'],['🤖 AI Tutor','🤖 Tutor IA'],
['Start free trial','Empezar prueba gratis'],['I already have an account','Ya tengo una cuenta'],
['What brings you to Talvo?','¿Qué te trae a Talvo?'],['This helps us tailor your practice.','Esto nos ayuda a personalizar tu práctica.'],
['💼 Work','💼 Trabajo'],['✈️ Travel','✈️ Viajes'],['🎓 Study','🎓 Estudios'],['📝 Exams (TOEFL, IELTS...)','📝 Exámenes (TOEFL, IELTS...)'],['🌱 Personal growth','🌱 Crecimiento personal'],
['How much time can you give each day?','¿Cuánto tiempo puedes dedicar cada día?'],["We'll set this as your daily goal — you can change it later in Settings.",'Lo usaremos como tu meta diaria. Puedes cambiarla después en Ajustes.'],
['5 minutes','5 minutos'],['10 minutes','10 minutos'],['15 minutes','15 minutos'],['20 minutes','20 minutos'],['30 minutes','30 minutos'],
['How would you rate your English today?','¿Cómo calificarías tu inglés hoy?'],["Be honest — we'll adjust as you practice.",'Sé sincero, nos ajustamos mientras practicas.'],
['🌱 Beginner — I know some words and phrases','🌱 Principiante: conozco algunas palabras y frases'],
['🙂 Elementary — I can have simple conversations','🙂 Elemental: puedo tener conversaciones simples'],
['💬 Intermediate — I can talk about most everyday topics','💬 Intermedio: puedo hablar de casi todo lo cotidiano'],
["🚀 Advanced — I'm fairly fluent, polishing details",'🚀 Avanzado: hablo con fluidez, pulo detalles'],
['Not sure? Take a 2-minute level check','¿No estás seguro? Haz una prueba rápida de nivel'],
['Choose the correct option.','Elige la opción correcta.'],['Continue','Continuar'],
['Your level','Tu nivel'],
/* inicio */
['Good day! 👋','¡Buen día! 👋'],['Ready to improve your English today?','¿Listo para mejorar tu inglés hoy?'],
['Next step','Siguiente paso'],['Loading your next lesson…','Cargando tu siguiente lección…'],['Start with a free practice','Empieza con una práctica libre'],
["Today's goal","Meta de hoy"],['Continue learning','Sigue aprendiendo'],
['Practice speaking','Practica hablar'],['Write with feedback','Escribe con retroalimentación'],['Read & explain','Lee y explica'],['Listen & transcribe','Escucha y transcribe'],['Talk out loud','Habla en voz alta'],['Build your word bank','Arma tu banco de palabras'],
['Your skills','Tus habilidades'],['Recent achievements','Logros recientes'],["Today's vocabulary",'Vocabulario de hoy'],['Loading...','Cargando...'],['No words yet.','Aún no hay palabras.'],['Review words →','Repasar palabras →'],['Your vocabulary','Tu vocabulario'],
['🗣️ Speaking','🗣️ Hablar'],
/* pronunciación */
['Pronunciation Lab','Laboratorio de pronunciación'],['Speak clearly. Improve precisely.','Habla claro. Mejora con precisión.'],
['Practice a guided sentence, free speaking, a tongue twister, or work with your AI Tutor.','Practica una frase guiada, habla libre, un trabalenguas o trabaja con tu tutor IA.'],
['Guided Reading','Lectura guiada'],['Free Talk','Habla libre'],['Tongue Twisters','Trabalenguas'],
['Loading your sentence...','Cargando tu frase...'],['Or enter your own sentence','O escribe tu propia frase'],['Use sentence','Usar frase'],['New sentence','Nueva frase'],['🔊 Listen','🔊 Escuchar'],
['Loading a speaking topic...','Cargando un tema para hablar...'],['New topic','Nuevo tema'],['Loading a tongue twister...','Cargando un trabalenguas...'],['New challenge','Nuevo reto'],
['Your AI Tutor helps you practice naturally. Type or speak, then receive feedback on grammar, vocabulary, clarity, and pronunciation.','Tu tutor IA te ayuda a practicar con naturalidad. Escribe o habla y recibe retroalimentación de gramática, vocabulario, claridad y pronunciación.'],
['Start recording','Empezar a grabar'],['Analyzing...','Analizando...'],
['Omissions','Omisiones'],['Inconsistent','Inconsistentes'],['Insertions','Inserciones'],['Unexpected breaks','Pausas inesperadas'],['Missing pause','Falta de pausa'],['Monotone','Monótono'],
['Overall score','Puntuación general'],['Phonemes','Fonemas'],['Your recording','Tu grabación'],['Speaking rate','Velocidad al hablar'],
['🔊 Hear it','🔊 Escúchala'],['Practice this word','Practicar esta palabra'],['Say it, then press record.','Dila y luego presiona grabar.'],
['Phonetic accuracy','Precisión fonética'],['Fluency','Fluidez'],['Completeness','Completitud'],['Prosody','Prosodia'],['Grammar','Gramática'],
['🧭 Coach insight','🧭 Consejo del coach'],['📍 Practice in Learning Path','📍 Practicar en la Ruta'],
['Complete words','Palabras completas'],['Consistent sounds','Sonidos consistentes'],['No extra sounds','Sin sonidos extra'],['Smooth flow','Fluidez natural'],['Natural pauses','Pausas naturales'],['Good intonation','Buena entonación'],
/* escritura */
['Write with purpose.','Escribe con propósito.'],['Submit your English writing and receive focused feedback.','Envía tu escrito en inglés y recibe retroalimentación enfocada.'],
['Choose a challenge','Elige un reto'],['Easy','Fácil'],['Intermediate','Intermedio'],['Advanced','Avanzado'],["Today's challenge",'Reto de hoy'],
['Loading a challenge for you...','Cargando un reto para ti...'],['🔄 New challenge','🔄 Nuevo reto'],['Skip — write freely','Omitir y escribir libremente'],
['Your text','Tu texto'],['Write in English...','Escribe en inglés...'],['Analyze writing','Analizar escritura'],
['Overall','General'],['Vocabulary','Vocabulario'],['Coherence','Coherencia'],['Corrections','Correcciones'],['Better version','Mejor versión'],
['Could not load a challenge — write about anything you like.','No se pudo cargar un reto. Escribe sobre lo que quieras.'],['Write something first.','Escribe algo primero.'],
/* lectura y escucha */
['Read. Understand. Explain.','Lee. Entiende. Explica.'],['Read an informational English text, then explain what you understood in your own words.','Lee un texto informativo en inglés y explica con tus palabras lo que entendiste.'],
['All','Todos'],['Beginner','Principiante'],['← Back to library','← Volver a la biblioteca'],['New reading','Nueva lectura'],
['Loading reading...','Cargando lectura...'],['Explain what you understood in English','Explica en inglés lo que entendiste'],['Write what you understood. Do not copy the text.','Escribe lo que entendiste. No copies el texto.'],
['Analyze comprehension','Analizar comprensión'],['Understanding','Comprensión'],['Accuracy','Precisión'],['English quality','Calidad del inglés'],
['What you did well','Lo que hiciste bien'],['Improve next','Para mejorar'],['Suggested vocabulary','Vocabulario sugerido'],
['Listen carefully.','Escucha con atención.'],['Listen to a short English passage and write what you hear.','Escucha un fragmento corto en inglés y escribe lo que oyes.'],
['Play audio','Reproducir audio'],['New audio','Nuevo audio'],['Press play, then write what you heard.','Presiona reproducir y escribe lo que oíste.'],
['Type what you heard...','Escribe lo que oíste...'],['Evaluate listening','Evaluar escucha'],['Words matched','Palabras acertadas'],['Differences','Diferencias'],['Level','Nivel'],
['Explain what you understood first.','Primero explica lo que entendiste.'],['Write what you heard first.','Primero escribe lo que oíste.'],['Load a reading first.','Primero carga una lectura.'],['Load a dictation first.','Primero carga un dictado.'],
['No readings for this level.','No hay lecturas para este nivel.'],['No audios for this level.','No hay audios para este nivel.'],['Could not load the library.','No se pudo cargar la biblioteca.'],
['Start reading →','Empezar a leer →'],['Start →','Empezar →'],
/* vocabulario */
['Build your word bank.','Arma tu banco de palabras.'],["Learn today's words and review what you've saved.",'Aprende las palabras de hoy y repasa las que guardaste.'],
["Today's words",'Palabras de hoy'],['🔄 New words','🔄 Nuevas palabras'],['✓ Learned','✓ Aprendida'],['Mark learned','Marcar como aprendida'],['No saved words yet.','Aún no hay palabras guardadas.'],
['Saved to your vocabulary.','Guardada en tu vocabulario.'],
['Daily review','Repaso diario'],['Words come back at the right time so you remember them.','Las palabras vuelven en el momento justo para que las recuerdes.'],
['Start review','Empezar repaso'],['Nothing to review right now','Nada que repasar por ahora'],['Save words from your readings and daily list to review them here.','Guarda palabras de tus lecturas y de la lista diaria para repasarlas aquí.'],
['Show meaning','Ver significado'],['Again','Otra vez'],['Good','Bien'],['Review done!','¡Repaso terminado!'],['Come back tomorrow for more.','Vuelve mañana por más.'],
/* tutor y llamada */
['Practice with your tutor.','Practica con tu tutor.'],['A conversational English coach for realistic practice and instant feedback.','Un coach de inglés conversacional para practicar de forma realista con retroalimentación inmediata.'],
['Conversation','Conversación'],['Free talk','Habla libre'],['Speak naturally. Ask questions. Make mistakes. Improve.','Habla con naturalidad. Pregunta. Equivócate. Mejora.'],
['Speak last reply','Escuchar última respuesta'],['🎙️ Speak','🎙️ Hablar'],['Send','Enviar'],['Thinking...','Pensando...'],
['Live Call','Llamada en vivo'],['Practice like a real phone call.','Practica como en una llamada real.'],
['Hold the button, say your turn in English, and let go. Palanqueta will answer out loud.','Mantén el botón, di tu turno en inglés y suéltalo. Palanqueta responderá en voz alta.'],
['🎙️ Hold to talk','🎙️ Mantén para hablar'],['Hold the button to talk','Mantén presionado el botón para hablar'],
['Hands-free: Off','Manos libres: No'],['Hands-free: On','Manos libres: Sí'],['Hands-free listens for your voice and answers when you pause.','Manos libres escucha tu voz y responde cuando haces una pausa.'],
['Listening… speak and pause when you are done.','Escuchando… habla y haz una pausa al terminar.'],
['Hang up and see summary','Colgar y ver resumen'],['Speaking score','Puntuación al hablar'],['Pronunciation*','Pronunciación*'],
['*Pronunciation is estimated from your transcript, not a live audio analysis.','*La pronunciación se estima con tu transcripción, no con un análisis de audio en vivo.'],
['Call summary','Resumen de la llamada'],['Strengths','Fortalezas'],['Common mistakes','Errores comunes'],['Recommended vocabulary','Vocabulario recomendado'],
["Listening... release when you're done",'Escuchando... suelta cuando termines'],['Palanqueta is speaking...','Palanqueta está hablando...'],['Palanqueta is thinking...','Palanqueta está pensando...'],
['Transcribing...','Transcribiendo...'],['Generating summary...','Generando resumen...'],["I couldn't hear you well, try again",'No te escuché bien, intenta de nuevo'],
["You haven't talked to Palanqueta yet.",'Todavía no has hablado con Palanqueta.'],['Generate a sentence first.','Genera una frase primero.'],
["Your browser doesn't support audio recording.",'Tu navegador no soporta grabación de audio.'],['Your browser does not support microphone recording.','Tu navegador no soporta grabación con micrófono.'],
['Voice input is not available in this browser.','La entrada por voz no está disponible en este navegador.'],
/* progreso, logros, tienda */
['See your improvement.','Mira tu mejora.'],['Your practice history and performance trends.','Tu historial de práctica y tendencias de rendimiento.'],
['🎯 Total activities','🎯 Actividades totales'],['🗣️ Pronunciation sessions','🗣️ Sesiones de pronunciación'],['✍️ Writing tasks','✍️ Tareas de escritura'],['📖 Reading tasks','📖 Tareas de lectura'],
['Recent performance','Rendimiento reciente'],['No scores yet.','Aún no hay puntuaciones.'],['Your practice history will appear here.','Tu historial de práctica aparecerá aquí.'],
['Your achievements.','Tus logros.'],['Keep practicing to unlock them all.','Sigue practicando para desbloquearlos todos.'],['✓ Completed','✓ Completado'],
['Spend your gems.','Gasta tus gemas.'],['Earned automatically as you practice — 1 gem for every ~10 XP.','Se ganan automáticamente al practicar: 1 gema por cada ~10 XP.'],
['Streak protection','Protección de racha'],['🧊 Streak Freeze','🧊 Protector de racha'],['Automatically protects your streak if you miss exactly one day.','Protege tu racha automáticamente si faltas exactamente un día.'],
['Unlock a unit early','Desbloquea una unidad antes'],['Avatar frames','Marcos de avatar'],['Equipped','Equipado'],['Equip','Equipar'],['Done!','¡Listo!'],["Could not load today's words.",'No se pudieron cargar las palabras de hoy.'],
['No units available to unlock right now.','No hay unidades por desbloquear ahora.'],['Could not load the shop.','No se pudo cargar la tienda.'],
/* ruta */
['Your English Journey.','Tu camino en inglés.'],['Follow your path and build confidence step by step.','Sigue tu ruta y gana confianza paso a paso.'],
['← Back to path','← Volver a la ruta'],['🗣️ Speak it','🗣️ Dilo'],['✍️ Write it','✍️ Escríbelo'],['📖 Read it','📖 Léelo'],['🎧 Listen & type','🎧 Escucha y escribe'],
['Not started','Sin empezar'],['Say this out loud:','Di esto en voz alta:'],['Writing challenge:','Reto de escritura:'],['Listen carefully, then type what you hear.','Escucha con atención y escribe lo que oyes.'],
['Explain what you understood, in English','Explica en inglés lo que entendiste'],['Write your explanation...','Escribe tu explicación...'],['Submit','Enviar'],['🔊 Play','🔊 Reproducir'],
['Keep practicing — you need at least 60% to complete this topic.','Sigue practicando: necesitas al menos 60% para completar este tema.'],['✓ Already completed.','✓ Ya completado.'],
['Could not load your learning path.','No se pudo cargar tu ruta de aprendizaje.'],['No learning path units available yet.','Aún no hay unidades en la ruta.'],
/* notificaciones y ajustes */
["What's new for you.",'Novedades para ti.'],['A quick look at your streak, goals, and progress — built from your real activity.','Un vistazo a tu racha, metas y progreso, según tu actividad real.'],
["You're all caught up — nothing new right now.",'Estás al día: no hay novedades por ahora.'],['Could not load notifications.','No se pudieron cargar las notificaciones.'],
['Make it feel right.','Hazla a tu gusto.'],['A couple of preferences for how the app talks to you.','Algunas preferencias de cómo te habla la app.'],
["Auto-play tutor voice replies","Reproducir automáticamente la voz del tutor"],["Automatically read the AI Tutor's replies out loud.",'Lee en voz alta las respuestas del tutor IA.'],
['On','Sí'],['Off','No'],['Speech rate','Velocidad de voz'],['How fast Palanqueta and dictation audio sound.','Qué tan rápido suenan Palanqueta y el audio de dictado.'],['Normal','Normal'],['Slow','Lenta'],
['App color','Color de la app'],['Pick the accent color for buttons, highlights and progress. It is saved on this device.','Elige el color de acento de botones, resaltados y progreso. Se guarda en este dispositivo.'],
['Interface language','Idioma de la interfaz'],['Choose the language of menus and buttons. The tutor and practice texts stay in English.','Elige el idioma de menús y botones. El tutor y los textos de práctica siguen en inglés.'],
['Install app','Instalar app'],['Add Talvo to your home screen. It opens like a native app and loads faster.','Agrega Talvo a tu pantalla de inicio. Se abre como una app y carga más rápido.'],
['Install','Instalar'],['On iPhone: tap Share, then “Add to Home Screen”.','En iPhone: toca Compartir y luego “Agregar a pantalla de inicio”.'],
/* cuenta */
['Account status','Estado de la cuenta'],['Display name','Nombre visible'],['Profile photo','Foto de perfil'],['Save','Guardar'],['Upload photo','Subir foto'],['JPG, PNG or WEBP, max 4MB','JPG, PNG o WEBP, máx. 4MB'],
['Your name','Tu nombre'],
/* modales y estados */
['Use your Talvo English account.','Usa tu cuenta de Talvo English.'],['Create account','Crear cuenta'],['Create an account','Crear una cuenta'],['Back to sign in','Volver a iniciar sesión'],['Cancel','Cancelar'],
['Email','Correo electrónico'],['Password','Contraseña'],['Enter your email and password.','Escribe tu correo y contraseña.'],['Creating...','Creando...'],['Account created.','Cuenta creada.'],
['We could not verify your access. Please sign in again.','No pudimos verificar tu acceso. Inicia sesión de nuevo.'],['Access check failed','Falló la verificación de acceso'],['Practice access active','Acceso de práctica activo'],
['Trial ended · subscribe to continue','Prueba terminada · suscríbete para continuar'],
['Waking up the server… this can take up to a minute the first time.','Despertando el servidor… la primera vez puede tardar hasta un minuto.'],
['You are offline. Some features need internet.','Sin conexión. Algunas funciones necesitan internet.'],
['Write a sentence first.','Escribe una frase primero.'],['Custom sentence','Frase personalizada'],['Recording could not be stopped.','No se pudo detener la grabación.'],['Recording... click to stop','Grabando... toca para detener'],
['Listening...','Escuchando...'],['Type what you heard first.','Primero escribe lo que oíste.'],['Good pace','Buen ritmo'],['Fast','Rápido'],
/* comunes de cuenta/soporte/admin/llamada (originales en español) */
['$79 MXN/month','$79 MXN/mes'],['Your free trial has ended','Tu prueba gratis terminó'],['Keep practicing for only','Sigue practicando por solo'],["Here's how to activate:",'Así puedes activarte:'],
['1. Transfer $79 MXN','1. Transfiere $79 MXN'],['Bank:','Banco:'],['Card:','Tarjeta:'],['Holder:','Titular:'],['2. Send your receipt on WhatsApp','2. Manda tu comprobante por WhatsApp'],
['We activate your access within 24 hours.','Te activamos el acceso en menos de 24 horas.'],['📲 Send receipt on WhatsApp','📲 Enviar comprobante por WhatsApp'],['📲 Renew on WhatsApp','📲 Renovar por WhatsApp'],['Sign in again','Volver a iniciar sesión'],
['Your real account and subscription info.','Información real de tu cuenta y tu suscripción.'],['Email address','Correo'],['Status','Estado'],['Days left','Días restantes'],['Member since','Miembro desde'],
['Free trial','Prueba gratis'],['Active','Activa'],['Expired','Vencida'],
['You are in your free trial. When it ends, renew to keep practicing.','Estás en tu período de prueba gratuita. Al terminar, renueva para seguir practicando.'],
['Your subscription is active. Keep practicing!','Tu suscripción está activa. ¡Sigue practicando!'],
['Your trial or subscription ended. Renew for $79 MXN/month to keep access.','Tu prueba o suscripción terminó. Renueva por $79 MXN/mes para seguir con acceso.'],
['Something not working, or got an idea?','¿Algo no funciona o tienes una idea?'],['Write to us directly — we read every message.','Escríbenos directo — leemos cada mensaje.'],
['Type','Tipo'],['Report a problem','Reportar un problema'],['Feedback / suggestion','Opinión / sugerencia'],['Question about my payment or subscription','Duda sobre mi pago o suscripción'],['Other','Otro'],
['Your message','Tu mensaje'],['Send message','Enviar mensaje'],['Thanks! We got your message.','¡Gracias! Ya recibimos tu mensaje.'],
["Tell us what happened or what you'd like to see in the app...",'Cuéntanos qué pasó o qué te gustaría ver en la app...'],['Write your message before sending.','Escribe tu mensaje antes de enviar.'],
['App activity','Actividad de la app'],['Only you can see this.','Solo tú puedes ver esto.'],['Total users','Usuarios totales'],['On trial','En prueba'],['Paying','Pagando'],['Loading activity...','Cargando actividad...'],
['Forgot your password?','¿Olvidaste tu contraseña?'],['New password','Nueva contraseña'],['Enter a new password for your account.','Escribe tu nueva contraseña para tu cuenta.'],['Save new password','Guardar nueva contraseña'],
['New password (min. 6 characters)','Nueva contraseña (mín. 6 caracteres)'],['Password updated. You can now use your account.','Contraseña actualizada. Ya puedes usar tu cuenta.'],
['Name updated.','Nombre actualizado.'],['Photo updated.','Foto actualizada.'],['Write at least 2 characters.','Escribe al menos 2 caracteres.'],['The image must not exceed 4 MB.','La imagen no debe pesar más de 4 MB.'],
['Recent performance','Rendimiento reciente']
];
var en2es={},es2en={};
PAIRS.forEach(function(p){ if(!(p[0] in en2es))en2es[p[0]]=p[1]; if(!(p[1] in es2en))es2en[p[1]]=p[0]; });

var LV={beginner:['Beginner','Principiante'],elementary:['Elementary','Elemental'],intermediate:['Intermediate','Intermedio'],advanced:['Advanced','Avanzado']};
function lv(k,i){return LV[k]?LV[k][i]:k}
/* patrones con números: [regex, función]  */
var PAT_ES=[
 [/^🔥 (\d+) day streak$/,function(m){return '🔥 Racha de '+m[1]+(m[1]==='1'?' día':' días')}],
 [/^⭐ (\d+) XP · Level (\d+)$/,function(m){return '⭐ '+m[1]+' XP · Nivel '+m[2]}],
 [/^⭐ (\d+) XP$/,function(m){return '⭐ '+m[1]+' XP'}],
 [/^🏆 (\d+) \/ (\d+) unlocked$/,function(m){return '🏆 '+m[1]+' / '+m[2]+' desbloqueados'}],
 [/^📚 (\d+) words saved$/,function(m){return '📚 '+m[1]+' palabras guardadas'}],
 [/^✅ (\d+) learned$/,function(m){return '✅ '+m[1]+' aprendidas'}],
 [/^(\d+) \/ (\d+) learned$/,function(m){return m[1]+' / '+m[2]+' aprendidas'}],
 [/^💎 (\d+) gems$/,function(m){return '💎 '+m[1]+' gemas'}],
 [/^🧊 (\d+) streak freezes?$/,function(m){return '🧊 '+m[1]+(m[1]==='1'?' protector de racha':' protectores de racha')}],
 [/^🎧 (\d+) plays?$/,function(m){return '🎧 '+m[1]+(m[1]==='1'?' reproducción':' reproducciones')}],
 [/^⏱ (\d+) min read$/,function(m){return '⏱ '+m[1]+' min de lectura'}],
 [/^(\d+) words?$/,function(m){return m[1]+(m[1]==='1'?' palabra':' palabras')}],
 [/^(\d+)\/(\d+) words$/,function(m){return m[1]+'/'+m[2]+' palabras'}],
 [/^Buy — (\d+) 💎$/,function(m){return 'Comprar — '+m[1]+' 💎'}],
 [/^Unlock — (\d+) 💎$/,function(m){return 'Desbloquear — '+m[1]+' 💎'}],
 [/^Free trial · (\d+) day\(s\) left$/,function(m){return 'Prueba gratis · quedan '+m[1]+' día(s)'}],
 [/^Good (morning|afternoon|evening), (.+)! 👋$/,function(m){return {morning:'Buenos días',afternoon:'Buenas tardes',evening:'Buenas noches'}[m[1]]+', '+m[2]+'! 👋'}],
 [/^(\d+)\/(\d+) lessons( · Completed 🎉)?$/,function(m){return m[1]+'/'+m[2]+' lecciones'+(m[3]?' · Completada 🎉':'')}],
 [/^Requires (\d+) XP( \+ previous unit)?$/,function(m){return 'Requiere '+m[1]+' XP'+(m[2]?' + unidad anterior':'')}],
 [/^Recording\.\.\. (\d+)s · Click to stop$/,function(m){return 'Grabando... '+m[1]+'s · Toca para detener'}],
 [/^Focus: (.+)$/,function(m){return 'Enfoque: '+m[1]}],
 [/^Focus$/,function(){return 'Enfoque'}],
 [/^How do you want to practice "(.+)"\?$/,function(m){return '¿Cómo quieres practicar "'+m[1]+'"?'}],
 [/^(beginner|elementary|intermediate|advanced) · (\d+) min$/,function(m){return lv(m[1],1)+' · '+m[2]+' min'}],
 [/^(beginner|elementary|intermediate|advanced)$/,function(m){return lv(m[1],1)}],
 [/^Continue · (\d+)\/(\d+) lessons$/,function(m){return 'Continuar · '+m[1]+'/'+m[2]+' lecciones'}],
 [/^Question (\d+) of (\d+)$/,function(m){return 'Pregunta '+m[1]+' de '+m[2]}],
 [/^Your level: (Beginner|Elementary|Intermediate|Advanced)$/,function(m){return 'Tu nivel: '+lv(m[1].toLowerCase(),1)}],
 [/^You got (\d+) of (\d+) right\. You can keep practicing and we adjust as you go\.$/,function(m){return 'Acertaste '+m[1]+' de '+m[2]+'. Sigue practicando y nos ajustamos sobre la marcha.'}],
 [/^(\d+) words? due today$/,function(m){return m[1]+(m[1]==='1'?' palabra por repasar hoy':' palabras por repasar hoy')}],
 [/^Microphone error: (.*)$/,function(m){return 'Error de micrófono: '+m[1]}],
 [/^Voice input: (.*)$/,function(m){return 'Entrada de voz: '+m[1]}],
 [/^Almost there: (.+) is (\d+)% complete\.$/,function(m){return 'Casi lo logras: '+m[1]+' va al '+m[2]+'%.'}],
 [/^Unlocked: (.+)$/,function(m){return 'Desbloqueado: '+m[1]}],
 [/^You're on a (\d+)-day streak! Keep it going today\.$/,function(m){return '¡Llevas '+m[1]+' días de racha! Sigue hoy.'}],
 [/^Today's goal is at (\d+)% — a bit more and you're done\.$/,function(m){return 'Tu meta de hoy va al '+m[1]+'%'+': un poco más y listo.'}]
];
var PAT_EN=[
 [/^(\d+) día\(s\)$/,function(m){return m[1]+' day(s)'}],
 [/^(\d+) días$/,function(m){return m[1]+' days'}],
 [/^Error de micrófono: (.*)$/,function(m){return 'Microphone error: '+m[1]}],
 [/^🔥 Racha de (\d+) días?$/,function(m){return '🔥 '+m[1]+' day streak'}],
 [/^⭐ (\d+) XP · Nivel (\d+)$/,function(m){return '⭐ '+m[1]+' XP · Level '+m[2]}],
 [/^🏆 (\d+) \/ (\d+) desbloqueados$/,function(m){return '🏆 '+m[1]+' / '+m[2]+' unlocked'}],
 [/^📚 (\d+) palabras guardadas$/,function(m){return '📚 '+m[1]+' words saved'}],
 [/^✅ (\d+) aprendidas$/,function(m){return '✅ '+m[1]+' learned'}],
 [/^(\d+) \/ (\d+) aprendidas$/,function(m){return m[1]+' / '+m[2]+' learned'}],
 [/^💎 (\d+) gemas$/,function(m){return '💎 '+m[1]+' gems'}],
 [/^🧊 (\d+) protectores? de racha$/,function(m){return '🧊 '+m[1]+(m[1]==='1'?' streak freeze':' streak freezes')}],
 [/^🎧 (\d+) reproducci(?:ón|ones)$/,function(m){return '🎧 '+m[1]+(m[1]==='1'?' play':' plays')}],
 [/^⏱ (\d+) min de lectura$/,function(m){return '⏱ '+m[1]+' min read'}],
 [/^(\d+) palabras?$/,function(m){return m[1]+(m[1]==='1'?' word':' words')}],
 [/^(\d+)\/(\d+) palabras$/,function(m){return m[1]+'/'+m[2]+' words'}],
 [/^Comprar — (\d+) 💎$/,function(m){return 'Buy — '+m[1]+' 💎'}],
 [/^Desbloquear — (\d+) 💎$/,function(m){return 'Unlock — '+m[1]+' 💎'}],
 [/^Prueba gratis · quedan (\d+) día\(s\)$/,function(m){return 'Free trial · '+m[1]+' day(s) left'}],
 [/^(Buenos días|Buenas tardes|Buenas noches), (.+)! 👋$/,function(m){return {'Buenos días':'Good morning','Buenas tardes':'Good afternoon','Buenas noches':'Good evening'}[m[1]]+', '+m[2]+'! 👋'}],
 [/^(\d+)\/(\d+) lecciones( · Completada 🎉)?$/,function(m){return m[1]+'/'+m[2]+' lessons'+(m[3]?' · Completed 🎉':'')}],
 [/^Requiere (\d+) XP( \+ unidad anterior)?$/,function(m){return 'Requires '+m[1]+' XP'+(m[2]?' + previous unit':'')}],
 [/^Grabando\.\.\. (\d+)s · Toca para detener$/,function(m){return 'Recording... '+m[1]+'s · Click to stop'}],
 [/^Enfoque: (.+)$/,function(m){return 'Focus: '+m[1]}],
 [/^¿Cómo quieres practicar "(.+)"\?$/,function(m){return 'How do you want to practice "'+m[1]+'"?'}],
 [/^(Principiante|Elemental|Intermedio|Avanzado) · (\d+) min$/,function(m){return {Principiante:'beginner',Elemental:'elementary',Intermedio:'intermediate',Avanzado:'advanced'}[m[1]]+' · '+m[2]+' min'}],
 [/^Continuar · (\d+)\/(\d+) lecciones$/,function(m){return 'Continue · '+m[1]+'/'+m[2]+' lessons'}],
 [/^Pregunta (\d+) de (\d+)$/,function(m){return 'Question '+m[1]+' of '+m[2]}],
 [/^Tu nivel: (Principiante|Elemental|Intermedio|Avanzado)$/,function(m){return 'Your level: '+{Principiante:'Beginner',Elemental:'Elementary',Intermedio:'Intermediate',Avanzado:'Advanced'}[m[1]]}],
 [/^(\d+) palabras? por repasar hoy$/,function(m){return m[1]+(m[1]==='1'?' word due today':' words due today')}]
];
var SKIP='script,style,textarea,.msg,#phrase,#twister,#reading-text,.reading,[data-i18n-skip]';
var lang='en';

function tr(str,to){
  var core=str.replace(/^\s+|\s+$/g,'');
  if(!core)return str;
  var map=to==='es'?en2es:es2en,out=map[core];
  if(out===undefined){
    var pats=to==='es'?PAT_ES:PAT_EN;
    for(var i=0;i<pats.length;i++){var m=core.match(pats[i][0]);if(m){out=pats[i][1](m);break}}
  }
  if(out===undefined||out===core)return str;
  var at=str.indexOf(core);
  return str.slice(0,at)+out+str.slice(at+core.length);
}
function skipNode(n){var el=n.nodeType===3?n.parentElement:n;return !el||!!(el.closest&&el.closest(SKIP))}
function fixText(n){
  if(skipNode(n))return;
  var v=n.nodeValue,t=tr(v,lang);
  if(t===v)return;
  var now=Date.now();
  if(n.__tt&&now-n.__tt<150){n.__tc=(n.__tc||0)+1;if(n.__tc>3)return}else n.__tc=0;
  n.__tt=now;n.nodeValue=t;
}
function fixAttrs(el){
  if(!el.getAttribute||(el.closest&&el.closest('[data-i18n-skip]')))return;
  ['placeholder','aria-label','title'].forEach(function(a){
    var v=el.getAttribute(a);if(!v)return;
    var t=tr(v,lang);if(t!==v)el.setAttribute(a,t);
  });
}
function walk(root){
  if(root.nodeType===3){fixText(root);return}
  if(root.nodeType!==1&&root.nodeType!==9&&root.nodeType!==11)return;
  if(root.nodeType===1){fixAttrs(root);if(root.matches&&root.matches(SKIP))return}
  var w=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT,{acceptNode:function(n){
    if(n.nodeType===1){return n.matches(SKIP)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}
    return NodeFilter.FILTER_ACCEPT}});
  var n;while((n=w.nextNode())){if(n.nodeType===3)fixText(n);else fixAttrs(n)}
}
var pending=false,queue=[];
var obs=new MutationObserver(function(list){
  list.forEach(function(r){
    if(r.type==='characterData')queue.push(r.target);
    else r.addedNodes.forEach(function(n){queue.push(n)});
  });
  if(pending)return;pending=true;
  Promise.resolve().then(function(){
    pending=false;var q=queue;queue=[];
    q.forEach(function(n){if(n.isConnected)walk(n)});
  });
});
function ui(){
  document.documentElement.lang=lang;
  document.querySelectorAll('.js-lang-toggle').forEach(function(b){b.textContent=lang==='es'?'EN':'ES';b.setAttribute('aria-label',lang==='es'?'Switch to English':'Cambiar a español')});
  document.querySelectorAll('#setting-lang-bar .mode').forEach(function(b){b.classList.toggle('active',b.dataset.lang===lang)});
}
function set(l){
  lang=(l==='es')?'es':'en';
  try{localStorage.setItem('talvo_lang',lang)}catch(e){}
  obs.disconnect();walk(document.body);ui();
  obs.observe(document.body,{childList:true,subtree:true,characterData:true});
}
function initial(){
  try{var s=localStorage.getItem('talvo_lang');if(s==='es'||s==='en')return s}catch(e){}
  return /^es/i.test(navigator.language||'')?'es':'en';
}
document.addEventListener('click',function(e){
  var t=e.target.closest&&e.target.closest('.js-lang-toggle');if(t){set(lang==='es'?'en':'es');return}
  var b=e.target.closest&&e.target.closest('#setting-lang-bar .mode');if(b)set(b.dataset.lang);
});
window.TalvoI18n={set:set,get:function(){return lang},tr:function(s){return tr(s,lang)}};
set(initial());
})();
