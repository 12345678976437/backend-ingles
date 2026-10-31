/* Talvo · Curso de español para extranjeros (interfaz en inglés). Datos: [texto, significado en inglés]. */
window.TALVO_COURSE_ES={
 id:'es',locale:'es-MX',root:'lc-es-root',
 title:['Spanish for English speakers','Español para angloparlantes'],
 voices:['es-MX-DaliaNeural','es-MX-JorgeNeural'],
 intro:['Learn real, spoken Mexican-neutral Spanish: listen, repeat and get scored on your pronunciation.','Aprende español hablado real: escucha, repite y recibe una nota de pronunciación.'],

 roles:[
  {id:'cafe',icon:'☕',name:['Order at a café','Pedir en un café'],ai:'You are a friendly waiter at a café in Mexico City. The student orders food and drinks.',open:['Buenas tardes, bienvenido. ¿Qué le gustaría tomar?','Good afternoon, welcome. What would you like to drink?']},
  {id:'hotel',icon:'🏨',name:['Hotel check-in','Registro en el hotel'],ai:'You are a hotel receptionist. The student arrives and wants to check in.',open:['Hola, buenas noches. ¿Tiene una reservación?','Hello, good evening. Do you have a reservation?']},
  {id:'taxi',icon:'🚕',name:['Taxi and directions','Taxi y direcciones'],ai:'You are a taxi driver. The student asks to go somewhere and asks how long it takes.',open:['Buenas. ¿A dónde va?','Hi. Where are you going?']},
  {id:'market',icon:'🛒',name:['At the market','En el mercado'],ai:'You are a fruit seller at a market. The student asks for prices and buys things.',open:['¡Pase, pase! ¿Qué se le ofrece hoy?','Come in! What can I get you today?']},
  {id:'pharmacy',icon:'💊',name:['At the pharmacy','En la farmacia'],ai:'You are a pharmacist. The student says they have a headache or a cold and asks for help.',open:['Buenos días. ¿En qué le puedo ayudar?','Good morning. How can I help you?']},
  {id:'friend',icon:'🤝',name:['Meet a new friend','Conocer a alguien'],ai:'You are a friendly local meeting the student at a party for the first time.',open:['¡Hola! Me llamo Carlos. ¿Y tú, cómo te llamas?',"Hi! I'm Carlos. And you, what's your name?"]}
 ],
 units:[
  {id:'es1',icon:'👋',name:['Hello!','¡Hola!'],tip:['In Spanish the letter H is always silent: “hola” sounds like “ola”.','En español la H nunca suena.'],
   items:[['Hola','Hello'],['Buenos días','Good morning'],['Buenas tardes','Good afternoon'],['Buenas noches','Good evening / Good night'],['¿Cómo estás?','How are you?'],['Estoy bien, gracias.',"I'm fine, thank you."],['Mucho gusto.','Nice to meet you.'],['Adiós.','Goodbye.']]},
  {id:'es2',icon:'🙋',name:['About you','Sobre ti'],tip:['Ñ sounds like “ny” in “canyon”: “año”, “español”.','La Ñ suena como “ny”.'],
   items:[['Me llamo Ana.','My name is Ana.'],['¿Cómo te llamas?',"What's your name?"],['Soy de Estados Unidos.',"I'm from the United States."],['¿De dónde eres?','Where are you from?'],['Hablo un poco de español.','I speak a little Spanish.'],['Tengo veinte años.',"I'm twenty years old."],['Vivo en Nueva York.','I live in New York.'],['¿Y tú?','And you?']]},
  {id:'es3',icon:'🔢',name:['Numbers 1–10','Números 1–10'],tip:['Spanish vowels are short and pure: a, e, i, o, u — never “ay”, “ee-oo”.','Las vocales son cortas y puras.'],
   items:[['uno','one'],['dos','two'],['tres','three'],['cuatro','four'],['cinco','five'],['seis','six'],['siete','seven'],['ocho','eight'],['nueve','nine'],['diez','ten']]},
  {id:'es4',icon:'🌮',name:['Food & drink','Comida y bebida'],tip:['Double R (“rr”) and R at the start of a word is rolled: “rico”, “carro”.','La RR vibra: “rico”, “carro”.'],
   items:[['Tengo hambre.',"I'm hungry."],['Quiero agua, por favor.','I want water, please.'],['Un café con leche, por favor.','A coffee with milk, please.'],['La cuenta, por favor.','The check, please.'],['Está muy rico.',"It's very tasty."],['Soy vegetariano.',"I'm vegetarian."],['¿Qué me recomienda?','What do you recommend?'],['Sin azúcar, por favor.','No sugar, please.']]},
  {id:'es5',icon:'🧭',name:['Getting around','Moverse'],tip:['J sounds like a strong English H: “jugo”, “Jalisco”.','La J suena fuerte.'],
   items:[['¿Dónde está el baño?','Where is the bathroom?'],['Voy al aeropuerto.',"I'm going to the airport."],['Gire a la derecha.','Turn right.'],['Siga todo recto.','Go straight ahead.'],['¿Cuánto cuesta?','How much does it cost?'],['Un boleto, por favor.','One ticket, please.'],['¿Está lejos?','Is it far?'],['Necesito un taxi.','I need a taxi.']]},
  {id:'es6',icon:'👨‍👩‍👧',name:['Family & friends','Familia y amigos'],tip:['LL sounds like the “y” in “yes”: “llamo”, “calle”.','La LL suena como “y”.'],
   items:[['mi madre','my mother'],['mi padre','my father'],['mi hermano','my brother'],['mi hermana','my sister'],['Tengo dos hermanos.','I have two siblings.'],['Mi amigo es simpático.','My friend is nice.'],['Somos una familia grande.','We are a big family.'],['Te presento a mi amiga.','Let me introduce my friend.']]},
  {id:'es7',icon:'☀️',name:['Daily life','Vida diaria'],tip:['Stress the marked syllable: “café”, “mañana”, “está”.','Acentúa la sílaba marcada.'],
   items:[['Me levanto a las siete.','I get up at seven.'],['Trabajo en una oficina.','I work in an office.'],['Me gusta leer.','I like to read.'],['Hoy hace calor.',"It's hot today."],['Mañana voy al mercado.',"Tomorrow I'm going to the market."],['¿Qué hora es?','What time is it?'],['Estoy cansado.',"I'm tired."],['Vamos a la playa.',"Let's go to the beach."]]},
  {id:'es8',icon:'🆘',name:['Survival phrases','Frases de supervivencia'],tip:['Say them slowly first, then at normal speed. Rhythm matters more than speed.','Primero despacio, luego normal.'],
   items:[['No entiendo.',"I don't understand."],['¿Puede repetir, por favor?','Can you repeat, please?'],['Más despacio, por favor.','Slower, please.'],['¿Habla inglés?','Do you speak English?'],['Necesito ayuda.','I need help.'],['Lo siento.',"I'm sorry."],['No hay problema.','No problem.'],['¿Cómo se dice esto en español?','How do you say this in Spanish?']]}
 ]
};
