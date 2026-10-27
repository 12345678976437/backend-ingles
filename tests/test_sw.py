"""Que el service worker guarde TODO lo que la app necesita sin internet: python3 tests/test_sw.py"""
import os, re
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sw = open(os.path.join(R, 'sw.js'), encoding='utf-8').read()
shell = set(re.findall(r"'([^']+\.(?:js|css|png|webp|webmanifest|html))'", sw.split('const SHELL=[')[1].split('];')[0]))
need = set()
for d, ext in (('js', '.js'), ('css', '.css'), ('img', ('.png', '.webp'))):
    for f in os.listdir(os.path.join(R, d)):
        if f.endswith(ext):
            need.add(f'{d}/{f}')
html = open(os.path.join(R, 'index.html'), encoding='utf-8').read()
for m in re.findall(r'(?:src|href)="([^":#?]+\.(?:js|css|png|webp|webmanifest))"', html):
    need.add(m)
missing = sorted(need - shell)
assert not missing, f'Falta en SHELL de sw.js: {missing}'
gone = sorted(f for f in shell if not os.path.exists(os.path.join(R, f)) and f not in ('./',))
assert not gone, f'SHELL apunta a archivos que no existen: {gone}'
assert 'networkFirst' in sw and "req.method!=='GET'" in sw and "talvo-v" in sw
assert html.index('js/offline.js') < html.index('js/core.js')
print('sw OK', len(shell), 'archivos')
