"""Prueba de humo del reto de 21 días (sin Internet): python3 tests/test_reto.py"""
import sys, types, importlib.util, json, uuid
import os
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
import stubs
spec=importlib.util.spec_from_file_location('appn',os.path.join(HERE,'..','app.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class Res:
    def __init__(s,d): s.data=d
class Q:
    def __init__(s,db,t): s.db=db;s.t=t;s.f=[];s.op='select';s.pl=None;s.lim=None;s.ord=None
    def select(s,*a,**k): return s
    def eq(s,c,v): s.f.append(('eq',c,v));return s
    def gte(s,c,v): s.f.append(('gte',c,v));return s
    def ilike(s,c,v): s.f.append(('eq',c,v));return s
    def limit(s,n): s.lim=n;return s
    def order(s,c,desc=False): s.ord=(c,desc);return s
    def insert(s,p): s.op='insert';s.pl=p;return s
    def update(s,p): s.op='update';s.pl=p;return s
    def delete(s): s.op='delete';return s
    def upsert(s,p): s.op='insert';s.pl=p;return s
    def match(s,r): return all((r.get(c)==v) if k=='eq' else (str(r.get(c))>=v) for k,c,v in s.f)
    def execute(s):
        rows=s.db.setdefault(s.t,[])
        if s.op=='insert':
            r=dict(s.pl); r.setdefault('id',str(uuid.uuid4())); r.setdefault('created_at','2026-10-10T10:00:00+00:00'); rows.append(r); return Res([r])
        if s.op=='update':
            for r in rows:
                if s.match(r): r.update(s.pl)
            return Res([])
        if s.op=='delete':
            s.db[s.t]=[r for r in rows if not s.match(r)]; return Res([])
        out=[r for r in rows if s.match(r)]
        if s.ord: out.sort(key=lambda r:r.get(s.ord[0]) or '',reverse=s.ord[1])
        if s.lim: out=out[:s.lim]
        return Res(out)
class DB:
    def __init__(s): s.d={}
    def table(s,t): return Q(s.d,t)
db=DB(); db.d['profiles']=[{'id':'u1','cefr_level':'elementary','daily_goal_minutes':10}]
m.supabase_admin=db; m.supabase=db
m.ai_client=object()
U=types.SimpleNamespace(id='u1',email='a@b.c')
m.authenticated_user=lambda:(U,None)
def fake(system,user,temperature=0.5):
    if 'fixed 21-day' in system:
        return {"title":"Vender queso","emoji":"🧀","summary_es":"x","days":[{"title":f"Day {i} t","focus_es":"f"} for i in range(1,22)],"roleplay":{"setup":"s","ai_role":"c","user_role":"u","goal":"g","opening":"Hi"}}
    print('TONE:',[l for l in system.split('\n') if 'learner' in l.lower() and 'Return' not in l][:2])
    return {"title":"T","note_es":"n","words":[{"en":f"w{uuid.uuid4().hex[:5]}","es":"p"} for _ in range(8)],"phrases":[{"en":f"I need {uuid.uuid4().hex[:4]} please","es":"lo necesito"} for _ in range(6)],"dialogs":[{"q":"Hi?","a":"Hello","wrong":["Bye","No"]}]*3}
m.ai_json=fake
c=m.app.test_client()
r=c.post('/api/reto21/crear',json={"pedido":"vender queso artesanal a clientes","tz":"America/Mexico_City"}); print(r.status_code, r.json['ruta']['tipo'])
rid=r.json['ruta']['id']
print(c.post('/api/reto21/dia',json={"route_id":rid,"lesson_id":"d1"}).json)
print(c.post('/api/reto21/dia',json={"route_id":rid,"lesson_id":"d2"}).status_code, "(d2 locked)")
d=c.get('/api/rutas/'+rid).json; print(len(d['lecciones']),d['lecciones'][0]['state'],d['lecciones'][1]['state'],d['reto']['racha'])
l=c.get(f'/api/rutas/{rid}/leccion/d1'); print(l.status_code, len(l.json.get('exercises',[])))
r=c.post(f'/api/rutas/{rid}/completar',json={"lesson_id":"d1","total":10,"correct":5,"seconds":60,"mistakes":[{"en":"cheese","es":"queso"}]}); print(r.json.get('passed'),r.json.get('score'))
r=c.post(f'/api/rutas/{rid}/completar',json={"lesson_id":"d1","total":10,"correct":9,"seconds":60,"mistakes":[{"en":"cheese","es":"queso"}]}); print(r.json.get('passed'))
d=c.get('/api/rutas/'+rid).json; print(d['lecciones'][1]['state'],d['lecciones'][1]['wait'])
# simulate next day
rt=[x for x in db.d['rutas_personalizadas']][0]; rt['meta']['start']='2020-01-01'
print(c.post('/api/reto21/dia',json={"route_id":rid,"lesson_id":"d2"}).json, rt['meta']['log'])
print(c.get('/api/rutas').json['reto']['dia_hoy'], len(c.get('/api/rutas').json['rutas']))
# --- listening check
l=c.get(f'/api/rutas/{rid}/leccion/d1').json
chk=[e for e in l['exercises'] if e.get('check')]
print('check exercises:',len(chk), l.get('listen_check'))
r=c.post(f'/api/rutas/{rid}/completar',json={"lesson_id":"d1","total":14,"correct":13,"seconds":60,"mistakes":[],"listen":{"ok":3,"n":4}}); print(r.json.get('passed'))
d=c.get('/api/rutas/'+rid).json; print(d['reto']['escucha'])
assert len(chk)==4, len(chk)
