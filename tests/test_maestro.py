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
