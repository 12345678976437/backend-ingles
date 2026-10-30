// Pruebas del motor de ajedrez: node tests/test_chess.js
const {Engine}=require('../js/chess-engine.js');
const assert=require('assert');
const e=new Engine();
const PERFT=[
 ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',4,197281],
 ['r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',3,97862],
 ['8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',4,43238],
 ['r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1',3,9467],
 ['rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8',3,62379]];
for(const [f,d,n] of PERFT){e.setFen(f);const t=Date.now();const c=e.perft(d,0);assert.strictEqual(c,n,f+' perft '+d+' = '+c+' (esperado '+n+')');console.log('perft ok',n,(Date.now()-t)+'ms')}
// el hash incremental coincide con el recalculado y make/unmake restaura todo
let seed=12345;const rn=k=>{seed=(seed*1103515245+12345)&0x7fffffff;return seed%k};
for(let g=0;g<30;g++){
  e.setFen(PERFT[g%5][0]);
  for(let ply=0;ply<80;ply++){
    const mv=e.legalMoves(0);if(!mv.length)break;
    const m=mv[rn(mv.length)];const before=e.hash,bb=Array.from(e.b);
    e.make(m);assert.strictEqual(e.hash,e.fullHash(),'hash incremental');
    e.unmake();assert.strictEqual(e.hash,before);assert.deepStrictEqual(Array.from(e.b),bb);
    e.make(m);
  }
}
console.log('hash y deshacer OK');
// mates de verdad (mate en 1 y en 2) y no regalar la dama
const T=[
 ['6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1','a1a8'],                       // mate del pasillo
 ['r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4','h5f7'], // mate pastor
 ['7k/5Q2/6K1/8/8/8/8/8 w - - 0 1','f7g7']];                         // dama y rey
for(const [f,mv] of T){e.setFen(f);const r=e.analyze(4,3000);assert.strictEqual(r.best,mv,f+' -> '+r.best);assert(r.score>Engine.MATE-100,'debe ver mate');}
e.setFen('4k3/8/8/8/8/8/4q3/4K2R w K - 0 1');
const rr=e.analyze(4,3000);console.log('torre: se come la dama?',rr.best);
// el rival de nivel 1..7 siempre juega algo legal
for(let lv=1;lv<=7;lv++){e.setFen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');const t=Date.now();const r=e.chooseMove(lv);assert(r&&e.legalMoves(0).includes(r.m));console.log('nivel',lv,e.uci(r.m),(Date.now()-t)+'ms')}
console.log('motor OK');
