/* Talvo English · service worker: instalable (PWA), funciona sin internet y notificaciones push.
   Estrategia de archivos de la app: SIEMPRE se pide primero a internet (así cada despliegue nuevo llega al instante)
   y solo si no hay red se usa la copia guardada. La API (Render/Supabase) nunca pasa por aquí. */
const VERSION='talvo-v1';
const SUPA='https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4';
const SHELL=[
  './','index.html','manifest.webmanifest','css/app.css',
  'js/offline.js','js/core.js','js/extras.js','js/mouth.js','js/learning-path.js','js/phrases.js','js/studio.js','js/voice-lab.js','js/tutorial.js','js/clips-presentations.js','js/i18n.js',
  'img/3be2953dd7.png','img/573023fda0.webp','img/5ef4891258.webp','img/616c0afe99.webp','img/69dc6ead34.webp','img/6f23951225.webp','img/8e1f1641d1.png','img/9abc8766f9.webp','img/afcfde06be.webp','img/d7b8a9c181.webp',
  'palanqueta-a.webp','palanqueta-asoma.webp','palanqueta-mascota.webp','logo-bienvenida.png',
  'icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png','icons/pq-icon.png','icons/pq-badge.png'
];
self.addEventListener('install',e=>{
  e.waitUntil((async()=>{
    const cache=await caches.open(VERSION);
    /* uno por uno: si un archivo falla, el resto se guarda igual y la instalación no se cae */
    await Promise.all(SHELL.map(u=>cache.add(new Request(u,{cache:'reload'})).catch(()=>{})));
    try{await cache.put(SUPA,await fetch(SUPA,{mode:'no-cors'}))}catch(_){}
    self.skipWaiting();
  })());
});
self.addEventListener('activate',e=>{
  e.waitUntil((async()=>{
    const ks=await caches.keys();
    await Promise.all(ks.filter(k=>k.startsWith('talvo-')&&k!==VERSION).map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
/* Un navegador rechaza una respuesta "redirigida" para una navegación (sale el dinosaurio). Se re-envuelve limpia. */
async function clean(r){
  if(!r||!r.redirected)return r;
  const body=await r.blob();
  return new Response(body,{status:200,statusText:'OK',headers:r.headers});
}
function withTimeout(p,ms){return new Promise((res,rej)=>{const t=setTimeout(()=>rej(new Error('timeout')),ms);p.then(v=>{clearTimeout(t);res(v)},e=>{clearTimeout(t);rej(e)})})}
async function networkFirst(req){
  const cache=await caches.open(VERSION);
  try{
    const r0=await withTimeout(fetch(req),req.mode==='navigate'?7000:9000);
    const r=req.mode==='navigate'?await clean(r0):r0;
    if(r&&r.ok&&r.type==='basic'){cache.put(req,r.clone()).catch(()=>{});if(req.mode==='navigate')cache.put('./',r.clone()).catch(()=>{})}
    return r;
  }catch(_){
    const hit=await cache.match(req,{ignoreSearch:true});
    if(hit)return clean(hit);
    if(req.mode==='navigate'){const home=(await cache.match('./'))||(await cache.match('index.html'));if(home)return clean(home)}
    return Response.error();
  }
}
async function cacheFirst(req){
  const cache=await caches.open(VERSION);
  const hit=await cache.match(req);
  if(hit)return hit;
  const r=await fetch(req);
  if(r&&(r.ok||r.type==='opaque'))cache.put(req,r.clone()).catch(()=>{});
  return r;
}
async function staleWhileRevalidate(req){
  const cache=await caches.open(VERSION);
  const hit=await cache.match(req);
  const net=fetch(req).then(r=>{if(r&&(r.ok||r.type==='opaque'))cache.put(req,r.clone()).catch(()=>{});return r}).catch(()=>null);
  return hit||(await net)||Response.error();
}
self.addEventListener('fetch',e=>{
  const req=e.request;
  if(req.method!=='GET')return;
  let url;try{url=new URL(req.url)}catch(_){return}
  if(url.origin===self.location.origin){
    if(url.pathname.endsWith('/sw.js'))return;
    e.respondWith(networkFirst(req));return;
  }
  if(req.url===SUPA){e.respondWith(cacheFirst(req));return}
  if(url.hostname==='fonts.googleapis.com'||url.hostname==='fonts.gstatic.com'){e.respondWith(staleWhileRevalidate(req));return}
  /* todo lo demás (API del servidor, Supabase, Turnstile…) va directo a internet */
});
self.addEventListener('push',e=>{
  let d={};
  try{d=e.data?e.data.json():{}}catch(_){d={body:e.data?e.data.text():''}}
  const mood=['cheer','streak','miss','verify'].includes(d.mood)?d.mood:'cheer';
  const en=d.lang==='en';
  e.waitUntil((async()=>{
    /* Si la app está abierta, también muestra el aviso animado dentro de la app. */
    const list=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    list.forEach(c=>{try{c.postMessage({type:'talvo-push',title:d.title||'Talvo English',body:d.body||'',mood})}catch(_){}});
    await self.registration.showNotification(d.title||'Talvo English',{
      body:d.body||'',icon:'icons/pq-icon.png',badge:'icons/pq-badge.png',image:'icons/notif-'+mood+'.png',
      tag:d.tag||'talvo',renotify:true,vibrate:[120,60,120,60,220],
      actions:[{action:'open',title:en?'Practice now':'Practicar ahora'}],
      data:{url:d.url||'./?pq='+mood},lang:en?'en':'es'
    });
  })());
});
self.addEventListener('notificationclick',e=>{
  e.notification.close();
  const url=new URL((e.notification.data&&e.notification.data.url)||'./',self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{
    for(const c of list){if(c.url.startsWith(self.registration.scope)&&'focus' in c){return c.focus()}}
    return self.clients.openWindow(url);
  }));
});
