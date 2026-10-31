const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:390,height:800}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.route('**/*',r=>{const u=r.request().url();if(u.startsWith('http://localhost:8765'))return r.continue();
 if(/supabase/.test(u))return r.fulfill({contentType:'application/javascript',body:'window.supabase={createClient:()=>({auth:{getSession:async()=>({data:{session:null}}),onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),refreshSession:async()=>({data:{}})},from:()=>({select:()=>({})})})}'});
 r.fulfill({status:200,body:''})});
await p.goto('http://localhost:8765/index.html');await p.waitForTimeout(800);
await p.evaluate(()=>{TalvoCore.state.user={id:'u'};TalvoCore.state.subscribed=true;TalvoCore.authFetch=async()=>({ok:true,json:async()=>({}),blob:async()=>new Blob(['x'])})});
const tabs=()=>p.evaluate(()=>[...document.querySelectorAll('#tabbar button')].map(b=>b.textContent.trim()+(b.classList.contains('active')?'*':'')).join('|'));
const act=()=>p.evaluate(()=>document.querySelector('.section.active').id);
console.log('en',await tabs());
for(const c of ['es','zh','chess']){
 await p.evaluate(id=>TalvoCourses.set(id,true),c);await p.waitForTimeout(300);
 console.log(c,await act(),await tabs());
 const side=await p.evaluate(()=>[...document.querySelectorAll('#main-nav button:not([hidden])')].map(b=>b.textContent.trim()).join(','));console.log(' side',side);
 await p.evaluate(()=>document.querySelector('#tabbar button:nth-child(2)').click());await p.waitForTimeout(200);console.log(' tab2',await act(),await tabs());
 await p.evaluate(()=>TalvoCore.section('home'));await p.waitForTimeout(200);console.log(' home->',await act(),await p.evaluate(()=>TalvoCourses.get()));
}
await p.evaluate(()=>TalvoCourses.set('en',true));await p.waitForTimeout(200);console.log('back en',await act(),await tabs());
console.log('errs',errs);await b.close()})();
