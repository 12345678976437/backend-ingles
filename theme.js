window.TalvoTheme=(function(){
  const T={"cyan": ["Cyan", "#3ee8ff", "#7c78ff"], "green": ["Green", "#3dff9a", "#00c2a8"], "red": ["Red", "#ff4d5e", "#ff8a4c"], "pink": ["Pink", "#ff5cc8", "#9b6bff"], "orange": ["Orange", "#ffa52e", "#ff5e3a"], "violet": ["Violet", "#a78bff", "#4f8cff"], "blue": ["Blue", "#4da3ff", "#3ee8ff"], "lime": ["Lime", "#d4ff3a", "#3dff9a"]};
  const rgb=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)).join(',');
  const dark=h=>'#'+[1,3,5].map(i=>Math.round(parseInt(h.slice(i,i+2),16)*.72).toString(16).padStart(2,'0')).join('');
  function apply(name){
    if(!T[name])name='cyan';
    const c1=T[name][1],c2=T[name][2],r=document.documentElement.style;
    r.setProperty('--cyan',c1);r.setProperty('--c1-rgb',rgb(c1));
    r.setProperty('--primary',c2);r.setProperty('--primary2',dark(c2));r.setProperty('--c2-rgb',rgb(c2));
    r.setProperty('--signal','linear-gradient(90deg,'+c1+','+c2+')');
    try{localStorage.setItem('talvo_theme',name)}catch(e){}
    document.querySelectorAll('#theme-picker .swatch').forEach(b=>b.setAttribute('aria-pressed',b.dataset.theme===name?'true':'false'));
    return name;
  }
  function current(){try{return localStorage.getItem('talvo_theme')||'cyan'}catch(e){return 'cyan'}}
  return {themes:T,apply:apply,current:current};
})();
window.TalvoTheme.apply(window.TalvoTheme.current());