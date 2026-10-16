/* Talvo English · service worker: instalable (PWA) + notificaciones push. Sin caché agresiva. */
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('talvo-')).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('push',e=>{
  let d={};
  try{d=e.data?e.data.json():{}}catch(_){d={body:e.data?e.data.text():''}}
  e.waitUntil(self.registration.showNotification(d.title||'Talvo English',{
    body:d.body||'',icon:'icons/icon-192.png',badge:'icons/icon-192.png',
    tag:d.tag||'talvo',data:{url:d.url||'./'},lang:'es'
  }));
});
self.addEventListener('notificationclick',e=>{
  e.notification.close();
  const url=new URL((e.notification.data&&e.notification.data.url)||'./',self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{
    for(const c of list){if(c.url.startsWith(self.registration.scope)&&'focus' in c){return c.focus()}}
    return self.clients.openWindow(url);
  }));
});
