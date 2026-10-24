/* Talvo · idioma de la interfaz (EN / ES)
   Solo traduce menús, botones y avisos. El tutor y los textos de práctica
   siguen en inglés. La traducción es por texto exacto, así que nunca toca
   contenido que viene del servidor (títulos de lecturas, frases, etc.). */
(function(){
'use strict';
var PAIRS=[
['🔥 Your streak needs you!','🔥 ¡Tu racha te necesita!'],['A quick lesson keeps your flame alive.','Una lección corta mantiene viva tu llama.'],['I missed you! 🥺','¡Te extrañé! 🥺'],['Come back with a short lesson.','Vuelve con una lección cortita.'],['Time to practice!','¡Hora de practicar!'],['Your goal for today is ready.','Tu meta de hoy está lista.'],['Almost there! ✉️','¡Casi listo! ✉️'],['Confirm your email to start your free trial.','Confirma tu correo para empezar tu prueba gratis.'],

['Reminders','Recordatorios'],['Remind me at','Recordarme a las'],['Chicken sound','Sonido de gallina'],['🔔 Send a test notification','🔔 Enviar notificación de prueba'],['Sending...','Enviando...'],['Want Palanqueta to remind you to practice?','¿Quieres que Palanqueta te recuerde practicar?'],['A short daily nudge so you keep your streak. You can turn it off anytime in My account.','Un aviso corto al día para mantener tu racha. Puedes apagarlo cuando quieras en Mi cuenta.'],['Turn on','Activar'],['Not now','Ahora no'],['Reminders on! 🔔','¡Recordatorios activados! 🔔'],['Reminders off.','Recordatorios apagados.'],['Saved','Guardado'],['Sent! Check your notifications.','¡Enviada! Revisa tus notificaciones.'],['No active device found. Turn reminders off and on again.','No hay dispositivos activos. Apaga y vuelve a activar los recordatorios.'],['On — Palanqueta will remind you to practice.','Activados: Palanqueta te recordará practicar.'],['Off — turn on to get a daily practice reminder.','Apagados: actívalos para recibir un recordatorio diario.'],['Notifications are blocked. Enable them in your browser or phone settings for this site.','Las notificaciones están bloqueadas. Actívalas en los ajustes de tu navegador o teléfono para este sitio.'],['On iPhone: tap Share → Add to Home Screen, open Talvo from there and turn on reminders.','En iPhone: toca Compartir → Añadir a pantalla de inicio, abre Talvo desde ahí y activa los recordatorios.'],['This browser does not support notifications.','Este navegador no admite notificaciones.'],['We could not connect reminders right now. Try again in a moment.','No pudimos conectar los recordatorios ahora. Intenta de nuevo en un momento.'],['We could not turn on reminders on this device.','No pudimos activar los recordatorios en este dispositivo.'],

['Surprise me','Sorpréndeme'],['No items for this level.','No hay elementos para este nivel.'],['New audio','Nuevo audio'],
['Instant feedback','Respuesta al instante'],['Voice or text','Voz o texto'],['Hands-free','Manos libres'],['Live call','Llamada en vivo'],['Daily words','Palabras del día'],['Spaced review','Repaso espaciado'],['Instant','Al instante'],['Hear it','Escúchalo'],['Real roles','Roles reales'],['Coach tips','Consejos del coach'],['Analyze','Analiza'],['Shadowing','Shadowing'],['Live subtitles','Subtítulos en vivo'],['Quick quiz','Quiz rápido'],['Script','Guion'],['Practice aloud','Practica en voz alta'],['Your goal','Tu meta'],['Custom path','Ruta a tu medida'],['Earn gems','Gana gemas'],['Rewards','Recompensas'],['Streak','Racha'],['Goals','Metas'],['Fast replies','Respuestas rápidas'],['Ideas welcome','Tus ideas cuentan'],['Secure','Seguro'],['Reminders','Recordatorios'],['Sessions','Sesiones'],['Best score','Mejor puntaje'],['Average','Promedio'],
['Hide text','Ocultar texto'],['Show text','Mostrar texto'],['Excellent understanding!','¡Excelente comprensión!'],['Good comprehension — a few details to add.','Buena comprensión, agrega algunos detalles.'],['Nice effort — read once more and look for details.','Buen esfuerzo, lee otra vez y busca detalles.'],['Good start — try reading again, slowly.','Buen comienzo, intenta leer de nuevo, despacio.'],['👆 Tap any word to hear it','👆 Toca cualquier palabra para escucharla'],['Smaller text','Texto más pequeño'],['Larger text','Texto más grande'],['Slow','Lento'],['word','palabra'],['words','palabras'],

['Listen to my text','Escuchar mi texto'],['Clear','Borrar'],['Draft saved ✓','Borrador guardado ✓'],['Clear your text?','¿Borrar tu texto?'],['Excellent writing!','¡Excelente escritura!'],['Good work — a few fixes will make it shine.','Buen trabajo, unos ajustes lo harán brillar.'],['Nice effort — let\'s fix the key points.','Buen esfuerzo, corrijamos lo importante.'],['Good start — every text makes you better.','Buen comienzo, cada texto te mejora.'],['Use this version','Usar esta versión'],['Copy','Copiar'],['Listen','Escuchar'],['Copied','Copiado'],['Could not copy','No se pudo copiar'],['Improved version loaded. Edit it and analyze again!','Versión mejorada cargada. ¡Edítala y analiza de nuevo!'],['Coherence','Coherencia'],

['Tap any word to hear it.','Toca cualquier palabra para escucharla.'],['🐢 Slow','🐢 Lento'],['Excellent — that sounded natural!','¡Excelente, sonó natural!'],['Good job — a few words to polish.','Buen trabajo, hay unas palabras por pulir.'],['Nice try — let\'s work on a few words.','Buen intento, trabajemos unas palabras.'],['Tap any word below to see its sounds.','Toca cualquier palabra de abajo para ver sus sonidos.'],['Hear the model','Escuchar el modelo'],['Practice only tricky words','Practicar solo las palabras difíciles'],['Try again','Intentar de nuevo'],['Practice your tricky words','Practica tus palabras difíciles'],

['Adaptive diagnostic test: 14–24 questions on grammar, vocabulary, reading and listening (about 6 minutes). It gets easier or harder as you answer.','Examen diagnóstico adaptativo: 14–24 preguntas de gramática, vocabulario, lectura y escucha (unos 6 minutos). Se vuelve más fácil o más difícil según respondes.'],

['Estimated CEFR level: ','Nivel CEFR estimado: '],['No more plays for this question.','Ya no hay más reproducciones en esta pregunta.'],['You can listen once more.','Puedes escuchar una vez más.'],['You can listen twice.','Puedes escuchar dos veces.'],['🔊 Listen','🔊 Escuchar'],['Grammar','Gramática'],['Vocabulary','Vocabulario'],['Reading','Lectura'],['Listening','Escucha'],

['Your level: ','Tu nivel: '],['Question ','Pregunta '],['Level ','Nivel '],['We will start from the very beginning, step by step.','Empezaremos desde cero, paso a paso.'],['Your path starts at ','Tu ruta empieza en '],[' and the earlier sections are marked as already known.',' y las secciones anteriores aparecen como ya conocidas.'],['You answered "I don\'t know" ','Respondiste "No sé" '],['that helps us place you accurately.','eso nos ayuda a ubicarte con precisión.'],['It keeps adapting to your results as you practice.','Se sigue adaptando a tus resultados mientras practicas.'],['🧭 Your path starts at','🧭 Tu ruta empieza en'],['. Earlier sections are marked as already known, and your level moves up or down automatically as you practice.','. Las secciones anteriores aparecen como ya conocidas y tu nivel sube o baja solo según cómo practiques.'],['🚀 You moved up to','🚀 Subiste a'],['🔄 We adjusted your path to','🔄 Ajustamos tu ruta a'],[' — your results were consistently excellent!',' — ¡tus resultados fueron excelentes de forma constante!'],[' so lessons feel right for you. You can climb back up anytime.',' para que las lecciones se sientan bien para ti. Puedes volver a subir cuando quieras.'],

['🤷 I don\'t know','🤷 No sé'],['Doesn\'t look right? Choose another level:','¿No te parece correcto? Elige otro nivel:'],['Already known','Ya lo dominas'],['✓ Already known','✓ Ya lo dominas'],['Review anyway','Repasar de todos modos'],['You tested above this level','Tu examen quedó por encima de este nivel'],['Continue','Continuar'],

/* navegación */
['Home','Inicio'],['Path','Ruta'],['Speak','Hablar'],['Tutor','Tutor'],['Menu','Menú'],
['Learn','Aprender'],['Practice','Practicar'],['Progress','Progreso'],['Account','Cuenta'],
['Learning Path','Ruta de aprendizaje'],['Pronunciation','Pronunciación'],['Writing','Escritura'],['Reading','Lectura'],['Listening','Escucha'],['Vocabulary','Vocabulario'],
['AI Tutor','Tutor IA'],['Call','Llamada'],['My Progress','Mi progreso'],['Achievements','Logros'],['Shop','Tienda'],['Admin','Admin'],
['My account','Mi cuenta'],['Notifications','Notificaciones'],['Settings','Ajustes'],['Support','Soporte'],
['Speak with confidence','Habla con confianza'],['Speak with confidence.','Habla con confianza.'],
['Not signed in','Sin sesión'],['Ready','Listo'],['Sign in','Iniciar sesión'],['Sign out','Cerrar sesión'],['Sign in to practice','Inicia sesión para practicar'],
['Close menu','Cerrar menú'],['Open menu','Abrir menú'],['Main navigation','Navegación principal'],
/* Studio */
['Voice Lab','Taller de voz'],['Train your voice.','Entrena tu voz.'],['Analyze your speaking, shadow native phrases, look words up and review real meetings.','Analiza tu forma de hablar, repite frases como nativo, consulta palabras y revisa reuniones reales.'],['Shadowing, dictionary, meetings','Shadowing, diccionario, reuniones'],['🎙️ Analyzer','🎙️ Analizador'],['🔁 Shadowing','🔁 Shadowing'],['📖 Dictionary','📖 Diccionario'],['🗣️ Meeting','🗣️ Reunión'],['Free-speech analyzer','Analizador de habla libre'],['🎙️ Start','🎙️ Iniciar'],['⏹ Stop','⏹ Detener'],['Analyzing…','Analizando…'],['Scoring…','Evaluando…'],['Words/min','Palabras/min'],['Variety %','Variedad %'],['🐢 Slow','🐢 Lento'],['🎙️ Repeat','🎙️ Repetir'],['Skip →','Saltar →'],['Next →','Siguiente →'],['Score','Puntaje'],['Average','Promedio'],['Session complete','Sesión completa'],['Another round','Otra ronda'],['✨ My topic','✨ Mi tema'],['Smart dictionary','Diccionario inteligente'],['Look up','Buscar'],['⭐ Save to my vocabulary','⭐ Guardar en mi vocabulario'],['🎙️ Practice saying it','🎙️ Practicar decirla'],['Synonyms:','Sinónimos:'],['Collocations:','Combinaciones:'],['Record a meeting','Graba una reunión'],['🎙️ Record','🎙️ Grabar'],['📁 Upload audio','📁 Subir audio'],['⏹ Stop & analyze','⏹ Detener y analizar'],['Useful vocabulary','Vocabulario útil'],['Action items','Acciones'],['Transcript','Transcripción'],['Words','Palabras'],['Length','Duración'],['Filler words:','Muletillas:'],['Practice these:','Practica estas:'],['Speak for at least 3 seconds.','Habla al menos 3 segundos.'],['Write a topic first.','Escribe un tema primero.'],['Saved! ⭐','¡Guardada! ⭐'],['Already in your vocabulary.','Ya está en tu vocabulario.'],['Record at least 8 seconds.','Graba al menos 8 segundos.'],
['I don\'t know my level','No conozco mi nivel'],['Take a quick placement test: 8 questions, about 2 minutes. We\'ll find your level for you.','Haz un examen rápido de nivel: 8 preguntas, unos 2 minutos. Nosotros encontramos tu nivel.'],['Start test →','Empezar examen →'],['or choose your level','o elige tu nivel'],['or','o'],
['Hi, I\'m Palanqueta!','¡Hola, soy Palanqueta!'],['I\'ll show you around Talvo in one minute. You can leave the tour at any time.','Te muestro Talvo en un minuto. Puedes salir del tutorial cuando quieras.'],['Your daily goal, streak and shortcuts live here. Start here every day.','Aquí viven tu meta diaria, tu racha y tus atajos. Empieza por aquí cada día.'],['Short lessons that adapt to your level and goal. Finish them to earn stars and XP and unlock the next steps.','Lecciones cortas que se adaptan a tu nivel y objetivo. Termínalas para ganar estrellas y XP y desbloquear los siguientes pasos.'],['Say a phrase out loud and get a score, word by word. Pick a new phrase, a free topic or a tongue twister.','Di una frase en voz alta y obtén una calificación palabra por palabra. Elige una frase nueva, un tema libre o un trabalenguas.'],['Tutor chat','Chat con el tutor'],['Chat with your AI tutor in English. Ask anything and get gentle corrections.','Conversa en inglés con tu tutor de IA. Pregunta lo que quieras y recibe correcciones amables.'],['Voice call','Llamada de voz'],['Talk to the tutor like a real phone call. It listens and answers out loud.','Habla con el tutor como en una llamada real. Te escucha y responde en voz alta.'],['Writing, Reading, Listening','Escritura, lectura y escucha'],['Write with feedback, read short texts and train your ear with dictation.','Escribe con retroalimentación, lee textos cortos y entrena el oído con dictados.'],['Save new words from anywhere and review them so they stick.','Guarda palabras nuevas desde cualquier lugar y repásalas para que se te queden.'],['Type or speak in Spanish or English and get a natural translation, with better ways to say it.','Escribe o habla en español o inglés y obtén una traducción natural, con mejores formas de decirlo.'],['Rehearse interviews, sales calls, travel and more with an AI partner who coaches you.','Ensaya entrevistas, llamadas de ventas, viajes y más con un compañero de IA que te guía.'],['Tell me what you want to achieve, like selling cheese in English, and I\'ll build a course just for you.','Dime qué quieres lograr, como vender quesos en inglés, y te armo un curso solo para ti.'],['Analyze your speaking, repeat phrases like a native, look words up and review real meetings.','Analiza tu forma de hablar, repite frases como nativo, consulta palabras y revisa reuniones reales.'],['Progress and rewards','Progreso y recompensas'],['See your history, unlock achievements and spend the gems you earn in the shop.','Mira tu historial, desbloquea logros y gasta en la tienda las gemas que ganas.'],['Your plan','Tu plan'],['Each plan has credits that renew every 5 hours. Check your usage and upgrade whenever you want.','Cada plan tiene créditos que se renuevan cada 5 horas. Revisa tu uso y mejora tu plan cuando quieras.'],['You\'re ready! 🎉','¡Estás listo! 🎉'],['Practice a little every day and I\'ll be cheering for you. You can open this tutorial again from the menu.','Practica un poco cada día y yo te echo porras. Puedes abrir este tutorial otra vez desde el menú.'],['Skip tour','Saltar tutorial'],['Next','Siguiente'],['Let\'s go!','¡Vamos!'],['Tutorial','Tutorial'],['🎓 Tutorial with Palanqueta','🎓 Tutorial con Palanqueta'],['New here?','¿Eres nuevo?'],['Let me show you around in one minute.','Te enseño todo en un minuto.'],['Not now','Ahora no'],['Show me','Muéstrame'],
['Talk about anything for up to 60 seconds. You get pronunciation, speed, filler words and weak words. Uses 2 credits.','Habla de lo que quieras hasta 60 segundos. Obtienes pronunciación, velocidad, muletillas y palabras débiles. Usa 2 créditos.'],['Meanings, pronunciation, examples and collocations in one place.','Significados, pronunciación, ejemplos y combinaciones en un solo lugar.'],['Record up to 3 minutes of a real meeting or presentation, or upload an audio file. You get a transcript, filler words, better phrasing and action items. Pro and Max plans · 6 credits.','Graba hasta 3 minutos de una reunión o presentación real, o sube un archivo de audio. Obtienes transcripción, muletillas, mejores frases y acciones. Planes Pro y Max · 6 créditos.'],['No phrases available.','No hay frases disponibles.'],['No filler words detected. Nice!','No detecté muletillas. ¡Muy bien!'],
['Learn from mini scenes.','Aprende con mini escenas.'],['Watch short everyday conversations with live subtitles, then check what you understood.','Mira conversaciones cortas de la vida diaria con subtítulos en vivo y comprueba qué entendiste.'],['Rehearse your slides in English.','Ensaya tus diapositivas en inglés.'],['Turn your slides into a spoken script and practice each one out loud.','Convierte tus diapositivas en un guion hablado y practica cada una en voz alta.'],['Short Clips','Clips cortos'],['Mini scenes with subtitles','Mini escenas con subtítulos'],['Presentations','Presentaciones'],['Rehearse your slides','Ensaya tus diapositivas'],['Watch short everyday scenes with live subtitles and test what you understood.','Mira escenas cortas de la vida diaria con subtítulos en vivo y comprueba lo que entendiste.'],['Paste your slides or upload a .pptx, get a spoken script and rehearse each slide.','Pega tus diapositivas o sube un .pptx, recibe un guion hablado y ensaya cada diapositiva.'],['▶ Play','▶ Reproducir'],['Spanish subtitles','Subtítulos en español'],['Quick check','Comprobación rápida'],['Replay','Repetir'],['Next clip →','Siguiente clip →'],['Correct! 🎉','¡Correcto! 🎉'],['Not quite, listen again.','Casi, escucha de nuevo.'],['That\'s all for now','Eso es todo por ahora'],['Come back for more clips, or make one about your own topic.','Vuelve por más clips o crea uno de tu propio tema.'],['More clips','Más clips'],['Make a clip about your topic','Crea un clip de tu tema'],['Describe a situation and I will write a new clip. Uses 1 credit.','Describe una situación y escribo un clip nuevo. Usa 1 crédito.'],['Custom clips are available from the Basic plan.','Los clips personalizados están disponibles desde el plan Básico.'],['✨ Create','✨ Crear'],['Rehearse your presentation','Ensaya tu presentación'],['Paste the text of your slides (one slide per paragraph, in Spanish or English) or upload a .pptx. I will write what to say in English and you practice each slide out loud. Uses 2 credits · Basic plan and up.','Pega el texto de tus diapositivas (una por párrafo, en español o inglés) o sube un .pptx. Yo escribo qué decir en inglés y tú practicas cada diapositiva en voz alta. Usa 2 créditos · Plan Básico en adelante.'],['✨ Create my presentation','✨ Crear mi presentación'],['📁 Upload .pptx','📁 Subir .pptx'],['Hide the script','Ocultar el guion'],['🎙️ Rehearse','🎙️ Ensayar'],['Practice again','Practicar de nuevo'],['New presentation','Nueva presentación'],['Slides practiced','Diapositivas practicadas'],['Finish','Terminar'],['Next slide →','Siguiente diapositiva →'],['Slides loaded. Review the text and tap Create.','Diapositivas cargadas. Revisa el texto y toca Crear.'],['Paste the text of your slides first.','Primero pega el texto de tus diapositivas.'],
['Studio','Taller'],['Translate live','Traduce en vivo'],['Rehearse real talks','Ensaya conversaciones reales'],['Lessons made for you','Lecciones a tu medida'],['Translator','Traductor'],['Role-play','Rol'],['My Routes','Mis rutas'],['NEW','NUEVO'],
['Live Translator','Traductor en vivo'],['Say it in any language.','Dilo en cualquier idioma.'],
['Type or speak in Spanish or English and get a natural translation instantly, with ways to say it better.','Escribe o habla en español o inglés y obtén al instante una traducción natural, con formas de decirlo mejor.'],
['Role-play Coach','Coach de rol'],['Rehearse the real conversation.','Ensaya la conversación real.'],
['Practice job interviews, sales calls, travel and more with an AI partner that coaches you as you speak.','Practica entrevistas, ventas, viajes y más con un compañero de IA que te va entrenando mientras hablas.'],
['A course made just for you.','Un curso hecho para ti.'],
['Tell us what you want to achieve in English and we will build your own lessons and conversation practice.','Cuéntanos qué quieres lograr en inglés y armamos tus propias lecciones y práctica de conversación.'],
['Text','Texto'],['Auto-detect','Detectar idioma'],['Spanish → English','Español → Inglés'],['English → Spanish','Inglés → Español'],['Neutral','Neutral'],['Formal','Formal'],['Casual','Casual'],
['Direction','Dirección'],['Tone','Tono'],['Listen','Escuchar'],['Copy','Copiar'],['Text to translate','Texto a traducir'],['Message','Mensaje'],
['Type or tap the mic and speak…','Escribe o toca el micrófono y habla…'],['Translate','Traducir'],['Clear','Borrar'],['Translate as I type','Traducir mientras escribo'],
['Each translation uses 0.3 credits from your plan. Voice uses your browser, so it is free.','Cada traducción gasta 0.3 créditos de tu plan. La voz usa tu navegador, así que es gratis.'],
['🇲🇽 I speak Spanish','🇲🇽 Hablo español'],['🇺🇸 They speak English','🇺🇸 Ellos hablan inglés'],['Read translations aloud','Leer traducciones en voz alta'],
['Pick who is talking, tap the mic and start. Each phrase is translated for the other person.','Elige quién habla, toca el micrófono y empieza. Cada frase se traduce para la otra persona.'],
['Or type here…','O escribe aquí…'],['Send','Enviar'],['Other ways to say it','Otras formas de decirlo'],['Literal:','Literal:'],
['⭐ Save to vocabulary','⭐ Guardar en vocabulario'],['Saved to your vocabulary','Guardado en tu vocabulario'],['Copied','Copiado'],
['Microphone blocked. Allow it in your browser settings.','Micrófono bloqueado. Permítelo en los ajustes del navegador.'],
['I did not hear anything. Try again.','No escuché nada. Inténtalo de nuevo.'],['Could not use the microphone.','No se pudo usar el micrófono.'],
['Voice input is not available in this browser.','La entrada de voz no está disponible en este navegador.'],
['All','Todos'],['Work','Trabajo'],['Travel','Viajes'],['Daily life','Vida diaria'],
['Create your own','Crea el tuyo'],['Describe any situation and the coach will play the other person.','Describe cualquier situación y el coach hará de la otra persona.'],
['🔒 Pro','🔒 Pro'],['🔒 Basic','🔒 Básico'],['This scenario is available from the Basic plan.','Este escenario está disponible desde el plan Básico.'],
['Creating your own situations is a Pro feature.','Crear tus propias situaciones es una función del plan Pro.'],
['Each message you send uses 1 credit and the final report uses 3. Voice uses your browser, so it is free.','Cada mensaje que envías gasta 1 crédito y el reporte final 3. La voz usa tu navegador, así que es gratis.'],
['← Back','← Volver'],['What do you want to practice?','¿Qué quieres practicar?'],
['E.g. I want to ask my boss for a raise · I need to return a broken laptop at a store','Ej. Quiero pedirle un aumento a mi jefe · Necesito devolver una laptop rota en una tienda'],
['Create situation','Crear situación'],['Reply in English…','Responde en inglés…'],['Your reply','Tu respuesta'],
['💡 Hint','💡 Pista'],['Finish & get feedback','Terminar y ver mi evaluación'],['Send a message first to get a hint.','Envía un mensaje primero para recibir una pista.'],
['Leave this conversation? You will lose it.','¿Salir de esta conversación? Se perderá.'],
['Goal reached! Tap Finish to see your feedback.','¡Meta lograda! Toca Terminar para ver tu evaluación.'],
['Great practice! Tap Finish to see your feedback.','¡Buena práctica! Toca Terminar para ver tu evaluación.'],
['Try:','Prueba:'],['Use it','Usarla'],['Palanqueta is reviewing your conversation…','Palanqueta está revisando tu conversación…'],
['Goal achieved 🎉','Meta lograda 🎉'],['Keep practicing 💪','Sigue practicando 💪'],['Fluency','Fluidez'],['Grammar','Gramática'],
['Strengths','Fortalezas'],['Say it better','Dilo mejor'],['Useful phrases','Frases útiles'],['Try again','Intentar de nuevo'],['More scenarios','Más escenarios'],['Save','Guardar'],
['What do you want to achieve in English?','¿Qué quieres lograr en inglés?'],
['E.g. I sell artisan cheese and I want to hold a sales conversation in English','Ej. Vendo quesos artesanales y quiero tener una conversación de venta en inglés'],
['✨ Create my route','✨ Crear mi ruta'],['Your routes','Tus rutas'],
['Palanqueta is gathering the right words for you…','Palanqueta está juntando las palabras justas para ti…'],
['Writing lessons about your situation…','Escribiendo lecciones sobre tu situación…'],
['Preparing dialogs and practice phrases…','Preparando diálogos y frases de práctica…'],
['Almost ready — polishing your route…','Casi lista — puliendo tu ruta…'],
['Tell me a bit more: what do you want to achieve, and where?','Cuéntame un poco más: ¿qué quieres lograr y dónde?'],
['You reached your route limit. Delete one or upgrade your plan.','Llegaste al límite de rutas. Elimina una o sube de plan.'],
['Your route is ready! 🎉','¡Tu ruta está lista! 🎉'],['← My routes','← Mis rutas'],['Ready','Listo'],
['Finish the previous lesson','Termina la lección anterior'],['Complete the previous lesson first.','Completa la lección anterior primero.'],
['🎭 Practice the real conversation','🎭 Practicar la conversación real'],['📖 Words','📖 Palabras'],['🗑 Delete','🗑 Eliminar'],
['Delete this route and its progress?','¿Eliminar esta ruta y su progreso?'],['Route deleted','Ruta eliminada'],['Back to my route','Volver a mi ruta'],
['🏆 Route completed! +','🏆 ¡Ruta completada! +'],
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
['Type what you heard...','Escribe lo que oíste...'],['Evaluate listening','Evaluar escucha'],['Words matched','Palabras acertadas'],['Differences','Diferencias'],['Level','Nivel'],['Not your level? Change it:','¿No es tu nivel? Cámbialo:'],['Level updated','Nivel actualizado'],
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
['Live Call','Llamada en vivo'],
["Tap Start call and just talk. Palanqueta listens, answers out loud, and keeps the conversation going like a real phone call.","Toca Iniciar llamada y habla. Palanqueta te escucha, responde en voz alta y sigue la conversación como en una llamada real."],
['📞 Start call','📞 Iniciar llamada'],['🎙️ Mute','🎙️ Silenciar'],['🔇 Unmute','🔇 Activar micrófono'],['⏭ Skip','⏭ Saltar'],
['Tap Start call and just talk.','Toca Iniciar llamada y habla.'],['Listening… let go when you are done.','Escuchando… suelta cuando termines.'],
['Palanqueta is thinking…','Palanqueta está pensando…'],['Palanqueta is speaking…','Palanqueta está hablando…'],['Transcribing…','Transcribiendo…'],
['I did not catch that, try again.','No te escuché bien, intenta de nuevo.'],['Muted','Silenciado'],['Ready','Listo'],['Hands-free','Manos libres'],['Push to talk','Mantén para hablar'],
['Unmute first to talk.','Activa el micrófono primero.'],['You: ','Tú: '],
["Hi! I'm Palanqueta. Tap Start call and let's talk. I'll answer out loud.","¡Hola! Soy Palanqueta. Toca Iniciar llamada y platiquemos. Te responderé en voz alta."],['Practice like a real phone call.','Practica como en una llamada real.'],
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
['Loading…','Cargando…'],['Palanqueta is hard at work gathering your learning…','Palanqueta está recopilando fuertemente tu aprendizaje…'],['Picking the best words for you…','Eligiendo las mejores palabras para ti…'],['Warming up your lesson…','Calentando tu lección…'],['Almost there, hang on…','Ya casi, aguanta…'],['Teaching the hen a new trick…','Enseñándole un truco nuevo a la gallina…'],
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
['Recent performance','Rendimiento reciente'],
/* ruta de aprendizaje v2 */
['Short lessons that adapt to your level and goal. Finish them to earn stars, XP and unlock the next steps.','Lecciones cortas que se adaptan a tu nivel y objetivo. Termínalas para ganar estrellas, XP y desbloquear los siguientes pasos.'],
['Stars','Estrellas'],['Today','Hoy'],['Start','Comenzar'],['Review','Repaso'],['Refresh what you learned','Refresca lo aprendido'],
['Sound Lab','Laboratorio de sonidos'],['🎙️ Sound Lab','🎙️ Laboratorio de sonidos'],['For your goal','Para tu objetivo'],['Retry','Reintentar'],
['Picked for your level','Elegida para tu nivel'],['Next in your path','Lo siguiente en tu ruta'],
['🔒 Unlocks when you finish 60% of the previous section.','🔒 Se desbloquea al completar el 60% de la sección anterior.'],
['Finish the previous section or unlock it with gems in the Shop.','Termina la sección anterior o desbloquéala con gemas en la Tienda.'],
['Complete the previous lesson first.','Completa primero la lección anterior.'],
['Check','Comprobar'],['New sound','Sonido nuevo'],['New words','Palabras nuevas'],
['What does it mean?','¿Qué significa?'],['Choose the English word','Elige la palabra en inglés'],['Tap what you hear','Toca lo que escuchas'],
['Choose the best reply','Elige la mejor respuesta'],['Complete the sentence','Completa la frase'],['Translate this sentence','Traduce esta frase'],
['Type what you hear','Escribe lo que escuchas'],['Write it in English','Escríbelo en inglés'],['Match the pairs','Une las parejas'],
['Say the word','Di la palabra'],['Say it out loud','Dilo en voz alta'],['Tap the mic and speak','Toca el micrófono y habla'],
['Listening... tap to stop','Escuchando... toca para detener'],['Analyzing your pronunciation...','Analizando tu pronunciación...'],
["I can't speak now",'No puedo hablar ahora'],['Type in English...','Escribe en inglés...'],
['Great!','¡Genial!'],['Nice!','¡Bien!'],['Perfect!','¡Perfecto!'],['Well done!','¡Bien hecho!'],['Exactly!','¡Exacto!'],['Not quite','Casi'],
['Correct:','Correcto:'],['Tiny typo · correct:','Pequeño error de escritura · correcto:'],
['Matched!','¡Unidas!'],['Matched, with some slips','Unidas, con algunos errores'],['No mistakes','Sin errores'],
['Excellent','Excelente'],['Good — keep it up','Bien, sigue así'],['Keep trying','Sigue intentando'],
['Great speaking!','¡Gran pronunciación!'],['Needs more practice','Necesita más práctica'],['We saved this phrase for review.','Guardamos esta frase para repasarla.'],
['Nice sound!','¡Buen sonido!'],['Keep practicing this one','Sigue practicando este'],['You can retry or continue','Puedes reintentar o continuar'],
['Continue anyway','Continuar de todos modos'],['Try again — listen first, then record.','Inténtalo otra vez: escucha primero y luego graba.'],
['Microphone blocked. Allow it in your browser, or skip.','Micrófono bloqueado. Permítelo en tu navegador o sáltalo.'],
['Could not use the microphone.','No se pudo usar el micrófono.'],['Something went wrong. Try again.','Algo salió mal. Inténtalo de nuevo.'],
['I could not hear you. Try again, a little closer to the mic.','No te escuché. Inténtalo de nuevo, un poco más cerca del micrófono.'],
['Your browser does not support microphone recording.','Tu navegador no permite grabar con el micrófono.'],
['Saving your progress...','Guardando tu progreso...'],['Could not save','No se pudo guardar'],['Try again','Intentar de nuevo'],
['Review complete','Repaso completo'],['Sound practice','Práctica de sonido'],['🔥 21-day challenge','🔥 Reto de 21 días'],['🔥 New · 21-day challenge','🔥 Nuevo · Reto de 21 días'],['Speak real English in 3 weeks.','Habla inglés real en 3 semanas.'],['A fixed plan of 21 short days built around your goal. It adapts to your level, your mistakes and your pace.','Un plan fijo de 21 días cortos hecho para tu meta. Se adapta a tu nivel, a tus errores y a tu ritmo.'],['📅 One day at a time','📅 Un día a la vez'],['🎯 Built for your goal','🎯 Hecho para tu meta'],['🧠 Adapts to you','🧠 Se adapta a ti'],['Start my 21 days','Empezar mis 21 días'],['Continue challenge →','Continuar el reto →'],['Day','Día'],['Done','Hecho'],['No routes yet','Aún no tienes rutas'],['Describe your goal on the right and Palanqueta will build your first course.','Describe tu meta a la derecha y Palanqueta armará tu primer curso.'],['Build a custom route','Crea una ruta a tu medida'],['Lessons made for your real situation','Lecciones hechas para tu situación real'],['Tell Palanqueta your goal.','Cuéntale tu meta a Palanqueta.'],['The more specific, the better your 21 days will fit you.','Mientras más específico, mejor se ajustarán tus 21 días.'],['E.g. I work in customer service and I need to talk with English-speaking clients','Ej. Trabajo en atención a clientes y necesito hablar con clientes en inglés'],['Time per day','Tiempo por día'],['Auto','Auto'],['🔥 Create my challenge','🔥 Crear mi reto'],['How it works','Cómo funciona'],['3 weeks, 21 days.','3 semanas, 21 días.'],['Survive → Interact → Perform.','Sobrevive → Interactúa → Desenvuélvete.'],['One day at a time.','Un día a la vez.'],['A new day opens every morning, so you build the habit.','Cada mañana se abre un nuevo día, así formas el hábito.'],['It adapts.','Se adapta.'],['Level, difficulty and review words change with your results.','El nivel, la dificultad y las palabras de repaso cambian según tus resultados.'],['Days 7, 14 and 21','Los días 7, 14 y 21'],['are milestones with real-life practice.','son hitos con práctica de la vida real.'],['Palanqueta is designing your 21 days…','Palanqueta está diseñando tus 21 días…'],['Your challenge is ready! 🔥','¡Tu reto está listo! 🔥'],['Your path','Tu camino'],['▶ Continue','▶ Continuar'],['Route complete','Ruta completa'],['Great job! 🎉','¡Buen trabajo! 🎉'],['🎭 Real conversation','🎭 Conversación real'],['Practice the real situation out loud with an AI partner.','Practica la situación real en voz alta con una IA.'],['Start the role-play','Empezar el role-play'],['📖 Key words','📖 Palabras clave'],['🗑 Delete route','🗑 Eliminar ruta'],['🗑 Delete challenge','🗑 Eliminar reto'],['Opens tomorrow','Se abre mañana'],['Week 1','Semana 1'],['Week 2','Semana 2'],['Week 3','Semana 3'],['Survive','Sobrevive'],['Interact','Interactúa'],['Perform','Desenvuélvete'],['🧠 Adapted for you','🧠 Adaptado para ti'],['Practice your real situation out loud.','Practica tu situación real en voz alta.'],['⏳ Opens tomorrow. One day at a time builds the habit.','⏳ Se abre mañana. Un día a la vez forma el hábito.'],['🔒 Finish the previous day first.','🔒 Termina primero el día anterior.'],['This day opens tomorrow. One day at a time!','Este día se abre mañana. ¡Un día a la vez!'],['Palanqueta is preparing your day…','Palanqueta está preparando tu día…'],['▶ Start today','▶ Empezar hoy'],['done','hecho'],['lessons','lecciones'],['custom route','ruta personalizada'],
['Real English: people say “gonna”, “wanna” and “gotta” all the time. “I\'m gonna go” = “I am going to go”.','Inglés real: la gente dice “gonna”, “wanna” y “gotta” todo el tiempo. “I\'m gonna go” = “I am going to go” (voy a ir).'],['Real English: natives blend words. “What do you want?” often sounds like “Whaddya want?”. Listen to the rhythm, not word by word.','Inglés real: los nativos unen las palabras. “What do you want?” suena como “Whaddya want?”. Escucha el ritmo, no palabra por palabra.'],['Real English: “I don\'t know” usually sounds like “I dunno”. You\'ll hear it everywhere.','Inglés real: “I don\'t know” casi siempre suena como “I dunno”. Lo oirás en todas partes.'],['Real English: if you don\'t catch something, say “Sorry, could you say that again?” or “Come again?”. Nobody minds.','Inglés real: si no entendiste algo, di “Sorry, could you say that again?” o “Come again?”. A nadie le molesta.'],['Real English: “How\'s it going?” and “What\'s up?” are greetings, not real questions. A quick “Good, you?” is enough.','Inglés real: “How\'s it going?” y “What\'s up?” son saludos, no preguntas de verdad. Un rápido “Good, you?” basta.'],['Real English: in the US a T between vowels sounds almost like a D. “Water” ≈ “wader”, “better” ≈ “bedder”.','Inglés real: en EE. UU. la T entre vocales suena casi como D. “Water” ≈ “wader”, “better” ≈ “bedder”.'],['Real English: at a restaurant people say “Can I get a…?” more than “I would like…”.','Inglés real: en un restaurante se dice más “Can I get a…?” que “I would like…”.'],['Real English: “Yeah, no worries” and “No problem” are the everyday answers to “thank you”.','Inglés real: “Yeah, no worries” y “No problem” son las respuestas de todos los días a “thank you”.'],['Real English: “Let me know” and “Sounds good” are the glue of daily conversation. Use them.','Inglés real: “Let me know” y “Sounds good” son el pegamento de la conversación diaria. Úsalas.'],['Real English: native speakers talk fast because they link sounds: “check it out” ≈ “che-ki-dout”. Slow audio helps; then try normal speed.','Inglés real: los nativos hablan rápido porque enlazan sonidos: “check it out” ≈ “che-ki-dout”. El audio lento ayuda; luego prueba a velocidad normal.'],['Real English: “Kind of” and “sort of” (“kinda”, “sorta”) soften almost everything: “It\'s kinda expensive”.','Inglés real: “Kind of” y “sort of” (“kinda”, “sorta”) suavizan casi todo: “It\'s kinda expensive” (está medio caro).'],['Nice! That\'s exactly how people say it.','¡Bien! Así lo dice la gente.'],['You got it. Keep that rhythm!','Lo tienes. ¡Sigue con ese ritmo!'],['Clean. That one\'s yours now.','Limpio. Esa ya es tuya.'],['Perfect — that\'s real, everyday English.','Perfecto: eso es inglés real, de todos los días.'],['Yes! Your ear is getting sharper.','¡Sí! Tu oído se está afinando.'],['No worries — mistakes are how it sticks. I\'ll bring it back.','Tranquilo: equivocarse es como se queda. La traigo de vuelta.'],['Close! Read the correct one below and say it out loud once.','¡Cerca! Lee la correcta abajo y dila en voz alta una vez.'],['That one trips everyone. It will come back in a moment.','A todos nos pasa con esa. Volverá en un momento.'],['Good try. Listen again, then keep going.','Buen intento. Escucha otra vez y sigue.'],['Words in this lesson','Palabras de esta lección'],['In a row','Seguidas'],
['Native speed','Velocidad nativa'],['⚡ This one has no big reductions — just speed and rhythm. Try repeating it at the same pace.','⚡ Esta casi no tiene reducciones: solo velocidad y ritmo. Intenta repetirla al mismo paso.'],
['Show all tools','Mostrar todas las herramientas'],['Show fewer tools','Mostrar menos herramientas'],['Speak real English in 3 weeks','Habla inglés real en 3 semanas'],['A fixed plan built around your goal. It adapts to you.','Un plan fijo hecho para tu meta. Se adapta a ti.'],['Your plan adapts to your level and mistakes.','Tu plan se adapta a tu nivel y a tus errores.'],['Continue →','Continuar →'],
['🎧 Listening check','🎧 Examen de escucha'],['How well you catch native-speed English (days 1, 7, 14, 21).','Qué tanto entiendes inglés a velocidad nativa (días 1, 7, 14 y 21).'],['🎧 Listening check: native speed, like real life. Don\'t translate word by word — catch the meaning.','🎧 Examen de escucha: velocidad nativa, como en la vida real. No traduzcas palabra por palabra: capta el sentido.'],
['🗺️ Course path','🗺️ Camino del curso'],['🧭 My routes','🧭 Mis rutas'],
['Challenge complete','Reto completado'],['Lesson complete','Lección completada'],
['Flawless!','¡Impecable!'],['Excellent!','¡Excelente!'],['Almost there','Casi lo logras'],['Accuracy','Precisión'],['Time','Tiempo'],['Back to path','Volver a la ruta'],
['You need at least 60% to pass. You can retry as many times as you want — no hearts, no penalty.','Necesitas al menos 60% para aprobar. Puedes reintentar las veces que quieras: sin vidas ni castigos.'],
['Progress saved. Spend a little more time per lesson to earn XP.','Progreso guardado. Dedica un poco más de tiempo por lección para ganar XP.'],
['Worth a second look','Vale la pena repasar'],['Worth a second look · saved to your vocabulary','Vale la pena repasar · guardado en tu vocabulario'],
['Sorted by your weakest sounds, based on your real speaking history.','Ordenados por tus sonidos más débiles, según tu historial real de pronunciación.'],
['Start with the sounds that are hardest for Spanish speakers. As you practice speaking, this list adapts to you.','Empieza por los sonidos más difíciles para hispanohablantes. Mientras practiques hablando, esta lista se adapta a ti.'],
['New','Nuevo'],['Quit this lesson? Your progress in it will be lost.','¿Salir de la lección? Perderás tu avance en ella.'],
['Up next','Siguiente'],['Start with a free practice','Empieza con una práctica libre'],
['beginner','principiante'],['elementary','elemental'],['intermediate','intermedio'],['advanced','avanzado'],
['Travel','Viajes'],['Study','Estudio'],['Exams','Exámenes'],['Personal growth','Crecimiento personal'],
['🎯 Today\'s plan','🎯 Plan de hoy'],['Finish all steps to earn +15 bonus XP.','Completa todos los pasos para ganar +15 XP de bonus.'],
['🎉 Plan complete — bonus earned today.','🎉 Plan completo: bonus ganado hoy.'],['Plan complete!','¡Plan completo!'],
['Today\'s plan complete','Plan de hoy completo'],['🎉 Keep going with your path','🎉 Sigue avanzando en tu ruta'],
['Warm-up: tricky words','Calentamiento: palabras difíciles'],['Refresh what you learned','Refresca lo aprendido'],
['Focus: Speaking','Enfoque: Hablar'],['Focus: Listening','Enfoque: Escuchar'],['Focus: Writing','Enfoque: Escribir'],['Focus: Reading','Enfoque: Leer'],['Focus: Vocabulary','Enfoque: Vocabulario'],
['Build this skill today','Fortalece esta habilidad hoy'],
['🎯 Personalized practice','🎯 Práctica personalizada'],['📍 Open Learning Path','📍 Abrir Ruta de aprendizaje'],['Personalized practice','Práctica personalizada'],
['Personalized for you','Personalizado para ti'],['Preparing your practice...','Preparando tu práctica...'],['Back','Volver'],
['🎯 Daily plan complete! +15 bonus XP','🎯 ¡Plan del día completo! +15 XP de bonus'],
['Repeat phrases you already know until they flow. Fluency comes from rhythm, not speed.','Repite frases que ya conoces hasta que fluyan. La fluidez viene del ritmo, no de la velocidad.'],
['Train your ear with words and phrases from your own lessons, plus the ones you missed.','Entrena tu oído con palabras y frases de tus lecciones, más las que fallaste.'],
['Build and type sentences from your own lessons. Grammar sticks when you produce it.','Arma y escribe frases de tus lecciones. La gramática se fija cuando la produces.'],
['Mixed comprehension practice using what you have learned and what you missed.','Práctica mixta de comprensión con lo que aprendiste y lo que fallaste.'],
['Recall the words that gave you trouble, in different ways, until they stick.','Recuerda las palabras que te costaron, de distintas formas, hasta que se queden.']
,['Your word bank','Tu banco de palabras'],['Short daily sessions work better than long ones.','Las sesiones cortas y diarias funcionan mejor que las largas.'],
['Word','Palabra'],['Meaning','Significado'],['Tap the card to flip it','Toca la tarjeta para voltearla'],['Flip card','Voltear tarjeta'],['Hear it','Escúchala'],
['Easy','Fácil'],['Practice 10 more','Practicar 10 más'],['My words','Mis palabras'],['Search your words','Busca entre tus palabras'],
['Learning','En aprendizaje'],['Learned','Aprendidas'],['Show more','Ver más'],['Loading','Cargando'],
["That's plenty for today — review these first!",'¡Ya son suficientes por hoy! Primero repasa estas.'],
['No se pudo reproducir el audio. Revisa el volumen de tu teléfono.','Could not play the audio. Check your phone volume.']
];
var en2es={},es2en={};
PAIRS.forEach(function(p){ var a=p[0].trim(),b=p[1].trim(); if(!(a in en2es))en2es[a]=b; if(!(b in es2en))es2en[b]=a; });

var LV={beginner:['Beginner','Principiante'],elementary:['Elementary','Elemental'],intermediate:['Intermediate','Intermedio'],advanced:['Advanced','Avanzado']};
function lv(k,i){return LV[k]?LV[k][i]:k}
/* patrones con números: [regex, función]  */
var PAT_ES=[
 [/^Turn (\d+) of (\d+)$/,function(m){return 'Turno '+m[1]+' de '+m[2]}],
 [/^Best (\d+)%$/,function(m){return 'Mejor '+m[1]+'%'}],
 [/^(A1|A2|B1|B2) · (\d+)\/(\d+) lessons · ★ (\d+)$/,function(m){return m[1]+' · '+m[2]+'/'+m[3]+' lecciones · ★ '+m[4]}],
 [/^(\d+)\/(\d+) lessons · (A1|A2|B1|B2)$/,function(m){return m[1]+'/'+m[2]+' lecciones · '+m[3]}],
 [/^Your plan: (.+) · (\d+)\/(\d+) routes · up to (\d+) lessons · 4 credits$/,function(m){return 'Tu plan: '+m[1]+' · '+m[2]+'/'+m[3]+' rutas · hasta '+m[4]+' lecciones · 4 créditos'}],
 [/^🏆 Route completed! \+(\d+) bonus XP$/,function(m){return '🏆 ¡Ruta completada! +'+m[1]+' XP de bonus'}],
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
 [/^Today's goal is at (\d+)% — a bit more and you're done\.$/,function(m){return 'Tu meta de hoy va al '+m[1]+'%'+': un poco más y listo.'}],
 [/^Up next · (.+)$/,function(m){return 'Siguiente · '+tr(m[1],'es')}],
 [/^Matches your goal: (.+)$/,function(m){return 'Coincide con tu objetivo: '+tr(m[1],'es')}],
 [/^Section (\d+) · (A1|A2|B1|B2)$/,function(m){return 'Sección '+m[1]+' · '+m[2]}],
 [/^(\d+) tricky items$/,function(m){return m[1]+' palabras difíciles'}],
 [/^(\d+)\/(\d+) lessons$/,function(m){return m[1]+'/'+m[2]+' lecciones'}],
 [/^Needs work · (\d+)$/,function(m){return 'A mejorar · '+m[1]}],
 [/^Good · (\d+)$/,function(m){return 'Bien · '+m[1]}],
 [/^Next: (.+)$/,function(m){return 'Siguiente: '+m[1]}],
 [/^Just (\d+) slips?$/,function(m){return 'Solo '+m[1]+(m[1]==='1'?' error':' errores')}],
 [/^🏆 Unit completed! \+(\d+) bonus XP$/,function(m){return '🏆 ¡Unidad completada! +'+m[1]+' XP de bonus'}],
 [/^🎯 (.+) · (.+) · (\d+) min\/day$/,function(m){return '🎯 '+tr(m[1],'es')+' · '+tr(m[2],'es')+' · '+m[3]+' min/día'}],
 [/^(\d+) min\/day$/,function(m){return m[1]+' min/día'}],
 [/^Today's plan · (\d+)\/(\d+)$/,function(m){return 'Plan de hoy · '+m[1]+'/'+m[2]}],
 [/^(\d+) items to refresh$/,function(m){return m[1]+' por refrescar'}],
 [/^Your lowest skill lately · (\d+)%$/,function(m){return 'Tu habilidad más baja últimamente · '+m[1]+'%'}],
 [/^🎯 Daily plan complete! \+(\d+) bonus XP$/,function(m){return '🎯 ¡Plan del día completo! +'+m[1]+' XP de bonus'}]
];
var PAT_EN=[
 [/^Turno (\d+) de (\d+)$/,function(m){return 'Turn '+m[1]+' of '+m[2]}],
 [/^Mejor (\d+)%$/,function(m){return 'Best '+m[1]+'%'}],
 [/^(A1|A2|B1|B2) · (\d+)\/(\d+) lecciones · ★ (\d+)$/,function(m){return m[1]+' · '+m[2]+'/'+m[3]+' lessons · ★ '+m[4]}],
 [/^(\d+)\/(\d+) lecciones · (A1|A2|B1|B2)$/,function(m){return m[1]+'/'+m[2]+' lessons · '+m[3]}],
 [/^Tu plan: (.+) · (\d+)\/(\d+) rutas · hasta (\d+) lecciones · 4 créditos$/,function(m){return 'Your plan: '+m[1]+' · '+m[2]+'/'+m[3]+' routes · up to '+m[4]+' lessons · 4 credits'}],
 [/^🏆 ¡Ruta completada! \+(\d+) XP de bonus$/,function(m){return '🏆 Route completed! +'+m[1]+' bonus XP'}],
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
