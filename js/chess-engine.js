/* Motor de ajedrez propio de Talvo (tablero 0x88, búsqueda alfa-beta). Sin dependencias ni costo.
   Sirve de rival (8 niveles), de pista y de análisis de errores. Corre en un Web Worker.
   También se puede usar desde Node para las pruebas: require('./chess-engine.js').Engine */
(function(root){
'use strict';
const P=1,N=2,B=3,R=4,Q=5,K=6;
const MATE=30000;
const VAL=[0,100,320,330,500,900,0];
const KN=[33,31,18,14,-33,-31,-18,-14],KG=[1,-1,16,-16,17,15,-17,-15],BD=[17,15,-17,-15],RD=[1,-1,16,-16];
const CMASK=new Uint8Array(128).fill(15);CMASK[0]=13;CMASK[4]=12;CMASK[7]=14;CMASK[112]=7;CMASK[116]=3;CMASK[119]=11;
const PST=[null,
[0,0,0,0,0,0,0,0,50,50,50,50,50,50,50,50,10,10,20,30,30,20,10,10,5,5,10,25,25,10,5,5,0,0,0,20,20,0,0,0,5,-5,-10,0,0,-10,-5,5,5,10,10,-20,-20,10,10,5,0,0,0,0,0,0,0,0],
[-50,-40,-30,-30,-30,-30,-40,-50,-40,-20,0,0,0,0,-20,-40,-30,0,10,15,15,10,0,-30,-30,5,15,20,20,15,5,-30,-30,0,15,20,20,15,0,-30,-30,5,10,15,15,10,5,-30,-40,-20,0,5,5,0,-20,-40,-50,-40,-30,-30,-30,-30,-40,-50],
[-20,-10,-10,-10,-10,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,10,10,5,0,-10,-10,5,5,10,10,5,5,-10,-10,0,10,10,10,10,0,-10,-10,10,10,10,10,10,10,-10,-10,5,0,0,0,0,5,-10,-20,-10,-10,-10,-10,-10,-10,-20],
[0,0,0,0,0,0,0,0,5,10,10,10,10,10,10,5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,0,0,0,5,5,0,0,0],
[-20,-10,-10,-5,-5,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,5,5,5,0,-10,-5,0,5,5,5,5,0,-5,0,0,5,5,5,5,0,-5,-10,5,5,5,5,5,0,-10,-10,0,5,0,0,0,0,-10,-20,-10,-10,-5,-5,-10,-10,-20],
[-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-20,-30,-30,-40,-40,-30,-30,-20,-10,-20,-20,-20,-20,-20,-20,-10,20,20,0,0,0,0,20,20,20,30,10,0,0,10,30,20]];
const KEND=[-50,-40,-30,-20,-20,-30,-40,-50,-30,-20,-10,0,0,-10,-20,-30,-30,-10,20,30,30,20,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,30,40,40,30,-10,-30,-30,-10,20,30,30,20,-10,-30,-30,-30,0,0,0,0,-30,-30,-50,-30,-30,-30,-30,-30,-30,-50];
/* tabla [pieza 0..15][casilla 0..127] con el valor posicional visto desde las blancas (negras en negativo) */
function mulberry(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)}}
const rnd=mulberry(0xC0FFEE);
const Z=[];for(let p=0;p<16;p++){Z.push(new Int32Array(128));for(let s=0;s<128;s++)Z[p][s]=rnd()|0}
const ZSIDE=rnd()|0,ZCAST=new Int32Array(16),ZEP=new Int32Array(8);
for(let i=0;i<16;i++)ZCAST[i]=rnd()|0;for(let i=0;i<8;i++)ZEP[i]=rnd()|0;
const LET={p:P,n:N,b:B,r:R,q:Q,k:K};
const SQN=s=>'abcdefgh'[s&7]+((s>>4)+1);
const NSQ=n=>(n.charCodeAt(0)-97)+(n.charCodeAt(1)-49)*16;

class Engine{
  constructor(){
    this.b=new Int8Array(128);this.side=0;this.castle=0;this.ep=-1;this.half=0;this.hash=0;this.ksq=[4,116];
    this.sp=0;const M=1024;this.stM=new Int32Array(M);this.stCap=new Int8Array(M);this.stCast=new Uint8Array(M);this.stEp=new Int16Array(M);this.stHalf=new Int16Array(M);this.stHash=new Int32Array(M);
    this.buf=[];for(let i=0;i<80;i++)this.buf.push(new Int32Array(256));
    this.sc=[];for(let i=0;i<80;i++)this.sc.push(new Int32Array(256));
    this.killers=[];for(let i=0;i<80;i++)this.killers.push([0,0]);
    this.hist=new Int32Array(128*128);
    this.nodes=0;this.stop=false;this.deadline=0;
    this.setFen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
  }
  setFen(fen){
    const t=fen.trim().split(/\s+/);this.b.fill(0);let r=7,f=0;
    for(const ch of t[0]){if(ch==='/'){r--;f=0}else if(ch>='1'&&ch<='8')f+=+ch;else{const lo=ch.toLowerCase(),p=LET[lo]|(ch===lo?8:0);const s=r*16+f;this.b[s]=p;if(lo==='k')this.ksq[ch===lo?1:0]=s;f++}}
    this.side=t[1]==='b'?1:0;const c=t[2]||'-';this.castle=(c.includes('K')?1:0)|(c.includes('Q')?2:0)|(c.includes('k')?4:0)|(c.includes('q')?8:0);
    this.ep=(t[3]&&t[3]!=='-')?NSQ(t[3]):-1;this.half=+(t[4]||0);this.sp=0;this.hash=this.fullHash();
  }
  fullHash(){let h=0;for(let s=0;s<128;s++){if(s&0x88)continue;const p=this.b[s];if(p)h^=Z[p][s]}if(this.side)h^=ZSIDE;h^=ZCAST[this.castle];if(this.ep>=0)h^=ZEP[this.ep&7];return h|0}
  isAttacked(sq,by){
    const b=this.b;let t;
    if(by===0){t=sq-15;if(!(t&0x88)&&b[t]===P)return true;t=sq-17;if(!(t&0x88)&&b[t]===P)return true}
    else{t=sq+15;if(!(t&0x88)&&b[t]===(P|8))return true;t=sq+17;if(!(t&0x88)&&b[t]===(P|8))return true}
    const o=by<<3;
    for(let i=0;i<8;i++){t=sq+KN[i];if(!(t&0x88)&&b[t]===(N|o))return true}
    for(let i=0;i<8;i++){t=sq+KG[i];if(!(t&0x88)&&b[t]===(K|o))return true}
    for(let i=0;i<4;i++){const d=BD[i];t=sq+d;while(!(t&0x88)){const p=b[t];if(p){if(p===(B|o)||p===(Q|o))return true;break}t+=d}}
    for(let i=0;i<4;i++){const d=RD[i];t=sq+d;while(!(t&0x88)){const p=b[t];if(p){if(p===(R|o)||p===(Q|o))return true;break}t+=d}}
    return false;
  }
  inCheck(){return this.isAttacked(this.ksq[this.side],this.side^1)}
  /* genera movimientos pseudo-legales en buf[ply]; devuelve cuántos */
  gen(ply,caps){
    const L=this.buf[ply],b=this.b,side=this.side;let n=0;const o=side<<3;
    for(let sq=0;sq<128;sq++){
      if(sq&0x88){sq+=7;continue}
      const p=b[sq];if(!p||(p>>3)!==side)continue;const ty=p&7;
      if(ty===P){
        const dir=side?-16:16,start=side?6:1,promoR=side?0:7;let t=sq+dir;
        if(!(t&0x88)&&b[t]===0){
          if((t>>4)===promoR){if(!caps||true){L[n++]=sq|(t<<7)|(Q<<14);if(!caps){L[n++]=sq|(t<<7)|(R<<14);L[n++]=sq|(t<<7)|(B<<14);L[n++]=sq|(t<<7)|(N<<14)}}}
          else if(!caps){L[n++]=sq|(t<<7);if((sq>>4)===start&&b[t+dir]===0)L[n++]=sq|((t+dir)<<7)|(4<<17)}
        }
        for(let k=-1;k<=1;k+=2){t=sq+dir+k;if(t&0x88)continue;const c=b[t];
          if(c&&(c>>3)!==side){if((t>>4)===promoR){L[n++]=sq|(t<<7)|(Q<<14);if(!caps){L[n++]=sq|(t<<7)|(R<<14);L[n++]=sq|(t<<7)|(B<<14);L[n++]=sq|(t<<7)|(N<<14)}}else L[n++]=sq|(t<<7)}
          else if(!c&&t===this.ep)L[n++]=sq|(t<<7)|(1<<17)}
      }else if(ty===N||ty===K){
        const D=ty===N?KN:KG;
        for(let i=0;i<8;i++){const t=sq+D[i];if(t&0x88)continue;const c=b[t];if(!c){if(!caps)L[n++]=sq|(t<<7)}else if((c>>3)!==side)L[n++]=sq|(t<<7)}
        if(ty===K&&!caps){
          const e=side?116:4,en=side^1;
          if(sq===e&&!this.isAttacked(e,en)){
            if((this.castle&(side?4:1))&&!b[e+1]&&!b[e+2]&&b[e+3]===(R|o)&&!this.isAttacked(e+1,en)&&!this.isAttacked(e+2,en))L[n++]=e|((e+2)<<7)|(2<<17);
            if((this.castle&(side?8:2))&&!b[e-1]&&!b[e-2]&&!b[e-3]&&b[e-4]===(R|o)&&!this.isAttacked(e-1,en)&&!this.isAttacked(e-2,en))L[n++]=e|((e-2)<<7)|(2<<17);
          }
        }
      }else{
        const D=ty===B?BD:ty===R?RD:KG,cnt=ty===Q?8:4;
        for(let i=0;i<cnt;i++){const d=D[i];let t=sq+d;while(!(t&0x88)){const c=b[t];if(!c){if(!caps)L[n++]=sq|(t<<7)}else{if((c>>3)!==side)L[n++]=sq|(t<<7);break}t+=d}}
      }
    }
    return n;
  }
  make(m){
    const b=this.b,from=m&127,to=(m>>7)&127,promo=(m>>14)&7,flag=(m>>17)&7,side=this.side;
    const p=b[from];let cap=b[to];const sp=this.sp;
    this.stM[sp]=m;this.stCast[sp]=this.castle;this.stEp[sp]=this.ep;this.stHalf[sp]=this.half;this.stHash[sp]=this.hash;
    let h=this.hash^ZSIDE^ZCAST[this.castle];if(this.ep>=0)h^=ZEP[this.ep&7];
    b[from]=0;h^=Z[p][from];
    if(flag&1){const cs=to+(side?16:-16);cap=b[cs];b[cs]=0;h^=Z[cap][cs]}
    else if(cap)h^=Z[cap][to];
    this.stCap[sp]=cap;
    const np=promo?(promo|(side<<3)):p;b[to]=np;h^=Z[np][to];
    if((p&7)===K){this.ksq[side]=to}
    if(flag&2){let rf,rt;if(to>from){rf=from+3;rt=from+1}else{rf=from-4;rt=from-1}const rk=b[rf];b[rf]=0;b[rt]=rk;h^=Z[rk][rf]^Z[rk][rt]}
    this.ep=(flag&4)?((from+to)>>1):-1;
    this.castle&=CMASK[from]&CMASK[to];
    this.half=((p&7)===P||cap)?0:this.half+1;
    this.side=side^1;h^=ZCAST[this.castle];if(this.ep>=0)h^=ZEP[this.ep&7];
    this.hash=h|0;this.sp=sp+1;
  }
  unmake(){
    const sp=--this.sp,m=this.stM[sp],b=this.b;this.side^=1;const side=this.side;
    const from=m&127,to=(m>>7)&127,promo=(m>>14)&7,flag=(m>>17)&7;
    let p=b[to];if(promo)p=P|(side<<3);const cap=this.stCap[sp];
    b[from]=p;
    if(flag&1){b[to]=0;b[to+(side?16:-16)]=cap}else b[to]=cap;
    if(flag&2){let rf,rt;if(to>from){rf=from+3;rt=from+1}else{rf=from-4;rt=from-1}b[rf]=b[rt];b[rt]=0}
    if((p&7)===K)this.ksq[side]=from;
    this.castle=this.stCast[sp];this.ep=this.stEp[sp];this.half=this.stHalf[sp];this.hash=this.stHash[sp];
  }
  legalMoves(ply){
    const n=this.gen(ply,false),L=this.buf[ply],out=[];
    for(let i=0;i<n;i++){const m=L[i];this.make(m);const ok=!this.isAttacked(this.ksq[this.side^1],this.side);this.unmake();if(ok)out.push(m)}
    return out;
  }
  perft(d,ply){
    if(d===0)return 1;const n=this.gen(ply,false);let c=0;
    const L=this.buf[ply],mine=new Int32Array(n);for(let i=0;i<n;i++)mine[i]=L[i];
    for(let i=0;i<n;i++){this.make(mine[i]);if(!this.isAttacked(this.ksq[this.side^1],this.side))c+=d===1?1:this.perft(d-1,ply+1);this.unmake()}
    return c;
  }
  evaluate(){
    const b=this.b;let mat=0,pos=0,wn=0,bn=0,wb=0,bb=0,wq=0,bq=0,wp=0,bp=0;
    for(let r=0;r<8;r++)for(let f=0;f<8;f++){
      const s=r*16+f,p=b[s];if(!p)continue;const ty=p&7;
      if(p<8){mat+=VAL[ty];if(ty===P)wp++;else if(ty===B){wb++;wn+=330}else if(ty===Q){wq++;wn+=900}else if(ty!==K)wn+=VAL[ty]}
      else{mat-=VAL[ty];if(ty===P)bp++;else if(ty===B){bb++;bn+=330}else if(ty===Q){bq++;bn+=900}else if(ty!==K)bn+=VAL[ty]}
    }
    const end=(wq+bq===0)||(wn<=1300&&bn<=1300);
    for(let r=0;r<8;r++)for(let f=0;f<8;f++){
      const s=r*16+f,p=b[s];if(!p)continue;const ty=p&7,white=p<8;
      const idx=white?(7-r)*8+f:r*8+f;
      let v=(ty===K&&end)?KEND[idx]:PST[ty][idx];
      pos+=white?v:-v;
    }
    let sc=mat+pos;
    if(wb>=2)sc+=30;if(bb>=2)sc-=30;
    /* final de partida con ventaja: empuja al rey rival al borde y acerca el propio (para poder dar mate) */
    const diff=(wn+wp*100)-(bn+bp*100);
    if(Math.abs(diff)>=300&&end){
      const win=diff>0?0:1,lose=win^1;const loserPawns=win?wp:bp,loserMat=win?wn:bn;
      if(loserPawns===0&&loserMat<=330){
        const lk=this.ksq[lose],wk=this.ksq[win];const lf=lk&7,lr=lk>>4,cd=Math.max(3-lf,lf-4)+Math.max(3-lr,lr-4);
        const dist=Math.abs((lk&7)-(wk&7))+Math.abs((lk>>4)-(wk>>4));
        const bonus=cd*12+(14-dist)*5;sc+=win===0?bonus:-bonus;
      }
    }
    return this.side===0?sc:-sc;
  }
  orderScores(ply,n,hm){
    const L=this.buf[ply],S=this.sc[ply],b=this.b,k=this.killers[ply];
    for(let i=0;i<n;i++){
      const m=L[i],to=(m>>7)&127,from=m&127,cap=b[to],promo=(m>>14)&7,flag=(m>>17)&7;let s=0;
      if(m===hm)s=1000000;
      else if(cap||(flag&1)){const v=flag&1?P:cap&7;s=100000+VAL[v]*10-VAL[b[from]&7]/10+(promo?VAL[promo]:0)}
      else if(promo)s=90000+VAL[promo];
      else if(m===k[0])s=80000;else if(m===k[1])s=79000;
      else s=this.hist[from*128+to];
      S[i]=s;
    }
  }
  pick(ply,i,n){
    const L=this.buf[ply],S=this.sc[ply];let bi=i,bs=S[i];
    for(let j=i+1;j<n;j++)if(S[j]>bs){bs=S[j];bi=j}
    if(bi!==i){const tm=L[i];L[i]=L[bi];L[bi]=tm;const ts=S[i];S[i]=S[bi];S[bi]=ts}
    return L[i];
  }
  isRepeat(){
    const lim=Math.max(0,this.sp-this.half);
    for(let i=this.sp-2;i>=lim;i-=2)if(this.stHash[i]===this.hash)return true;
    return false;
  }
  quiesce(alpha,beta,ply){
    this.nodes++;
    if((this.nodes&2047)===0&&Date.now()>this.deadline)this.stop=true;
    if(this.stop)return 0;
    const stand=this.evaluate();
    if(ply>=70)return stand;
    if(stand>=beta)return stand;
    if(stand>alpha)alpha=stand;
    const n=this.gen(ply,true);this.orderScores(ply,n,0);
    for(let i=0;i<n;i++){
      const m=this.pick(ply,i,n);
      if(stand+900+200<alpha&&!((m>>14)&7))continue;
      this.make(m);
      if(this.isAttacked(this.ksq[this.side^1],this.side)){this.unmake();continue}
      const sc=-this.quiesce(-beta,-alpha,ply+1);this.unmake();
      if(this.stop)return 0;
      if(sc>=beta)return sc;if(sc>alpha)alpha=sc;
    }
    return alpha;
  }
  search(depth,alpha,beta,ply){
    this.nodes++;
    if((this.nodes&2047)===0&&Date.now()>this.deadline)this.stop=true;
    if(this.stop)return 0;
    if(ply>0&&(this.half>=100||this.isRepeat()))return 0;
    const chk=this.isAttacked(this.ksq[this.side],this.side^1);
    if(chk&&ply<60)depth++;
    if(depth<=0)return this.quiesce(alpha,beta,ply);
    if(ply>=70)return this.evaluate();
    const n=this.gen(ply,false);this.orderScores(ply,n,0);
    let legal=0,best=-MATE-1;
    for(let i=0;i<n;i++){
      const m=this.pick(ply,i,n);
      this.make(m);
      if(this.isAttacked(this.ksq[this.side^1],this.side)){this.unmake();continue}
      legal++;
      const sc=-this.search(depth-1,-beta,-alpha,ply+1);
      this.unmake();
      if(this.stop)return 0;
      if(sc>best)best=sc;
      if(sc>alpha){alpha=sc;
        if(alpha>=beta){
          if(!this.b[(m>>7)&127]&&!((m>>14)&7)&&!((m>>17)&1)){const k=this.killers[ply];if(k[0]!==m){k[1]=k[0];k[0]=m}this.hist[(m&127)*128+((m>>7)&127)]+=depth*depth}
          break}}
    }
    if(!legal)return chk?-MATE+ply:0;
    return best;
  }
  /* puntúa TODAS las jugadas legales de la raíz con profundidad fija (ventana completa) */
  rootScores(depth,moves){
    const out=[];
    for(const m of moves){
      this.make(m);
      const sc=-this.search(depth-1,-MATE-10,MATE+10,1);
      this.unmake();
      if(this.stop)return null;
      out.push({m,s:sc});
    }
    return out;
  }
  /* profundización iterativa con poda en la raíz; devuelve {m, s, depth} */
  think(maxDepth,ms){
    this.nodes=0;this.stop=false;this.deadline=Date.now()+ms;
    this.hist.fill(0);for(const k of this.killers){k[0]=0;k[1]=0}
    let moves=this.legalMoves(0);if(!moves.length)return null;
    let best={m:moves[0],s:0,depth:0};
    let order=moves.slice();
    for(let d=1;d<=maxDepth;d++){
      let alpha=-MATE-10,bm=null,bs=-MATE-10;
      const res=[];
      for(const m of order){
        this.make(m);
        const sc=-this.search(d-1,-MATE-10,-alpha,1);
        this.unmake();
        if(this.stop)break;
        res.push({m,s:sc});
        if(sc>bs){bs=sc;bm=m}
        if(sc>alpha)alpha=sc;
      }
      if(this.stop||res.length<order.length){if(bm&&res.length&&d>1){/* iteración incompleta: solo se acepta si ya encontró algo mejor */ }break}
      best={m:bm,s:bs,depth:d};
      order=res.sort((a,b)=>b.s-a.s).map(x=>x.m);
      if(Math.abs(bs)>MATE-100)break;
      if(Date.now()>this.deadline)break;
    }
    return best;
  }
  uci(m){const f=m&127,t=(m>>7)&127,pr=(m>>14)&7;return SQN(f)+SQN(t)+(pr?'nbrq'[pr-2]:'')}
  fromUci(u){
    const f=NSQ(u.slice(0,2)),t=NSQ(u.slice(2,4)),pr=u[4]?{n:N,b:B,r:R,q:Q}[u[4]]:0;
    for(const m of this.legalMoves(0))if((m&127)===f&&((m>>7)&127)===t&&((m>>14)&7)===pr)return m;
    return 0;
  }
}
/* niveles pensados para aprender: del que se equivoca mucho al que casi no perdona */
const LEVELS=[null,
 {d:1,ms:300,noise:260},{d:1,ms:300,noise:110},{d:2,ms:600,noise:70},{d:3,ms:1200,noise:35},
 {d:4,ms:1800,noise:12},{d:5,ms:2500,noise:0},{d:7,ms:4000,noise:0}];
Engine.LEVELS=LEVELS;
/* elige la jugada de la máquina según el nivel (1-7) */
Engine.prototype.chooseMove=function(level){
  const cfg=LEVELS[Math.max(1,Math.min(7,level|0||3))];
  if(cfg.noise>0&&cfg.d<=3){
    const moves=this.legalMoves(0);if(!moves.length)return null;
    this.nodes=0;this.stop=false;this.deadline=Date.now()+cfg.ms*6;
    const sc=this.rootScores(cfg.d,moves)||moves.map(m=>({m,s:0}));
    let bm=sc[0],bv=-1e9;
    for(const x of sc){const v=x.s+(Math.random()*2-1)*cfg.noise;if(v>bv){bv=v;bm=x}}
    return {m:bm.m,s:bm.s,depth:cfg.d};
  }
  return this.think(cfg.d,cfg.ms);
};
/* cuánto vale la posición (para quien mueve), buscando hasta d capas o ms milisegundos */
Engine.prototype.analyze=function(d,ms){const r=this.think(d,ms);return r?{best:this.uci(r.m),score:r.s,depth:r.depth}:null};
Engine.MATE=MATE;
root.Engine=Engine;
if(typeof module!=='undefined'&&module.exports)module.exports={Engine};
/* ---- modo Worker: el navegador le manda posiciones y recibe jugadas ---- */
if(typeof self!=='undefined'&&typeof window==='undefined'&&typeof self.postMessage==='function'&&typeof importScripts==='function'){
  const eng=new Engine();
  self.onmessage=e=>{
    const d=e.data||{};
    try{
      eng.setFen(d.fen||'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
      for(const u of (d.moves||[])){const m=eng.fromUci(u);if(!m)break;eng.make(m)}
      if(d.cmd==='move'){const r=eng.chooseMove(d.level);self.postMessage({id:d.id,cmd:'move',best:r?eng.uci(r.m):null,score:r?r.s:0})}
      else if(d.cmd==='analyze'){const r=eng.analyze(d.depth||4,d.ms||1500);self.postMessage({id:d.id,cmd:'analyze',best:r&&r.best,score:r?r.score:0,depth:r?r.depth:0})}
      else if(d.cmd==='batch'){
        /* varias posiciones seguidas (repaso de una partida): avisa el avance */
        const out=[];
        (d.fens||[]).forEach((f,i)=>{eng.setFen(f);const r=eng.analyze(d.depth||3,d.ms||900);out.push(r?{best:r.best,score:r.score}:null);self.postMessage({id:d.id,cmd:'progress',i:i+1,n:d.fens.length})});
        self.postMessage({id:d.id,cmd:'batch',out});
      }
    }catch(err){self.postMessage({id:d.id,cmd:'error',error:String(err&&err.message||err)})}
  };
}
})(typeof self!=='undefined'?self:globalThis);
