/* Talvo · service worker (generado automáticamente). Cambia solo cuando cambian los archivos. */
const VERSION='talvo-41579fd3e5';
const CORE=["./", "assets/img-039fa38f.webp", "assets/img-2aa8b477.webp", "assets/img-4145c7f0.png", "assets/img-4b463dd2.webp", "assets/img-5f908050.webp", "assets/img-66c6cea6.webp", "assets/img-a0344521.webp", "assets/img-ac1046cd.png", "assets/img-e38bc3f3.webp", "assets/img-f298199c.webp", "css/app.css", "icons/apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "index.html", "js/app.js", "js/extras.js", "js/i18n.js", "js/theme.js", "manifest.webmanifest"];
self.addEventListener('install',e=>{e.waitUntil(caches.open(VERSION).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==VERSION&&k.startsWith('talvo-')).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
async function networkFirst(req){
  try{const r=await fetch(req);if(r&&r.ok){const c=await caches.open(VERSION);c.put(req,r.clone())}return r}
  catch(e){const hit=await caches.match(req,{ignoreSearch:true});if(hit)return hit;if(req.mode==='navigate'){const idx=await caches.match('index.html');if(idx)return idx}throw e}
}
async function cacheFirst(req){
  const hit=await caches.match(req,{ignoreSearch:true});if(hit)return hit;
  const r=await fetch(req);if(r&&r.ok){const c=await caches.open(VERSION);c.put(req,r.clone())}return r;
}
self.addEventListener('fetch',e=>{
  const req=e.request;if(req.method!=='GET')return;
  const url=new URL(req.url);
  if(url.origin===location.origin){
    if(req.mode==='navigate'||/\.(html|css|js|webmanifest)$/.test(url.pathname))e.respondWith(networkFirst(req));
    else e.respondWith(cacheFirst(req));
    return;
  }
  /* fuentes de Google: se guardan para que carguen sin conexión */
  if(url.hostname==='fonts.googleapis.com'||url.hostname==='fonts.gstatic.com')e.respondWith(cacheFirst(req));
  /* el resto (tu API, Supabase) nunca se intercepta ni se guarda */
});
