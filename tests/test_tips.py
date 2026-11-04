"""Los tips (push y correo) apuntan a secciones y a imágenes que existen."""
import os,re,ast
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src=open(os.path.join(root,'app.py')).read()
a=src.index('_TIPS = [');b=src.index('_TIP_IDX')
tips=ast.literal_eval(src[a+len('_TIPS = '):b].strip())
html=open(os.path.join(root,'index.html')).read()
ids=[t[0] for t in tips];assert len(ids)==len(set(ids))
for t in tips:
    sec=t[1]
    assert 'id="sec-%s"'%sec in html,sec
    assert os.path.exists(os.path.join(root,'icons','notif-tip-%s.png'%t[2])),t[2]
    assert os.path.exists(os.path.join(root,'email','pq-tip-%s.png'%t[2])),t[2]
    assert len(t[3])==2 and len(t[4])==2 and len(t[5])==3
    assert len(t[3][1])<=110 and len(t[4][1])<=110,t[0]
print('tips OK',len(tips))
