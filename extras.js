/* Talvo · extras: selector de color, instalación (PWA) y aviso sin conexión */
(function(){
'use strict';
/* ---- selector de color ---- */
var T=window.TalvoTheme,box=document.getElementById('theme-picker');
if(T&&box){
  box.innerHTML=Object.keys(T.themes).map(function(k){var t=T.themes[k];return '<button type="button" class="swatch" data-theme="'+k+'" aria-pressed="false" data-i18n-skip><i style="background:linear-gradient(135deg,'+t[1]+','+t[2]+')"></i><span>'+t[0]+'</span></button>'}).join('');
  box.addEventListener('click',function(e){var b=e.target.closest('.swatch');if(b)T.apply(b.dataset.theme)});
  T.apply(T.current());
}
/* ---- PWA: service worker ---- */
if('serviceWorker' in navigator&&(location.protocol==='https:'||location.hostname==='localhost'||location.hostname==='127.0.0.1')){
  window.addEventListener('load',function(){navigator.serviceWorker.register('sw.js').catch(function(){})});
}
/* ---- PWA: botón de instalar ---- */
var deferred=null,card=document.getElementById('install-card'),btn=document.getElementById('install-btn'),note=document.getElementById('install-note');
function standalone(){return (window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone===true}
function renderInstall(){
  if(!card)return;
  if(standalone()){card.style.display='none';return}
  var ios=/iphone|ipad|ipod/i.test(navigator.userAgent);
  if(deferred){card.style.display='block';btn.style.display='';note.style.display='none'}
  else if(ios){card.style.display='block';btn.style.display='none';note.style.display=''}
  else card.style.display='none';
}
window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();deferred=e;renderInstall()});
window.addEventListener('appinstalled',function(){deferred=null;renderInstall()});
if(btn)btn.addEventListener('click',function(){
  if(!deferred)return;
  deferred.prompt();
  (deferred.userChoice||Promise.resolve()).then(function(){deferred=null;renderInstall()});
});
renderInstall();
/* ---- sin conexión ---- */
function say(msg){var t=document.getElementById('toast');if(!t)return;t.textContent=msg;t.style.display='block';clearTimeout(say.t);say.t=setTimeout(function(){t.style.display='none'},3200)}
window.addEventListener('offline',function(){say('You are offline. Some features need internet.')});
})();
