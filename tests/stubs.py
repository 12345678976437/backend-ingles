import sys, types
def stub(name, **attrs):
    try:
        __import__(name); return
    except Exception:
        pass
    parts = name.split(".")
    for i in range(1, len(parts)+1):
        n = ".".join(parts[:i])
        if n not in sys.modules:
            sys.modules[n] = types.ModuleType(n)
        if i > 1:
            setattr(sys.modules[".".join(parts[:i-1])], parts[i-1], sys.modules[n])
    for k, v in attrs.items():
        setattr(sys.modules[name], k, v)
class _Any:
    def __init__(self,*a,**k): pass
    def __call__(self,*a,**k): return _Any()
    def __getattr__(self,k): return _Any()
stub("flask_cors", CORS=lambda *a, **k: None)
stub("dotenv", load_dotenv=lambda *a, **k: None)
stub("openai", OpenAI=_Any, AzureOpenAI=_Any)
stub("pydub", AudioSegment=_Any)
stub("azure.cognitiveservices.speech")
stub("supabase", Client=_Any, create_client=lambda *a, **k: None)
