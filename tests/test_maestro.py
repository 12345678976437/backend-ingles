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
