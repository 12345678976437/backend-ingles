"""Modo maestra bilingüe (sin Internet): python3 tests/test_maestro.py"""
import sys, importlib.util, os
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
import stubs
spec=importlib.util.spec_from_file_location('appn',os.path.join(HERE,'..','app.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ssml=m._bilingual_ssml('Di conmigo: "How\'s it going?" Eso significa "¿Cómo vas?" & más.', m._DEFAULT_VOICE)
assert "<lang xml:lang='en-US'><prosody rate='-8%'>How&apos;s it going?" in ssml or "How's it going?" in ssml, ssml
assert "es-MX'>Di conmigo:" in ssml and "&amp;" in ssml
p=m.build_tutor_system_prompt('A2','', 'maestro','')
assert 'SPANISH' in p and 'double quotes' in p
assert 'LIVE VOICE CALL' not in p
for k,v in m.PLAN_FEATURES.items(): assert v['maestro_dia']>0
assert [m.PLAN_FEATURES[k]['maestro_dia'] for k in ('gratis','basico','pro','max')]==sorted(m.PLAN_FEATURES[k]['maestro_dia'] for k in ('gratis','basico','pro','max'))
print('maestro OK')
e1=m.build_exam_prompt(1); e8=m.build_exam_prompt(8)
assert 'EXAM MODE' in e1 and 'question 1 of 8' in e1 and 'LAST' in e8
assert m._CEFR_TO_LEVEL['B1']=='intermediate'
assert [m.PLAN_FEATURES[k]['examen_mes'] for k in ('gratis','basico','pro','max')]==[1,4,10,30]
print('examen OK')
# clase como maestro humano
new=m.build_tutor_system_prompt('A2','','maestro','',ficha={},clases=1,clase_n=1)
assert 'Nice to meet you' in new and 'new student' in new
back=m.build_tutor_system_prompt('A2','','maestro','',ficha={'nombre':'Ana','gustos':['cocinar']},clases=3,clase_n=1)
assert 'RETURNING' in back and 'Ana' in back
assert 'WRAP UP' in m._class_plan({}, 1, 12) and 'role-play' in m._class_plan({'nombre':'Ana'}, 3, 10)
print('clase OK')
# temario escuela + calle
assert len(m.TEACHER_SYLLABUS)>=15 and m._syllabus_unit({}, 'A2')[0]==6 and m._syllabus_unit({'unidad':99}, None)[0]==len(m.TEACHER_SYLLABUS)-1
pl=m._class_plan({'nombre':'Ana'},3,6,'A1'); assert 'SCHOOL BASE' in pl and 'CURRICULUM UNIT 1' in pl
assert 'REAL LIFE' in m._class_plan({'nombre':'Ana'},3,7,'A1') and 'UNDERSTAND THEM' in m._class_plan({'nombre':'Ana'},3,8,'A1')
assert 'STREET ENGLISH' in m.build_tutor_system_prompt('A1','','maestro','',ficha={'nombre':'Ana'},clases=2,clase_n=6)
print('temario OK')
assert any(u['code']=='grammar_basics' for u in m.LEARNING_UNITS) and all(c in {x for s in m.SECTION_DEFS for x in s['units']} for c in ('spoken_real','grammar_build','grammar_pro'))
print('rutas OK')
assert m._syllabus_unit({}, 'C1')[0]==19 and m._syllabus_unit({}, 'B1')[0]==13
assert any(r.rule.startswith('/api/maestro/temario') for r in m.app.url_map.iter_rules())
print('mapa OK')
assert len(m.TEACHER_ROUTE_MAP)==len(m.TEACHER_SYLLABUS)
for uc,lid in m.TEACHER_ROUTE_MAP:
    assert m.get_lesson(m.get_unit(uc),lid),(uc,lid)
# ruta -> ficha
saved={}
m._ficha_get=lambda uid:{"ficha":{"nombre":"Ana","en_rutas":[]},"clases":2}
m._ficha_save=lambda uid,ficha=None,clases=None:saved.update(f=ficha)
m._ficha_note_route("u1","grammar_basics","to_be",70,[{"en":"I am tired"}])
assert saved["f"]["en_rutas"][0]["leccion"].startswith("The verb to be") and saved["f"]["para_repasar"]==["I am tired"],saved
assert "en_rutas" in m.build_tutor_system_prompt('A1','','maestro','',ficha={'en_rutas':[1]},clases=2,clase_n=1)
print('puente OK')
# transcripción bilingüe: gana el idioma más seguro y nunca se pasan frases de la lección
res={}
m._stt_once=lambda w,l,n=(): res[l]
res.update({"en-US":("Caleb",0.91),"es-MX":("Canet",0.55)}); assert m.stt_bilingual("x")=="Caleb"
res.update({"en-US":("Me you want",0.3),"es-MX":("Me llamo Caleb",0.88)}); assert m.stt_bilingual("x")=="Me llamo Caleb"
res.update({"en-US":("",0.0),"es-MX":("hola",0.7)}); assert m.stt_bilingual("x")=="hola"
assert "NEVER A YES-MAN" in m.TEACHER_PROMPT and "Do NOT reveal" in m.TEACHER_PROMPT
print('stt OK')
# basura tipo "0138" no se acepta como transcripción
assert not m._plausible("0138",0.9) and not m._plausible("-",0.9) and not m._plausible("hola",0.1) and m._plausible("Caleb",0.8)
res.update({"en-US":("0138",0.8),"es-MX":("",0.0)}); assert m.stt_bilingual("x")==""
# frase meta: solo cuando la maestra pidió repetir; usa la última frase entre comillas
h=[{"role":"assistant","content":'Muy bien. Ahora repite conmigo: "How\'s it going?" Dilo despacio.'}]
assert m._target_phrase(h)=="How's it going?"
assert m._target_phrase([{"role":"assistant","content":'Eso se dice "How\'s it going?" y significa qué tal.'}])==""
assert m._target_phrase([])==""
# Pronunciation Assessment contra la frase meta (simulado)
m.assess_pronunciation=lambda w,t:{"transcript":"How's it going","pronunciation_score":72.4,"completeness_score":100,"words":[{"word":"How's","accuracy":90},{"word":"it","accuracy":85},{"word":"going","accuracy":41}]}
pr=m._pron_check("x","How's it going?"); assert pr["score"]==72 and pr["words"][2]=={"w":"going","a":41}
assert "going (41)" in m._pron_note(pr) and "do NOT say it was perfect" in m._pron_note(pr)
m.assess_pronunciation=lambda w,t:{"transcript":"no entiendo","pronunciation_score":10,"completeness_score":0,"words":[]}
assert m._pron_check("x","How's it going?") is None   # contestó otra cosa: no cuenta como intento
print('pron OK')
# comillas con español se leen en español; el inglés sigue en inglés
sx=m._bilingual_ssml('Di conmigo: "How are you?" y luego "¿cómo dices cómo estás hoy?" ok', m._DEFAULT_VOICE)
assert sx.count("xml:lang='en-US'")==1 and "How are you?" in sx.split("xml:lang='en-US'")[1][:60]
assert not m._looks_spanish('"How are you doing today?"') and m._looks_spanish('"¿cómo estás hoy?"')
assert 'CANNOT HEAR' in m.TEACHER_PROMPT and 'ONE task per turn' in m.TEACHER_PROMPT
print('capturas OK')
