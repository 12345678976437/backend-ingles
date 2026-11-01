/* Talvo · Piezas de ajedrez en SVG (dibujo propio, sin licencias ni descargas) y tema del tablero.
   window.ChessArt.piece(type,color) -> HTML de la pieza (usa un sprite que se inserta una sola vez). */
(function(){
'use strict';
/* siluetas en un cuadro de 45x45; cada pieza = lista de elementos [tag, atributos] */
const SH={
 p:['<circle class="cp-b" cx="22.5" cy="12.5" r="5.2"/>','<path class="cp-b" d="M17.2 18.4h10.6l-1.6 3.4c3.4 2.2 5.6 6.4 5.8 12.2H13c.2-5.800 2.400-10 5.800-12.200z"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>'],
 r:['<path class="cp-b" d="M11 8.500h4.600v3.400h3.400V8.500h7v3.400h3.400V8.500H34v8.400l-3.200 2.800H14.200L11 16.900z"/>','<path class="cp-b" d="M15.600 19.700h13.800l1.200 14.300H14.400z"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>'],
 n:['<path class="cp-b" d="M13.600 34c-.6-8.200 1.600-15.200 8-18.600l-2.200-3.200 3.800-2.400 2.600 2.600c5.200 2.200 8.600 8.600 8.600 21.600z"/>','<path d="M14.400 26.200l5.800-4.800" class="cp-line"/>','<circle cx="24.600" cy="15.800" r="1.300" class="cp-eye"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>'],
 b:['<circle class="cp-b" cx="22.500" cy="7.600" r="2.600"/>','<path class="cp-b" d="M22.500 10.200c-4.800 3.600-7 7.600-7 11.400 0 2.800 1.400 4.800 3.200 6l-2.600 6.400h12.800l-2.600-6.400c1.800-1.200 3.200-3.200 3.200-6 0-3.800-2.200-7.800-7-11.400z"/>','<path d="M20 17.500h5M22.500 15v5" class="cp-line"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>'],
 q:['<circle class="cp-b" cx="8.600" cy="12.200" r="2.600"/><circle class="cp-b" cx="15.600" cy="8.400" r="2.600"/><circle class="cp-b" cx="22.500" cy="7.200" r="2.600"/><circle class="cp-b" cx="29.400" cy="8.400" r="2.600"/><circle class="cp-b" cx="36.400" cy="12.200" r="2.600"/>','<path class="cp-b" d="M8.800 14.600l5.400 13.400h16.600l5.400-13.400-7.400 6.200-1.800-10.200-4.700 9.800-4.700-9.800-1.800 10.200z"/>','<path class="cp-b" d="M14.200 28h16.600l1 6H13.200z"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>'],
 k:['<path d="M22.500 3.600v8M18.700 7.400h7.600" class="cp-line cp-thick"/>','<path class="cp-b" d="M22.500 11.600c-6.800 0-12.200 4.400-12.200 10.200 0 3.200 1.800 5.600 4.200 6.800L13.300 34h18.400l-1.200-5.400c2.400-1.200 4.200-3.600 4.200-6.800 0-5.800-5.400-10.200-12.200-10.200z"/>','<path d="M16 24.400h13" class="cp-line"/>','<rect class="cp-b" x="10.500" y="34" width="24" height="4.600" rx="2.300"/>']
};
const css='.cp{width:100%;height:100%;display:block;overflow:visible;pointer-events:none}'
 +'.cp.w{--cpf:url(#cpGw);--cps:#0b1424;--cpl:#0b1424;filter:drop-shadow(0 2px 2px rgba(0,0,0,.55))}'
 +'.cp.b{--cpf:url(#cpGb);--cps:#7be9ff;--cpl:#7be9ff;filter:drop-shadow(0 0 2.5px rgba(70,200,255,.55)) drop-shadow(0 2px 2px rgba(0,0,0,.6))}'
 +'.cp-b{fill:var(--cpf);stroke:var(--cps);stroke-width:1.2;stroke-linejoin:round}.cp-line{fill:none;stroke:var(--cpl);stroke-width:1.6;stroke-linecap:round}.cp-thick{stroke-width:2.2}.cp-eye{fill:var(--cpl)}';
let ready=false;
function sprite(){
  if(ready||!document.body)return;ready=true;
  const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
  let s='<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>'
   +'<linearGradient id="cpGw" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#e3f2ff"/><stop offset="1" stop-color="#a9c8e6"/></linearGradient>'
   +'<linearGradient id="cpGb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#34456e"/><stop offset=".55" stop-color="#16213f"/><stop offset="1" stop-color="#0a1226"/></linearGradient></defs>';
  Object.keys(SH).forEach(t=>{s+='<symbol id="cp-'+t+'" viewBox="0 0 45 45">'+SH[t].join('')+'</symbol>'});
  document.body.insertAdjacentHTML('afterbegin',s+'</svg>');
}
window.ChessArt={
  piece(t,c){sprite();return '<svg class="cp '+(c==='w'?'w':'b')+'" viewBox="0 0 45 45"><use href="#cp-'+t+'"/></svg>'},
  sprite
};
})();
