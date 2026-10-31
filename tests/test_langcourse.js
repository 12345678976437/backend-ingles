const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:390,height:800}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.setContent('<html><body><section id="sec-espanol"><div id="lc-es-root"></div></section><section id="sec-chino"><div id="lc-zh-root"></div></section></body></html>');
await p.evaluate(()=>{window.TalvoCore={esc:s=>s,toast:m=>window.__t=m,authFetch:async(u,o)=>({ok:true,blob:async()=>new Blob(['x']),json:async()=>({})}),jsonFetch:async()=>({respuesta:'你好！你叫什么名字？',pinyin:'nǐ hǎo! nǐ jiào shénme míngzi?',significado:'Hello! What is your name?',correccion:'',explicacion:''})};HTMLMediaElement.prototype.play=async()=>{}});
for(const f of ['course-es','course-zh','lang-course'])await p.addScriptTag({path:'js/'+f+'.js'});
for(const [sec,root] of [['espanol','lc-es-root'],['chino','lc-zh-root']]){
 await p.evaluate(s=>TalvoLang.onSection(s),sec);const id=sec==='espanol'?'es':'zh';
 const home=await p.locator('#'+root+' .lc-next').count();await p.evaluate(i=>TalvoLang.view(i,'learn'),id);
 const n=await p.locator('#'+root+' [data-lc-unit]').count();
 await p.click('#'+root+' [data-lc-unit]:nth-child(2)');
 const items=await p.locator('#'+root+' .lc-item').count();
 await p.click('#'+root+' [data-lc-quiz]');
 for(let i=0;i<8;i++){await p.click('#'+root+' [data-lc-opt]:nth-child(1)');await p.click('#'+root+' [data-lc-next]')}
 const end=await p.locator('#'+root+' .lc-end').count();
 console.log(sec,'units',n,'items',items,'end',end);
 await p.click('#'+root+' [data-lc-unit]');await p.click('#'+root+' [data-lc-back]');console.log('home card',home);await p.evaluate(i=>TalvoLang.view(i,'speak'),id);console.log('speak',await p.locator('#'+root+' [data-lc-spmic]').count());
 await p.evaluate(i=>TalvoLang.view(i,'vocab'),id);await p.click('#'+root+' [data-lc-vstart]');let nc=0;
 while(await p.locator('#'+root+' [data-lc-vflip]').count()){await p.click('#'+root+' [data-lc-vflip]');await p.click('#'+root+' [data-lc-vg="1"]');nc++;if(nc>30)break}
 console.log("vocab cards",nc,'done',await p.locator('#'+root+' [data-lc-vexit]').count());await p.click('#'+root+' [data-lc-vexit]');
 await p.evaluate(i=>TalvoLang.view(i,'roles'),id);await p.click('#'+root+' [data-lc-role]');console.log('role open',await p.locator('#'+root+' .lc-b.tu').count());await p.fill('#'+root+' #lc-in','hola');await p.press('#'+root+' #lc-in','Enter');await p.waitForSelector('#'+root+' .lc-b.me');console.log('role bubbles',await p.locator('#'+root+' .lc-b').count());
 await p.evaluate(i=>TalvoLang.view(i,'tutor'),id);await p.fill('#'+root+' #lc-in','hola');await p.press('#'+root+' #lc-in','Enter');
 await p.waitForSelector('#'+root+' .lc-b.tu',{timeout:3000}).catch(()=>{console.log('ERRS',errs)});console.log('tutor ok',await p.locator('#'+root+' .lc-b').count());
}
console.log('errs',errs);await b.close()})();
