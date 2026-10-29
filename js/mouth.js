/* Diagramas de boca (vista lateral) para el Sound Lab: dónde van la lengua y los labios.
   Dibujo propio en SVG con animación SMIL, sin imágenes ni costo. window.mouthDiagram(id) -> HTML. */
(function(){
  /* j = apertura de mandíbula 0-1 · tip/front/back = puntos de la lengua · lips = neutral|round|spread|teeth
     voiced = vibra la garganta · nasal = sale por la nariz · contact = punto de contacto · air = sale aire */
  const REST={j:.2,tip:[180,114],front:[140,108],back:[92,112],lips:'neutral'};
  const P={
    th:{j:.2,tip:[194,100],front:[150,103],back:[96,112],lips:'neutral',voiced:false,contact:[191,99],air:true},
    dh:{j:.2,tip:[194,100],front:[150,103],back:[96,112],lips:'neutral',voiced:true,contact:[191,99]},
    ih:{j:.25,tip:[174,106],front:[140,90],back:[96,106],lips:'neutral',voiced:true},
    iy:{j:.15,tip:[176,100],front:[140,84],back:[95,104],lips:'spread',voiced:true},
    ae:{j:.95,tip:[176,134],front:[138,128],back:[92,114],lips:'neutral',voiced:true},
    ah:{j:.55,tip:[172,120],front:[138,116],back:[92,102],lips:'neutral',voiced:true},
    sh:{j:.2,tip:[166,90],front:[136,84],back:[96,104],lips:'round',voiced:false,air:true,contact:[168,80]},
    jh:{j:.2,tip:[176,82],front:[142,92],back:[96,106],lips:'round',voiced:true,contact:[176,79]},
    v:{j:.15,tip:[160,118],front:[130,114],back:[92,112],lips:'teeth',voiced:true,contact:[194,99]},
    z:{j:.15,tip:[172,88],front:[140,98],back:[96,108],lips:'spread',voiced:true,contact:[174,83]},
    r:{j:.3,tip:[150,80],front:[128,104],back:[94,86],lips:'round',voiced:true},
    h:{j:.55,tip:[172,122],front:[138,120],back:[92,116],lips:'neutral',voiced:false,air:true,throat:true},
    ng:{j:.2,tip:[176,116],front:[130,104],back:[80,74],lips:'neutral',voiced:true,nasal:true,contact:[74,70]},
    w:{j:.1,tip:[158,114],front:[128,106],back:[90,80],lips:'round',voiced:true},
    uh:{j:.3,tip:[160,114],front:[130,106],back:[92,84],lips:'round',voiced:true},
    uw:{j:.15,tip:[158,112],front:[128,104],back:[90,78],lips:'round',voiced:true},
    er:{j:.35,tip:[150,82],front:[128,106],back:[94,88],lips:'round',voiced:true},
    y:{j:.15,tip:[172,100],front:[140,80],back:[100,100],lips:'spread',voiced:true}
  };
  const LIP={neutral:{x:0,o:0},round:{x:9,o:-5},spread:{x:-3,o:6},teeth:{x:0,o:-12}};
  const mid=(a,b)=>[(a[0]+b[0])/2,(a[1]+b[1])/2];
  const f=n=>Math.round(n*10)/10;
  function tongue(s){
    const T=[[48,170],[54,s.back[1]+18],s.back,s.front,s.tip];
    let d='M'+T[0].join(' ');
    for(let i=1;i<T.length-1;i++){const m=mid(T[i],T[i+1]);d+=' Q'+f(T[i][0])+' '+f(T[i][1])+' '+f(m[0])+' '+f(m[1])}
    d+=' L'+T[T.length-1].join(' ');
    d+=' L'+f(s.tip[0]-4)+' '+f(s.tip[1]+14)+' L'+f(s.tip[0]-30)+' '+f(s.tip[1]+26)+' L108 176 Z';
    return d;
  }
  const DY=j=>f(j*26);
  function tags(s){
    const t=[];
    t.push(s.voiced?'<span class="mo-chip v">🔊 Con voz: tu garganta vibra</span>':'<span class="mo-chip">💨 Sin voz: solo aire</span>');
    t.push({round:'<span class="mo-chip">👄 Labios redondos</span>',spread:'<span class="mo-chip">😁 Labios en sonrisa</span>',teeth:'<span class="mo-chip">🦷 Dientes de arriba sobre el labio de abajo</span>',neutral:'<span class="mo-chip">👄 Labios relajados</span>'}[s.lips]);
    if(s.contact&&!s.nasal&&s.lips!=='teeth')t.push('<span class="mo-chip">🎯 Punto de contacto</span>');
    if(s.nasal)t.push('<span class="mo-chip">👃 El aire sale por la nariz</span>');
    return t.join('');
  }
  window.mouthDiagram=function(id){
    const s=P[id];if(!s)return '';
    const a=Object.assign({},REST,{voiced:false}),L=LIP[s.lips]||LIP.neutral;
    const dur='3s',kt='0;.28;.82;1',kts='.42 0 .58 1;0 0 1 1;.42 0 .58 1';
    const an=(attr,v0,v1,extra)=>'<animate attributeName="'+attr+'" values="'+v0+';'+v1+';'+v1+';'+v0+'" keyTimes="'+kt+'" dur="'+dur+'" repeatCount="indefinite" calcMode="spline" keySplines="'+kts+'"'+(extra||'')+'/>';
    const at=(typ,v0,v1)=>'<animateTransform attributeName="transform" type="'+typ+'" values="'+v0+';'+v1+';'+v1+';'+v0+'" keyTimes="'+kt+'" dur="'+dur+'" repeatCount="indefinite" calcMode="spline" keySplines="'+kts+'"/>';
    const lowerBase=DY(a.j),lowerT=DY(s.j);
    let svg='<svg class="mo-svg" viewBox="0 0 250 200" role="img" aria-label="Posición de la boca" data-i18n-skip>';
    /* cabeza: nariz, mejilla y cuello */
    svg+='<path d="M205 66 Q222 56 224 44 Q226 34 214 34 L150 30 Q70 30 52 60 L46 176" fill="none" stroke="currentColor" stroke-opacity=".28" stroke-width="2" stroke-linecap="round"/>';
    svg+='<path d="M46 176 Q60 198 120 196 Q196 194 216 150" fill="none" stroke="currentColor" stroke-opacity=".28" stroke-width="2" stroke-linecap="round"/>';
    /* nariz (aire nasal) */
    if(s.nasal)svg+='<path d="M64 66 Q70 40 150 42 Q196 42 214 44" fill="none" stroke="#5ec8ff" stroke-width="3" stroke-dasharray="6 7" stroke-linecap="round"><animate attributeName="stroke-dashoffset" values="26;0" dur="1s" repeatCount="indefinite"/></path>';
    /* paladar */
    svg+='<path d="M190 80 Q150 50 104 56 Q72 58 58 80" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="3" stroke-linecap="round"/>';
    if(s.nasal)svg+='<path d="M58 80 Q54 96 66 104" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="3" stroke-linecap="round"/>';
    /* lengua */
    svg+='<path d="'+tongue(a)+'" fill="#ff8aa0" fill-opacity=".92" stroke="#d6546f" stroke-width="2" stroke-linejoin="round">'+an('d',tongue(a),tongue(s))+'</path>';
    /* dientes y labio de arriba */
    svg+='<rect x="186" y="78" width="10" height="22" rx="3" fill="#fff" stroke="#9aa3b2" stroke-width="1.5"/>';
    svg+='<g><path d="M198 64 Q216 62 222 76 Q224 92 212 98 Q204 100 198 98 Z" fill="#f08a8a" stroke="#c45a5a" stroke-width="2" stroke-linejoin="round"/>'+(L.x?at('translate','0 0',L.x+' 0'):'')+'</g>';
    /* mandíbula inferior: dientes, labio y mentón se mueven juntos */
    svg+='<g transform="translate(0 '+lowerBase+')">'+at('translate','0 '+lowerBase,'0 '+lowerT);
    svg+='<rect x="186" y="104" width="10" height="18" rx="3" fill="#fff" stroke="#9aa3b2" stroke-width="1.5"/>';
    svg+='<path d="M198 106 Q214 104 222 114 Q222 134 206 138 Q198 138 196 130 Z" fill="#f08a8a" stroke="#c45a5a" stroke-width="2" stroke-linejoin="round">'+(s.lips==='teeth'?at('translate','0 0','0 -12'):(L.x?at('translate','0 0',L.x+' 0'):''))+'</path>';
    svg+='<path d="M196 138 Q204 168 150 176" fill="none" stroke="currentColor" stroke-opacity=".28" stroke-width="2" stroke-linecap="round"/></g>';
    /* contacto */
    if(s.contact)svg+='<circle cx="'+s.contact[0]+'" cy="'+s.contact[1]+'" r="5" fill="none" stroke="#ffd166" stroke-width="2.5"><animate attributeName="r" values="4;9;4" dur="1.2s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;.35;1" dur="1.2s" repeatCount="indefinite"/></circle>';
    /* voz: vibración en la garganta */
    if(s.voiced||s.throat){const cy=s.throat?118:124;svg+='<g fill="none" stroke="'+(s.voiced?'#5ee6a8':'#9aa3b2')+'" stroke-width="2" stroke-linecap="round"><path d="M44 '+cy+' q-6 -7 0 -14 q6 -7 0 -14"><animate attributeName="opacity" values="1;.2;1" dur=".5s" repeatCount="indefinite"/></path><path d="M36 '+(cy+2)+' q-8 -9 0 -18 q8 -9 0 -18"><animate attributeName="opacity" values=".2;1;.2" dur=".5s" repeatCount="indefinite"/></path></g>'}
    /* aire */
    if(s.air){for(let i=0;i<3;i++){const y=92+i*14;svg+='<line x1="224" y1="'+y+'" x2="240" y2="'+y+'" stroke="#5ec8ff" stroke-width="3" stroke-linecap="round"><animate attributeName="x1" values="224;240" dur="1s" begin="'+(i*.25)+'s" repeatCount="indefinite"/><animate attributeName="x2" values="236;250" dur="1s" begin="'+(i*.25)+'s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0" dur="1s" begin="'+(i*.25)+'s" repeatCount="indefinite"/></line>'}}
    svg+='</svg>';
    return '<div class="mo-box">'+svg+'<div class="mo-chips">'+tags(s)+'</div><small class="mo-note" data-i18n-skip>Dibujo esquemático: la boca va de reposo a la posición del sonido. Frente a un espejo se ve más claro.</small></div>';
  };
  const css=document.createElement('style');
  css.textContent='.mo-box{margin:12px auto 4px;max-width:340px;text-align:center}.mo-svg{width:100%;height:auto;color:var(--text,#e8ecf5);background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:16px}.mo-chips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:10px}.mo-chip{font-size:12px;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12)}.mo-chip.v{border-color:rgba(94,230,168,.5)}.mo-note{display:block;margin-top:8px;color:var(--muted,#9aa3b2);font-size:11px}';
  document.head.appendChild(css);
})();
