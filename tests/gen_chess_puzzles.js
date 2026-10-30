// Genera js/chess-puzzles.js con problemas de mate verificados por el motor:  node tests/gen_chess_puzzles.js
const {Engine}=require('../js/chess-engine.js');
global.window={};eval(require('fs').readFileSync(__dirname+'/../js/vendor/chess.js','utf8'));
const E=new Engine(),MATE=Engine.MATE;
let seed=20261029;const rn=()=>{seed=(seed*1103515245+12345)&0x7fffffff;return seed/0x7fffffff};
const have=new Set(),m1=[],m2=[];
function mating(){const out=[];for(const m of E.legalMoves(0)){E.make(m);const chk=E.inCheck();const rep=E.legalMoves(1).length;E.unmake();if(chk&&rep===0)out.push(m)}return out}
function pieces(fen){return (fen.split(' ')[0].match(/[a-zA-Z]/g)||[]).length}
let games=0;
while((m1.length<40||m2.length<40)&&games<300){
  games++;const c=new window.Chess();const mv=[];
  for(let ply=0;ply<120&&!c.isGameOver();ply++){
    E.setFen(new window.Chess().fen());for(const u of mv)E.make(E.fromUci(u));
    if(ply>=10){
      const fen=c.fen(),key=fen.split(' ').slice(0,2).join(' ');
      if(!have.has(key)&&pieces(fen)>=6){
        const mm=mating();
        if(mm.length===1&&m1.length<40){have.add(key);m1.push(fen)}
        else if(mm.length===0&&m2.length<40&&ply%2===0&&!E.inCheck()){
          const sc=E.rootScores(3,E.legalMoves(0));
          if(sc){const w=sc.filter(x=>x.s>=MATE-3);if(w.length===1){have.add(key);m2.push(fen)}}
        }
      }
    }
    if(games%10===0&&ply===0)console.error('partidas',games,'m1',m1.length,'m2',m2.length);
    const lv=1+Math.floor(rn()*3);const r=E.chooseMove(lv);if(!r)break;
    const u=E.uci(r.m);c.move({from:u.slice(0,2),to:u.slice(2,4),promotion:u[4]});mv.push(u);
  }
}
const sort=a=>a.sort((x,y)=>pieces(x)-pieces(y)||(x<y?-1:1));
sort(m1);sort(m2);
const out='/* Problemas de mate generados y verificados por el motor (tests/gen_chess_puzzles.js). [FEN]. m1 = mate en 1, m2 = mate en 2 (única primera jugada). */\nwindow.CHESS_PUZZLES={m1:'+JSON.stringify(m1)+',m2:'+JSON.stringify(m2)+'};\n';
require('fs').writeFileSync(__dirname+'/../js/chess-puzzles.js',out);
console.log('partidas',games,'mate en 1:',m1.length,'mate en 2:',m2.length);
