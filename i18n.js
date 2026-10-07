/* Talvo English · interfaz en español / inglés
   Traduce el texto de la interfaz (no el contenido que se practica). Se aplica
   a lo que ya está en la página y a lo que la app va agregando después. */
(function(){
'use strict';
var ES={
// Bienvenida y registro
'Speak with confidence.':'Habla con confianza.',
'✨ 7-day free trial, no strings attached':'✨ 7 días de prueba gratis, sin compromiso',
'Practice pronunciation, writing, reading, listening and real conversation with an AI tutor — all in one place.':'Practica pronunciación, escritura, lectura, comprensión auditiva y conversación real con un tutor de IA, todo en un solo lugar.',
'🗣️ Speaking':'🗣️ Hablar','✍️ Writing':'✍️ Escribir','🎧 Listening':'🎧 Escuchar','🤖 AI Tutor':'🤖 Tutor IA',
'Start free trial':'Comenzar prueba gratis','I already have an account':'Ya tengo cuenta',
'Sign in':'Iniciar sesión','Sign out':'Cerrar sesión','Sign in again':'Iniciar sesión de nuevo','Create account':'Crear cuenta',
'Create an account':'Crear una cuenta','Back to sign in':'Volver a iniciar sesión','Cancel':'Cancelar',
'Use your Talvo English account.':'Usa tu cuenta de Talvo English.','Sign in to practice':'Inicia sesión para practicar','Not signed in':'Sin sesión',
// Onboarding
'What brings you to Talvo?':'¿Para qué quieres aprender inglés?','This helps us tailor your practice.':'Esto nos ayuda a adaptar tu práctica.',
'💼 Work':'💼 Trabajo','✈️ Travel':'✈️ Viajes','🎓 Study':'🎓 Estudios','📝 Exams (TOEFL, IELTS...)':'📝 Exámenes (TOEFL, IELTS...)','🌱 Personal growth':'🌱 Crecimiento personal',
'How much time can you give each day?':'¿Cuánto tiempo puedes dedicar cada día?',
'We\'ll set this as your daily goal — you can change it later in Settings.':'Será tu meta diaria; puedes cambiarla después en Ajustes.',
'5 minutes':'5 minutos','10 minutes':'10 minutos','15 minutes':'15 minutos','20 minutes':'20 minutos','30 minutes':'30 minutos',
'How would you rate your English today?':'¿Cómo calificas tu inglés hoy?','Be honest — we\'ll adjust as you practice.':'Sé sincero; iremos ajustando mientras practicas.',
'🌱 Beginner — I know some words and phrases':'🌱 Principiante: conozco algunas palabras y frases',
'🙂 Elementary — I can have simple conversations':'🙂 Básico: puedo tener conversaciones simples',
'💬 Intermediate — I can talk about most everyday topics':'💬 Intermedio: puedo hablar de casi cualquier tema cotidiano',
'🚀 Advanced — I\'m fairly fluent, polishing details':'🚀 Avanzado: hablo con fluidez, pulo detalles',
'🎯 Take a quick level test (1 min)':'🎯 Hacer una mini prueba de nivel (1 min)','…or choose your level yourself:':'…o elige tu nivel tú mismo:',
// Navegación
'Home':'Inicio','Learn':'Aprender','Practice':'Practicar','Progress':'Progreso','Account':'Cuenta',
'Learning Path':'Ruta de aprendizaje','Pronunciation':'Pronunciación','Writing':'Escritura','Reading':'Lectura','Listening':'Escucha','Vocabulary':'Vocabulario',
'AI Tutor':'Tutor IA','Call':'Llamada','My Progress':'Mi progreso','Achievements':'Logros','Shop':'Tienda','Admin':'Admin',
'My account':'Mi cuenta','Notifications':'Notificaciones','Settings':'Ajustes','Support':'Soporte',
'Path':'Ruta','Speak':'Hablar','Tutor':'Tutor','Menu':'Menú','Ready':'Listo',
// Home
'Ready to improve your English today?':'¿Listo para mejorar tu inglés hoy?','Today\'s goal':'Meta de hoy',
'More ways to practice':'Más formas de practicar','Practice speaking':'Practica hablar','Write with feedback':'Escribe con retroalimentación',
'Read & explain':'Lee y explica','Listen & transcribe':'Escucha y transcribe','Talk out loud':'Habla en voz alta','Build your word bank':'Construye tu banco de palabras',
'Your skills':'Tus habilidades','Recent achievements':'Logros recientes','Today\'s vocabulary':'Vocabulario de hoy',
'Loading...':'Cargando...','No words yet.':'Aún no hay palabras.','Your vocabulary':'Tu vocabulario','Review words →':'Repasar palabras →',
'Could not load today\'s word.':'No se pudo cargar la palabra de hoy.','Could not load today\'s words.':'No se pudieron cargar las palabras de hoy.',
'🗣️ Speaking ':'🗣️ Hablar ','📖 Reading':'📖 Lectura','🎧 Listening ':'🎧 Escucha ',
// Siguiente paso
'Your next step':'Tu siguiente paso','Continue':'Continuar','Start':'Empezar','Review vocabulary':'Repasar vocabulario',
'You finished every available lesson. Keep your words fresh!':'¡Terminaste todas las lecciones disponibles! Mantén tus palabras frescas.',
'words to review today':'palabras para repasar hoy','Review now':'Repasar ahora',
// Pronunciación
'Pronunciation Lab':'Laboratorio de pronunciación','Speak clearly. Improve precisely.':'Habla claro. Mejora con precisión.',
'Practice a guided sentence, free speaking, a tongue twister, or work with your AI Tutor.':'Practica una frase guiada, habla libre, un trabalenguas o trabaja con tu Tutor IA.',
'Guided Reading':'Lectura guiada','Free Talk':'Habla libre','Tongue Twisters':'Trabalenguas','Loading your sentence...':'Cargando tu frase...',
'Or enter your own sentence':'O escribe tu propia frase','Use sentence':'Usar frase','New sentence':'Nueva frase','New topic':'Nuevo tema','New challenge':'Nuevo reto',
'Focus':'Enfoque','Start recording':'Empezar a grabar','Recording... 0s · Click to stop':'Grabando... 0s · Toca para detener','Analyzing...':'Analizando...',
'Omissions':'Omisiones','Inconsistent':'Inconsistentes','Insertions':'Inserciones','Unexpected breaks':'Pausas inesperadas','Missing pause':'Falta de pausa','Monotone':'Monótono',
'Overall score':'Puntuación general','Phonetic accuracy':'Precisión fonética','Fluency':'Fluidez','Completeness':'Completitud','Prosody':'Prosodia','Grammar':'Gramática',
'Your recording':'Tu grabación','Speaking rate':'Velocidad al hablar','Slow':'Lenta','Good pace':'Buen ritmo','Fast':'Rápida','Phonemes':'Fonemas',
'Your AI Tutor helps you practice naturally. Type or speak, then receive feedback on grammar, vocabulary, clarity, and pronunciation.':'Tu Tutor IA te ayuda a practicar con naturalidad. Escribe o habla y recibe comentarios sobre gramática, vocabulario, claridad y pronunciación.',
'📍 Practice in Learning Path':'📍 Practicar en la Ruta de aprendizaje','🧭 Coach insight':'🧭 Consejo del coach',
'Complete words':'Palabras completas','Consistent sounds':'Sonidos consistentes','No extra sounds':'Sin sonidos extra','Smooth flow':'Flujo suave','Natural pauses':'Pausas naturales','Good intonation':'Buena entonación',
'🎯 Practice only this word':'🎯 Practicar solo esta palabra','🔊 Native voice':'🔊 Voz nativa','Your sounds over time':'Tus sonidos con el tiempo',
'Needs work':'Por mejorar','Improving':'Mejorando','Steady':'Estable','Practice a few sentences to see how each sound evolves.':'Practica algunas frases para ver cómo evoluciona cada sonido.',
'No phoneme detail available.':'Sin detalle de fonemas.',
// Escritura / lectura / escucha
'Write with purpose.':'Escribe con propósito.','Submit your English writing and receive focused feedback.':'Envía tu texto en inglés y recibe comentarios puntuales.',
'Choose a challenge':'Elige un reto','Easy':'Fácil','Intermediate':'Intermedio','Advanced':'Avanzado','Beginner':'Principiante','All':'Todos',
'Today\'s challenge':'Reto de hoy','Loading a challenge for you...':'Cargando un reto para ti...','🔄 New challenge':'🔄 Nuevo reto','Skip — write freely':'Omitir: escribir libremente',
'Your text':'Tu texto','Write in English...':'Escribe en inglés...','Analyze writing':'Analizar escritura','Overall':'General','Vocabulary ':'Vocabulario ',
'Read. Understand. Explain.':'Lee. Comprende. Explica.','Read an informational English text, then explain what you understood in your own words.':'Lee un texto informativo en inglés y luego explica con tus palabras lo que entendiste.',
'← Back to library':'← Volver a la biblioteca','Loading reading...':'Cargando lectura...','New reading':'Nueva lectura',
'Explain what you understood in English':'Explica en inglés lo que entendiste','Write what you understood. Do not copy the text.':'Escribe lo que entendiste. No copies el texto.',
'Analyze comprehension':'Analizar comprensión','Understanding':'Comprensión',
'Listen carefully.':'Escucha con atención.','Listen to a short English passage and write what you hear.':'Escucha un fragmento corto en inglés y escribe lo que oyes.',
'Play audio':'Reproducir audio','New audio':'Nuevo audio','Press play, then write what you heard.':'Presiona reproducir y luego escribe lo que oíste.',
'Type what you heard...':'Escribe lo que oíste...','Evaluate listening':'Evaluar escucha','Accuracy':'Precisión','Words matched':'Palabras acertadas',
// Vocabulario
'Build your word bank.':'Construye tu banco de palabras.','Learn today\'s words and review what you\'ve saved.':'Aprende las palabras de hoy y repasa las que guardaste.',
'Today\'s words':'Palabras de hoy','🔄 New words':'🔄 Nuevas palabras','No saved words yet.':'Aún no hay palabras guardadas.',
'✓ Learned':'✓ Aprendida','Mark learned':'Marcar aprendida',
'Daily review':'Repaso del día','Show meaning':'Mostrar significado','✅ I knew it':'✅ La sabía','❌ I didn\'t know it':'❌ No la sabía',
'Review complete! Come back tomorrow for more.':'¡Repaso completado! Vuelve mañana por más.','Nothing to review right now. Great job!':'No hay nada por repasar ahora. ¡Buen trabajo!',
'Words come back after 1, 3, 7, 14 and 30 days so they really stick.':'Las palabras regresan a los 1, 3, 7, 14 y 30 días para que se queden de verdad.',
// Tutor y llamada
'Practice with your tutor.':'Practica con tu tutor.','A conversational English coach for realistic practice and instant feedback.':'Un coach de inglés conversacional para práctica realista y comentarios al instante.',
'Conversation':'Conversación','Free talk':'Habla libre','Speak naturally. Ask questions. Make mistakes. Improve.':'Habla con naturalidad. Haz preguntas. Equivócate. Mejora.',
'Speak last reply':'Escuchar última respuesta','🎙️ Speak':'🎙️ Hablar','Send':'Enviar',
'Live Call':'Llamada en vivo','Practice like a real phone call.':'Practica como en una llamada real.',
'Hold the button, say your turn in English, and let go. Palanqueta will answer out loud.':'Mantén presionado el botón, di tu turno en inglés y suelta. Palanqueta responderá en voz alta.',
'🎙️ Hold to talk':'🎙️ Mantén para hablar','🎧 Hands-free: OFF':'🎧 Manos libres: NO','🎧 Hands-free: ON':'🎧 Manos libres: SÍ',
'Speaking score':'Puntaje al hablar','Pronunciation*':'Pronunciación*',
'*Pronunciation is estimated from your transcript, not a live audio analysis.':'*La pronunciación se estima con tu transcripción, no con un análisis de audio en vivo.',
// Progreso, logros, tienda
'See your improvement.':'Mira tu mejora.','Your practice history and performance trends.':'Tu historial de práctica y tendencias de desempeño.',
'🎯 Total activities':'🎯 Actividades totales','🗣️ Pronunciation sessions':'🗣️ Sesiones de pronunciación','✍️ Writing tasks':'✍️ Tareas de escritura','📖 Reading tasks':'📖 Tareas de lectura',
'Recent performance':'Desempeño reciente','Your achievements.':'Tus logros.','Keep practicing to unlock them all.':'Sigue practicando para desbloquearlos todos.',
'✓ Completed':'✓ Completado','Spend your gems.':'Gasta tus gemas.','Earned automatically as you practice — 1 gem for every ~10 XP.':'Se ganan al practicar: 1 gema por cada ~10 XP.',
'Streak protection':'Protección de racha','🧊 Streak Freeze':'🧊 Congelar racha','Automatically protects your streak if you miss exactly one day.':'Protege tu racha automáticamente si faltas exactamente un día.',
'Buy — 50 💎':'Comprar — 50 💎','Unlock a unit early':'Desbloquea una unidad antes','Avatar frames':'Marcos de avatar',
'Your English Journey.':'Tu camino en inglés.','Follow your path and build confidence step by step.':'Sigue tu ruta y gana confianza paso a paso.','← Back to path':'← Volver a la ruta',
'🗣️ Speak it':'🗣️ Dilo','✍️ Write it':'✍️ Escríbelo','📖 Read it':'📖 Léelo','🎧 Listen & type':'🎧 Escucha y escribe','Not started':'Sin empezar',
// Cuenta, notificaciones, ajustes
'Account status':'Estado de la cuenta','Display name':'Nombre para mostrar','Your name':'Tu nombre','Save':'Guardar','Profile photo':'Foto de perfil','Upload photo':'Subir foto',
'JPG, PNG or WEBP, max 4MB':'JPG, PNG o WEBP, máx. 4 MB','What\'s new for you.':'Novedades para ti.',
'A quick look at your streak, goals, and progress — built from your real activity.':'Un vistazo a tu racha, metas y progreso, según tu actividad real.',
'Make it feel right.':'Hazla a tu gusto.','A couple of preferences for how the app talks to you.':'Un par de preferencias sobre cómo te habla la app.',
'Auto-play tutor voice replies':'Reproducir automáticamente las respuestas del tutor','Automatically read the AI Tutor\'s replies out loud.':'Lee en voz alta las respuestas del Tutor IA.',
'On':'Sí','Off':'No','Speech rate':'Velocidad de voz','How fast Palanqueta and dictation audio sound.':'Qué tan rápido suenan Palanqueta y el audio de dictado.','Normal':'Normal',
'Free trial':'Prueba gratis','Open menu':'Abrir menú','Close menu':'Cerrar menú',
'Install app':'Instalar app','📲 Install app':'📲 Instalar app',
'Waking up the server… the first time can take up to a minute.':'Despertando el servidor… la primera vez puede tardar hasta un minuto.',
'Loading a speaking topic...':'Cargando un tema para hablar...','Loading a tongue twister...':'Cargando un trabalenguas...',
'Coherence':'Coherencia','Corrections':'Correcciones','Better version':'Versión mejorada','English quality':'Calidad del inglés','What you did well':'Lo que hiciste bien',
'Improve next':'Para mejorar','Suggested vocabulary':'Vocabulario sugerido','Differences':'Diferencias','Level':'Nivel','Main navigation':'Navegación principal',
'Email':'Correo','Password':'Contraseña','🔊 Escuchar':'🔊 Escuchar',
'Hi! I’m Palanqueta, your English tutor. Tell me something about your day.':'Hi! I’m Palanqueta, your English tutor. Cuéntame algo de tu día (en inglés).',
"Hi! I'm Palanqueta. Press and hold the button, say something, and let go when you're done.":"Hi! I'm Palanqueta. Mantén presionado el botón, di algo en inglés y suéltalo cuando termines.",
'Connected ✓':'Conectado ✓'
};
var PATTERNS=[
[/^(Good morning|Good afternoon|Good evening), (.*)! 👋$/,function(m){return {'Good morning':'Buenos días','Good afternoon':'Buenas tardes','Good evening':'Buenas noches'}[m[1]]+', '+m[2]+'! 👋'}],
[/^Good day! 👋$/,function(){return '¡Buen día! 👋'}],
[/^🔥 (\d+) day streak$/,function(m){return '🔥 '+m[1]+(m[1]==='1'?' día de racha':' días de racha')}],
[/^⭐ (\d+) XP · Level (\d+)$/,function(m){return '⭐ '+m[1]+' XP · Nivel '+m[2]}],
[/^Free trial · (\d+) day\(s\) left$/,function(m){return 'Prueba gratis · quedan '+m[1]+' día(s)'}],
[/^Practice access active$/,function(){return 'Acceso activo'}],
[/^Trial ended · subscribe to continue$/,function(){return 'Prueba terminada · suscríbete para continuar'}],
[/^📚 (\d+) words? saved$/,function(m){return '📚 '+m[1]+(m[1]==='1'?' palabra guardada':' palabras guardadas')}],
[/^✅ (\d+) learned$/,function(m){return '✅ '+m[1]+' aprendidas'}],
[/^(\d+) \/ (\d+) learned$/,function(m){return m[1]+' / '+m[2]+' aprendidas'}],
[/^(\d+)\/(\d+) lessons( · Completed 🎉)?$/,function(m){return m[1]+'/'+m[2]+' lecciones'+(m[3]?' · Completada 🎉':'')}],
[/^🏆 (\d+) \/ (\d+) unlocked$/,function(m){return '🏆 '+m[1]+' / '+m[2]+' desbloqueados'}],
[/^Requires (\d+) XP( \+ previous unit)?$/,function(m){return 'Requiere '+m[1]+' XP'+(m[2]?' + unidad anterior':'')}],
[/^⭐ (\d+) XP$/,function(m){return '⭐ '+m[1]+' XP'}],
[/^(\d+) words?$/,function(m){return m[1]+(m[1]==='1'?' palabra':' palabras')}],
[/^🎧 (\d+) plays?$/,function(m){return '🎧 '+m[1]+(m[1]==='1'?' reproducción':' reproducciones')}],
[/^💎 (\d+) gems$/,function(m){return '💎 '+m[1]+' gemas'}],
[/^🧊 (\d+) streak freezes?$/,function(m){return '🧊 '+m[1]+' congelador(es) de racha'}],
[/^Recording\.\.\. (\d+)s · Click to stop$/,function(m){return 'Grabando... '+m[1]+'s · Toca para detener'}],
[/^(Continue|Start): Unit (\d+), lesson (\d+)$/,function(m){return (m[1]==='Continue'?'Continuar':'Empezar')+': Unidad '+m[2]+', lección '+m[3]}],
[/^(\d+) words? to review today$/,function(m){return m[1]+(m[1]==='1'?' palabra para repasar hoy':' palabras para repasar hoy')}],
[/^Reviewed (\d+)\/(\d+)$/,function(m){return 'Repasadas '+m[1]+'/'+m[2]}],
[/^Level (\d+)$/,function(m){return 'Nivel '+m[1]}]
];
var lang=(function(){try{var s=localStorage.getItem('talvo_lang');if(s==='es'||s==='en')return s}catch(e){}return 'es'})();
var EN={};Object.keys(ES).forEach(function(k){EN[ES[k]]=k});
var orig=new WeakMap(),origAttr=new WeakMap(),busy=false;
function tx(str){
  var t=str.trim();if(!t)return str;
  var r=ES[t];
  if(r===undefined){for(var i=0;i<PATTERNS.length;i++){var m=t.match(PATTERNS[i][0]);if(m){r=PATTERNS[i][1](m);break}}}
  return r===undefined?str:str.replace(t,r);
}
function doNode(n){
  if(n.nodeType===3){
    var p=n.parentNode;if(p&&(p.nodeName==='SCRIPT'||p.nodeName==='STYLE'||p.nodeName==='TEXTAREA'))return;
    if(lang==='es'){var cur=n.nodeValue,res=tx(cur);if(res!==cur){if(!orig.has(n))orig.set(n,cur);n.nodeValue=res}}
    else if(orig.has(n)){n.nodeValue=orig.get(n);orig.delete(n)}
    return;
  }
  if(n.nodeType!==1||n.nodeName==='SCRIPT'||n.nodeName==='STYLE')return;
  ['placeholder','aria-label','title','alt'].forEach(function(a){
    if(!n.hasAttribute(a))return;var v=n.getAttribute(a);
    if(lang==='es'){var r=tx(v);if(r!==v){var o=origAttr.get(n)||{};if(!(a in o))o[a]=v;origAttr.set(n,o);n.setAttribute(a,r)}}
    else{var o2=origAttr.get(n);if(o2&&a in o2){n.setAttribute(a,o2[a]);delete o2[a]}}
  });
  for(var c=n.firstChild;c;c=c.nextSibling)doNode(c);
}
function run(root){busy=true;try{doNode(root||document.body)}finally{busy=false}}
function setLang(l){
  lang=l;try{localStorage.setItem('talvo_lang',l)}catch(e){}
  document.documentElement.lang=l;run(document.body);syncButtons();
  document.dispatchEvent(new CustomEvent('talvo:lang',{detail:l}));
}
function syncButtons(){
  var els=document.querySelectorAll('.lang-toggle');
  for(var i=0;i<els.length;i++)els[i].innerHTML=lang==='es'?'<b>ES</b> | EN':'ES | <b>EN</b>';
}
function tr(en,vars){
  var s=(lang==='es'&&ES[en])?ES[en]:en;
  if(vars)Object.keys(vars).forEach(function(k){s=s.split('{'+k+'}').join(vars[k])});
  return s;
}
function mountToggles(){
  var targets=[document.querySelector('.userbar'),document.querySelector('.welcome-card')];
  targets.forEach(function(t,i){
    if(!t||t.querySelector('.lang-toggle'))return;
    var b=document.createElement('button');b.type='button';b.className='btn lang-toggle'+(i?' lang-toggle-welcome':'');
    b.setAttribute('aria-label','Idioma / Language');
    b.addEventListener('click',function(){setLang(lang==='es'?'en':'es')});
    t.insertBefore(b,t.firstChild);
  });
  syncButtons();
}
window.TALVO_I18N={tr:tr,setLang:setLang,get lang(){return lang},refresh:function(){run(document.body)}};
window.tr=tr;
document.addEventListener('DOMContentLoaded',function(){
  document.documentElement.lang=lang;mountToggles();run(document.body);
  new MutationObserver(function(muts){
    if(busy||lang!=='es')return;
    busy=true;
    try{muts.forEach(function(m){
      if(m.type==='characterData')doNode(m.target);
      else m.addedNodes.forEach(function(n){doNode(n)});
    })}finally{busy=false}
  }).observe(document.body,{childList:true,subtree:true,characterData:true});
});
})();
