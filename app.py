import json
import os
import random
import re
import tempfile
import threading
import time
import hashlib
import math
import platform
import requests
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape as _xml_escape
from collections import defaultdict, deque, OrderedDict
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, g, stream_with_context
from flask_cors import CORS
from openai import OpenAI
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from supabase import Client, create_client

load_dotenv()

app = Flask(__name__)
_ALLOWED = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]
# ALLOWED_ORIGINS (Render > Environment): dominios del front separados por coma. Vacío = cualquiera (menos seguro).
CORS(app, origins=_ALLOWED or "*", allow_headers=["Authorization", "Content-Type"], methods=["GET", "POST", "OPTIONS"],
     supports_credentials=False, max_age=600)


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if request.path.startswith("/api") or request.path.startswith("/analizar") or request.path.startswith("/evaluar"):
        resp.headers["Cache-Control"] = "no-store"
    return resp
# Límite de tamaño de subida (audios): evita que un archivo enorme te cueste procesamiento.
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024


@app.errorhandler(Exception)
def _unhandled(exc):
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return jsonify({"ok": False, "error": exc.description if exc.code in (400, 404, 405, 413) else "Solicitud no válida."}), exc.code
    print(f"[UNHANDLED] {request.path}: {exc}")
    return jsonify({"ok": False, "error": "Ocurrió un error en el servidor. Inténtalo de nuevo."}), 500


@app.errorhandler(413)
def too_large(_exc):
    return jsonify({"ok": False, "error": "El archivo es demasiado grande."}), 413

def env(name, default=""):
    return (os.getenv(name) or default).strip()

AZURE_SPEECH_KEY = env("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = env("AZURE_SPEECH_REGION", "westus3")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", "")
# Cuentas con acceso al panel de administración (separa varias con comas en ADMIN_EMAIL).
ADMIN_EMAILS = {e.strip().lower() for e in env("ADMIN_EMAIL", "a07077189@tec.mx").split(",") if e.strip()}


def is_admin_user(user):
    """Admin solo si el correo coincide Y está confirmado (evita que alguien registre ese correo sin verificarlo)."""
    if (getattr(user, "email", "") or "").lower() not in ADMIN_EMAILS:
        return False
    if hasattr(user, "email_confirmed_at") and not getattr(user, "email_confirmed_at"):
        return False
    return True
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = env("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = env("SUPABASE_KEY")
# Service role key: SOLO se usa en el servidor, nunca se envía al frontend.
# Se consigue en Supabase > Project Settings > API > service_role secret.
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase conectado.")
    except Exception as exc:
        print(f"[WARN] Supabase no pudo conectarse: {exc}")

# Cliente "admin": usa la service_role key, que ignora RLS.
# Lo usamos SOLO después de haber verificado la identidad del usuario
# con supabase.auth.get_user(token), así que es seguro consultar por user.id.
supabase_admin: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("[OK] Supabase (admin/service_role) conectado.")
    except Exception as exc:
        print(f"[WARN] Supabase admin no pudo conectarse: {exc}")

ai_client: OpenAI | None = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    try:
        ai_client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/",
        )
        print("[OK] Azure OpenAI configurado.")
    except Exception as exc:
        print(f"[WARN] Azure OpenAI no pudo inicializarse: {exc}")



def _err_log(msg, exc):
    """Guarda el detalle técnico solo en los logs del servidor; al usuario le llega un mensaje limpio."""
    try:
        print(f"[ERROR] {request.path}: {msg}: {exc}")
    except Exception:
        print(f"[ERROR] {msg}: {exc}")
    return msg + ". Inténtalo de nuevo."


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _is_uuid(v):
    return bool(v and _UUID_RE.match(str(v)))

def json_error(message, status=400, **extra):
    payload = {"ok": False, "error": message}
    if status == 429 and getattr(g, "limit_info", None):
        payload["limite"] = g.limit_info        # el frontend lo usa para mostrar el aviso de plan
    payload.update(extra)
    return jsonify(payload), status


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


def has_active_access(profile_data):
    """True si el usuario pagó, o si sigue dentro de su periodo de prueba de 7 días."""
    if profile_data.get("is_subscribed"):
        return True
    trial_ends_at = profile_data.get("trial_ends_at")
    if not trial_ends_at:
        return False
    try:
        deadline = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) < deadline


# ---------------------------------------------------------------------------
# Límites de uso por usuario (protegen tu crédito de Azure sin costo extra).
# Se guardan en memoria del servidor: gratis y suficientes para un solo servidor.
# Ajusta los números aquí si algún límite se queda corto para tus alumnos.
# ---------------------------------------------------------------------------
RATE_RULES = {
    "/api/tutor": (60, 3600),
    "/api/sintetizar-audio": (120, 3600),
    "/api/transcribir-audio": (60, 3600),
    "/api/resumen-llamada": (10, 3600),
    "/api/llamada/turno": (70, 3600),
    "/analizar-escritura": (20, 3600),
    "/evaluar-lectura": (30, 3600),
    "/evaluar-dictado": (40, 3600),
    "/analizar-audio-real": (150, 3600),
    "/api/assess-reading": (40, 3600),
    "/api/assess-unscripted": (40, 3600),
    "/nueva-frase": (60, 3600),
    "/nuevo-tema-libre": (60, 3600),
    "/nuevo-trabalenguas": (60, 3600),
    "/nuevo-texto-lectura": (30, 3600),
    "/nuevo-dictado": (30, 3600),
    "/api/writing/challenge": (30, 3600),
    "/api/vocabulario/diario": (20, 3600),
    "/api/traducir": (150, 3600),
    "/api/rutas/crear": (8, 3600),
    "/api/escenario/nuevo": (10, 3600),
    "/api/escenario/turno": (90, 3600),
    "/api/escenario/feedback": (12, 3600),
    "/api/diccionario": (120, 3600),
    "/api/clips/tema": (20, 3600), "/api/presentacion/guion": (10, 3600),
    "/api/shadowing/tema": (30, 3600),
    "/api/reunion/analizar": (6, 3600),
}
GENERAL_PER_MINUTE = 120                                      # cualquier endpoint, por usuario
_rate_lock = threading.Lock()
_rate_hits = {}
_rate_calls = 0


def _rate_hit(key, limit, window):
    """Registra una llamada. Devuelve (permitida, segundos_para_reintentar)."""
    global _rate_calls
    now = time.time()
    with _rate_lock:
        _rate_calls += 1
        if _rate_calls % 2000 == 0:  # limpieza ocasional para no acumular memoria
            for k in [k for k, q in _rate_hits.items() if not q or now - q[-1] > 86400]:
                _rate_hits.pop(k, None)
        q = _rate_hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False, int(window - (now - q[0])) + 1
        q.append(now)
        return True, 0


# ---------------------------------------------------------------------------
# PLANES Y CRÉDITOS (como Claude: una cuota que se renueva cada 5 horas + un tope diario).
# Cada acción con IA gasta créditos. Cuando se acaban, el alumno espera a que se renueve
# o sube de plan. Todo se puede ajustar aquí o con variables de entorno en Render.
#   ventana = créditos cada 5 horas   |   dia = créditos cada 24 horas
# ---------------------------------------------------------------------------
WINDOW_SECONDS = 5 * 3600
PLANS = {
    "gratis": {"nombre": "Prueba gratis", "precio": 0,
               "ventana": int(env("PLAN_GRATIS_VENTANA", "10") or 10), "dia": int(env("PLAN_GRATIS_DIA", "25") or 25)},
    "basico": {"nombre": "Básico", "precio": int(env("PRICE_BASICO_MXN", "79") or 79),
               "ventana": int(env("PLAN_BASICO_VENTANA", "40") or 40), "dia": int(env("PLAN_BASICO_DIA", "120") or 120)},
    "pro":    {"nombre": "Pro", "precio": int(env("PRICE_PRO_MXN", "149") or 149),
               "ventana": int(env("PLAN_PRO_VENTANA", "100") or 100), "dia": int(env("PLAN_PRO_DIA", "300") or 300)},
    "max":    {"nombre": "Max", "precio": int(env("PRICE_MAX_MXN", "299") or 299),
               "ventana": int(env("PLAN_MAX_VENTANA", "250") or 250), "dia": int(env("PLAN_MAX_DIA", "700") or 700)},
}
# Cuánto cuesta cada acción (lo caro de Azure cuesta más créditos; 1 crédito ≈ 1 mensaje al tutor).
CREDIT_COST = {
    "/api/tutor": 1, "/api/resumen-llamada": 3, "/api/transcribir-audio": 1,
    "/api/llamada/turno": 2.1,   # un turno de llamada = transcribir (1) + tutor (1) + voz (0.1), igual que antes pero en una sola petición
    "/api/sintetizar-audio": 0.1,
    "/analizar-escritura": 2, "/evaluar-lectura": 2, "/evaluar-dictado": 1.5,
    "/analizar-audio-real": 2, "/api/assess-reading": 2, "/api/assess-unscripted": 2,
    "/nueva-frase": 0.5, "/nuevo-tema-libre": 0.5, "/nuevo-trabalenguas": 0.5,
    "/nuevo-texto-lectura": 1, "/nuevo-dictado": 1, "/api/writing/challenge": 1,
    "/api/vocabulario/diario": 1,
    # Funciones nuevas (la voz del escenario y del traductor usa el navegador: costo de audio 0)
    "/api/traducir": 0.3, "/api/rutas/crear": 4, "/api/escenario/nuevo": 1,
    "/api/escenario/turno": 1, "/api/escenario/feedback": 3,
    "/api/diccionario": 0.3, "/api/clips/tema": 1, "/api/presentacion/guion": 2, "/api/shadowing/tema": 0.5, "/api/reunion/analizar": 6,
}
# Interruptor de emergencia: si entre todos los alumnos se gastan estos créditos en un día,
# la prueba gratis se pausa (los que pagan siguen). Protege tu saldo de Azure.
GLOBAL_DAILY_CREDITS = float(env("GLOBAL_DAILY_CREDITS", "6000") or 6000)
# Tope diario sólo para pruebas gratis (en conjunto), por si llega mucha gente nueva de golpe.
FREE_GLOBAL_DAILY_CREDITS = float(env("FREE_GLOBAL_DAILY_CREDITS", "2500") or 2500)

_use = {}                      # uid -> deque[(timestamp, costo)]
_use_loaded = set()
_global_use = deque()          # (timestamp, costo, es_gratis)
_use_table_ok = True
_profile_cache = {}            # uid -> (expira, datos)
_plan_col_ok = True


import copy
CONFIG_TABLE = "config_app"
_DEFAULT_CFG = None
_cfg_loaded = False
_cfg_saved_ok = None


def _current_config():
    return {
        "planes": {k: {"precio": v["precio"], "ventana": v["ventana"], "dia": v["dia"]} for k, v in PLANS.items()},
        "costos": dict(CREDIT_COST),
        "global_dia": GLOBAL_DAILY_CREDITS,
        "gratis_global_dia": FREE_GLOBAL_DAILY_CREDITS,
    }


def _apply_config(cfg):
    """Aplica una configuración (ya validada) a los límites en vivo."""
    global GLOBAL_DAILY_CREDITS, FREE_GLOBAL_DAILY_CREDITS
    for k, v in (cfg.get("planes") or {}).items():
        if k in PLANS and isinstance(v, dict):
            for f in ("precio", "ventana", "dia"):
                if f in v:
                    PLANS[k][f] = int(v[f])
    for path, c in (cfg.get("costos") or {}).items():
        if path in CREDIT_COST:
            CREDIT_COST[path] = float(c)
    if "global_dia" in cfg:
        GLOBAL_DAILY_CREDITS = float(cfg["global_dia"])
    if "gratis_global_dia" in cfg:
        FREE_GLOBAL_DAILY_CREDITS = float(cfg["gratis_global_dia"])


def _validate_config(raw):
    """Devuelve (config_limpia, error)."""
    if not isinstance(raw, dict):
        return None, "Configuración inválida."
    out = {"planes": {}, "costos": {}}
    for k, v in (raw.get("planes") or {}).items():
        if k not in PLANS or not isinstance(v, dict):
            continue
        clean = {}
        for f, hi in (("precio", 100000), ("ventana", 100000), ("dia", 1000000)):
            if f in v:
                try:
                    n = int(float(v[f]))
                except (TypeError, ValueError):
                    return None, f"Número inválido en {PLANS[k]['nombre']} · {f}."
                if n < 0 or n > hi:
                    return None, f"{PLANS[k]['nombre']} · {f} debe estar entre 0 y {hi}."
                clean[f] = n
        if clean.get("dia") is not None and clean.get("ventana") is not None and clean["ventana"] > clean["dia"]:
            return None, f"{PLANS[k]['nombre']}: los mensajes por 5 h no pueden superar los del día."
        out["planes"][k] = clean
    for p, c in (raw.get("costos") or {}).items():
        if p not in CREDIT_COST:
            continue
        try:
            n = float(c)
        except (TypeError, ValueError):
            return None, f"Costo inválido en {p}."
        if n < 0 or n > 50:
            return None, f"El costo de {p} debe estar entre 0 y 50."
        out["costos"][p] = round(n, 2)
    for key in ("global_dia", "gratis_global_dia"):
        if key in raw:
            try:
                n = float(raw[key])
            except (TypeError, ValueError):
                return None, "Tope global inválido."
            if n < 0 or n > 10000000:
                return None, "Tope global fuera de rango."
            out[key] = n
    return out, None


def _load_config():
    """Una sola vez por arranque: lee lo que guardaste desde el panel de admin (si existe la tabla)."""
    global _cfg_loaded, _DEFAULT_CFG, _cfg_saved_ok
    if _cfg_loaded:
        return
    _cfg_loaded = True
    _DEFAULT_CFG = copy.deepcopy(_current_config())
    client = supabase_admin or supabase
    if not client:
        return
    try:
        rows = client.table(CONFIG_TABLE).select("value").eq("key", "planes").limit(1).execute().data or []
        if rows and isinstance(rows[0].get("value"), dict):
            cfg, err = _validate_config(rows[0]["value"])
            if not err:
                _apply_config(cfg)
                print("[PLAN] Configuración de planes cargada desde la base de datos.")
        _cfg_saved_ok = True
    except Exception as exc:
        _cfg_saved_ok = False
        print(f"[PLAN] Sin tabla {CONFIG_TABLE}: se usan los valores por defecto ({str(exc)[:100]}).")


def _save_config():
    """Guarda la configuración actual. Devuelve un aviso si no se pudo guardar de forma permanente."""
    global _cfg_saved_ok
    client = supabase_admin or supabase
    try:
        client.table(CONFIG_TABLE).upsert({"key": "planes", "value": _current_config(),
                                           "updated_at": datetime.now(timezone.utc).isoformat()}).execute()
        _cfg_saved_ok = True
        return None
    except Exception as exc:
        _cfg_saved_ok = False
        return (f"Se aplicó ahora mismo, pero NO quedó guardado: si Render reinicia, vuelve a los valores de antes. "
                f"Crea la tabla {CONFIG_TABLE} con planes_y_uso.sql ({str(exc)[:80]}).")


def _fmt_wait(sec):
    sec = max(60, int(sec))
    h, m = sec // 3600, (sec % 3600) // 60
    if h and m:
        return f"{h} h {m} min"
    return f"{h} h" if h else f"{m} min"


def _profile_access(uid, fresh=False):
    """Perfil mínimo del usuario (acceso + plan). Se guarda 30 s para no consultar la base en cada petición."""
    global _plan_col_ok
    now = time.time()
    hit = _profile_cache.get(uid)
    if hit and hit[0] > now and not fresh:
        return hit[1]
    client = supabase_admin or supabase
    data = {}
    for cols in (("is_subscribed,trial_ends_at,plan" if _plan_col_ok else None), "is_subscribed,trial_ends_at"):
        if not cols:
            continue
        try:
            res = client.table("profiles").select(cols).eq("id", uid).limit(1).execute()
            rows = getattr(res, "data", None) or []
            data = rows[0] if rows else {}
            break
        except Exception as exc:
            if "plan" in cols and "plan" in str(exc).lower():
                _plan_col_ok = False
                print("[PLAN] La columna profiles.plan no existe todavía; todos los de pago se tratan como Básico.")
                continue
            raise
    if len(_profile_cache) > 5000:
        _profile_cache.clear()
    _profile_cache[uid] = (now + 30, data)
    return data


def plan_key(profile):
    if profile and profile.get("is_subscribed"):
        p = str(profile.get("plan") or "basico").strip().lower()
        return p if p in PLANS else "basico"
    return "gratis"


def _load_usage(uid):
    """Tras un reinicio del servidor recupera el consumo de las últimas 24 h (si existe la tabla uso_ia)."""
    global _use_table_ok
    if uid in _use_loaded:
        return
    _use_loaded.add(uid)
    q = _use.setdefault(uid, deque())
    if not _use_table_ok:
        return
    client = supabase_admin or supabase
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = (client.table("uso_ia").select("costo,created_at").eq("user_id", uid)
                .gte("created_at", since).order("created_at").limit(2000).execute()).data or []
        loaded = []
        for r in rows:
            ts = _parse_ts(r.get("created_at"))
            if ts:
                loaded.append((ts.timestamp(), float(r.get("costo") or 0)))
        merged = sorted(loaded + list(q))
        q.clear()
        q.extend(merged)
    except Exception as exc:
        _use_table_ok = False
        print(f"[USO] Tabla uso_ia no disponible (los límites siguen funcionando en memoria): {str(exc)[:120]}")


_uso_ruta_ok = True


def _persist_usage(uid, cost):
    if not _use_table_ok:
        return
    try:
        ruta = request.path[:60]
    except Exception:
        ruta = None
    def _w():
        global _use_table_ok, _uso_ruta_ok
        try:
            c = supabase_admin or supabase
            if _uso_ruta_ok and ruta:
                try:
                    c.table("uso_ia").insert({"user_id": uid, "costo": cost, "ruta": ruta}).execute()
                    return
                except Exception as exc2:
                    if "ruta" not in str(exc2).lower():
                        raise
                    _uso_ruta_ok = False
            c.table("uso_ia").insert({"user_id": uid, "costo": cost}).execute()
        except Exception as exc:
            _use_table_ok = False
            print(f"[USO] No se pudo guardar el consumo: {str(exc)[:120]}")
    threading.Thread(target=_w, daemon=True).start()


def usage_snapshot(uid, plan):
    now = time.time()
    _load_usage(uid)
    q = _use.setdefault(uid, deque())
    while q and now - q[0][0] > 86400:
        q.popleft()
    p = PLANS[plan]
    used_w = sum(c for t, c in q if now - t < WINDOW_SECONDS)
    used_d = sum(c for t, c in q)
    def reset_after(limit, window, used):
        oldest = [t for t, c in q if now - t < window]
        return int(min(oldest) + window - now) if oldest else 0
    return {
        "plan": plan, "plan_nombre": p["nombre"],
        "ventana": {"usado": round(used_w, 2), "limite": p["ventana"], "reinicia_seg": reset_after(p["ventana"], WINDOW_SECONDS, used_w)},
        "dia": {"usado": round(used_d, 2), "limite": p["dia"], "reinicia_seg": reset_after(p["dia"], 86400, used_d)},
    }


def _wait_to_fit(q, now, window, limit, cost):
    """Segundos hasta que haya espacio para `cost` créditos más dentro de `window`."""
    used = sum(c for t, c in q if now - t < window)
    need = used + cost - limit
    freed = 0.0
    for t, c in q:
        if now - t >= window:
            continue
        freed += c
        if freed >= need:
            return int(t + window - now) + 1
    return window


def check_rate_limit(user):
    """Devuelve None si todo bien, o un mensaje de error (429)."""
    g.limit_info = None
    _load_config()
    if is_admin_user(user):
        return None
    uid = getattr(user, "id", "anon")
    ok, wait = _rate_hit((uid, "minuto"), GENERAL_PER_MINUTE, 60)
    if not ok:
        return f"Vas muy rápido. Espera {wait} segundos e inténtalo de nuevo."
    rule = RATE_RULES.get(request.path)
    if not rule:
        return None
    ok, wait = _rate_hit((uid, request.path), rule[0], rule[1])
    if not ok:
        return f"Alcanzaste el límite de esta actividad por ahora. Vuelve a intentarlo en {max(1, wait // 60)} min."
    try:
        fast_clip = request.path == "/analizar-audio-real" and request.form.get("fast") in ("1", "true")
    except Exception:
        fast_clip = False
    if fast_clip:
        return None  # los audios rápidos de las lecciones no usan IA, así que no cuentan
    cost = CREDIT_COST.get(request.path, 1)
    try:
        plan = plan_key(_profile_access(uid))
    except Exception as exc:
        print(f"[PLAN] {exc}")
        plan = "gratis"
    p = PLANS[plan]
    now = time.time()
    _load_usage(uid)
    q = _use.setdefault(uid, deque())
    while q and now - q[0][0] > 86400:
        q.popleft()
    while _global_use and now - _global_use[0][0] > 86400:
        _global_use.popleft()

    # 1) Interruptores globales (protegen tu dinero de Azure)
    g_total = sum(c for _, c, _f in _global_use)
    g_free = sum(c for _, c, f in _global_use if f)
    if plan == "gratis" and (g_total >= GLOBAL_DAILY_CREDITS or g_free >= FREE_GLOBAL_DAILY_CREDITS):
        g.limit_info = {"tipo": "alta_demanda", "plan": plan, "plan_nombre": p["nombre"], "reinicia_seg": 3600}
        return ("Hay muchísima gente practicando ahora y las pruebas gratis están en pausa un rato. "
                "Vuelve en un rato o activa un plan para seguir sin esperar.")
    if g_total >= GLOBAL_DAILY_CREDITS * 1.5:
        g.limit_info = {"tipo": "alta_demanda", "plan": plan, "plan_nombre": p["nombre"], "reinicia_seg": 3600}
        return "El servicio está con mucha demanda. Inténtalo de nuevo en un rato."

    # 2) Cuota por plan: ventana de 5 horas y tope del día
    used_w = sum(c for t, c in q if now - t < WINDOW_SECONDS)
    used_d = sum(c for t, c in q)
    if used_d + cost > p["dia"]:
        wait = _wait_to_fit(q, now, 86400, p["dia"], cost)
        g.limit_info = {"tipo": "dia", "plan": plan, "plan_nombre": p["nombre"], "reinicia_seg": wait, **_limit_extra(plan)}
        return f"Llegaste a tu límite diario del plan {p['nombre']}. Se renueva en {_fmt_wait(wait)}."
    if used_w + cost > p["ventana"]:
        wait = _wait_to_fit(q, now, WINDOW_SECONDS, p["ventana"], cost)
        g.limit_info = {"tipo": "ventana", "plan": plan, "plan_nombre": p["nombre"], "reinicia_seg": wait, **_limit_extra(plan)}
        return f"Usaste todos tus mensajes de estas 5 horas del plan {p['nombre']}. Se renuevan en {_fmt_wait(wait)}."

    q.append((now, cost))
    _global_use.append((now, cost, plan == "gratis"))
    _persist_usage(uid, cost)
    return None


def _limit_extra(plan):
    order = ["gratis", "basico", "pro", "max"]
    nxt = order[order.index(plan) + 1] if plan != "max" else None
    return {"siguiente_plan": nxt, "siguiente_nombre": PLANS[nxt]["nombre"] if nxt else None}


def _client_ip():
    h = request.headers
    ip = h.get("CF-Connecting-IP") or h.get("True-Client-IP") or (h.get("X-Forwarded-For") or "").split(",")[0].strip() or request.remote_addr
    return (ip or "?")[:64]


def _rate_peek(key, limit, window):
    """True si ya se alcanzó el límite (sin registrar una llamada nueva)."""
    now = time.time()
    with _rate_lock:
        q = _rate_hits.get(key)
        if not q:
            return False
        while q and now - q[0] > window:
            q.popleft()
        return len(q) >= limit


_auth_cache = {}            # sha256(token) -> (expira, user)
_auth_lock = threading.Lock()
AUTH_CACHE_SECONDS = 45     # si cierras sesión o te bloquean, el cambio tarda como máximo esto en notarse


def _auth_key(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _auth_cache_get(token):
    now = time.time()
    with _auth_lock:
        hit = _auth_cache.get(_auth_key(token))
        if hit and hit[0] > now:
            return hit[1]
    return None


def _auth_cache_put(token, user):
    now = time.time()
    with _auth_lock:
        if len(_auth_cache) > 2000:
            for k in [k for k, v in _auth_cache.items() if v[0] <= now]:
                _auth_cache.pop(k, None)
            if len(_auth_cache) > 2000:
                _auth_cache.clear()
        _auth_cache[_auth_key(token)] = (now + AUTH_CACHE_SECONDS, user)


def authenticated_user(require_subscription=True):
    if not supabase:
        return None, ("Supabase no está configurado.", 500)

    # Protección contra fuerza bruta / abuso por IP (antes de gastar una consulta a Supabase)
    ip = _client_ip()
    if _rate_peek(("authfail", ip), 25, 300):
        return None, ("Demasiados intentos con sesión inválida. Espera unos minutos.", 429)
    ok_ip, _w = _rate_hit(("ip", ip), 900, 60)
    if not ok_ip:
        return None, ("Demasiadas solicitudes desde tu red. Espera un momento.", 429)

    token = get_bearer_token()
    if not token:
        return None, ("Sesión requerida.", 401)
    if len(token) > 4096:
        _rate_hit(("authfail", ip), 25, 300)
        return None, ("Sesión inválida.", 401)

    try:
        user = _auth_cache_get(token)
        if user is None:
            result = supabase.auth.get_user(token)
            user = result.user
            if user:
                _auth_cache_put(token, user)
    except Exception as exc:
        print(f"[AUTH] {exc}")
        _rate_hit(("authfail", ip), 25, 300)
        return None, ("Sesión inválida o expirada.", 401)

    if not user:
        _rate_hit(("authfail", ip), 25, 300)
        return None, ("Sesión inválida.", 401)

    if require_subscription and not is_admin_user(user):
        try:
            data = _profile_access(user.id)
            if not has_active_access(data):
                return None, ("Tu acceso todavía no está activo.", 403)
        except Exception as exc:
            print(f"[PROFILE] {exc}")
            return None, ("No se pudo comprobar tu acceso.", 500)

    limited = check_rate_limit(user)
    if limited:
        return None, (limited, 429)

    return user, None


def ai_json(system_prompt, user_prompt, temperature=0.7):
    if not ai_client:
        raise RuntimeError("Azure OpenAI no está configurado en el servidor.")

    response = ai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
        timeout=100,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def save_history(table, user_id, payload):
    client = supabase_admin or supabase
    if not client:
        return
    try:
        client.table(table).insert({"user_id": user_id, **payload}).execute()
    except Exception as exc:
        print(f"[HISTORY:{table}] {exc}")


def award_xp(user_id, amount):
    """Suma XP y gemas, y actualiza la racha de días consecutivos practicando."""
    client = supabase_admin or supabase
    if not client:
        return
    try:
        profile = (
            client.table("profiles")
            .select("xp,streak_days,last_activity_date,gems,streak_freezes")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        data = profile.data or {}
        today = datetime.now(timezone.utc).date()
        last = data.get("last_activity_date")
        streak = data.get("streak_days") or 0
        freezes = data.get("streak_freezes") or 0
        if last:
            last_date = datetime.fromisoformat(last).date()
            if last_date == today:
                pass  # ya contó hoy
            elif last_date == today - timedelta(days=1):
                streak += 1
            elif last_date == today - timedelta(days=2) and freezes > 0:
                # Se saltó exactamente un día, pero tiene una racha congelada guardada.
                freezes -= 1
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        new_xp = (data.get("xp") or 0) + amount
        new_gems = (data.get("gems") or 0) + max(1, amount // 10)
        client.table("profiles").update({
            "xp": new_xp,
            "gems": new_gems,
            "streak_days": streak,
            "streak_freezes": freezes,
            "last_activity_date": today.isoformat(),
        }).eq("id", user_id).execute()
    except Exception as exc:
        print(f"[XP] {exc}")


def speech_config():
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("Azure Speech no está configurado.")
    config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    config.speech_recognition_language = "en-US"
    return config


def convert_audio_to_wav(upload):
    suffix = os.path.splitext(upload.filename or "audio.webm")[1] or ".webm"
    source_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as source:
            upload.save(source.name)
            source_path = source.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav:
            wav_path = wav.name

        audio = AudioSegment.from_file(source_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception:
        if source_path and os.path.exists(source_path):
            os.remove(source_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        raise


def assess_pronunciation(wav_path, reference_text=None):
    config = speech_config()
    if reference_text:
        pronunciation = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation.enable_prosody_assessment()
    else:
        pronunciation = speechsdk.PronunciationAssessmentConfig(
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )

    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
    pronunciation.apply_to(recognizer)
    result = recognizer.recognize_once()

    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        detail = getattr(result, "cancellation_details", None)
        reason = getattr(detail, "reason", "No se reconoció el audio.") if detail else "No se reconoció el audio."
        raise RuntimeError(str(reason))

    raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult, "{}")
    raw = json.loads(raw_json)
    nbest = (raw.get("NBest") or [{}])[0]
    assessment_raw = nbest.get("PronunciationAssessment") or {}

    words = []
    for word in nbest.get("Words") or []:
        wa = word.get("PronunciationAssessment") or {}
        phonemes = []
        for phoneme in word.get("Phonemes") or []:
            pa = phoneme.get("PronunciationAssessment") or {}
            phonemes.append({
                "phoneme": phoneme.get("Phoneme", ""),
                "accuracy": round(float(pa.get("AccuracyScore", 0) or 0), 1),
            })
        words.append({
            "word": word.get("Word", ""),
            "accuracy": round(float(wa.get("AccuracyScore", 0) or 0), 1),
            "error_type": wa.get("ErrorType", "None"),
            "offset": word.get("Offset", 0),
            "duration": word.get("Duration", 0),
            "phonemes": phonemes,
        })

    speaking_rate_wpm = 0
    if words:
        first_offset = words[0].get("offset", 0) or 0
        last_word = words[-1]
        last_end = (last_word.get("offset", 0) or 0) + (last_word.get("duration", 0) or 0)
        speaking_seconds = max(0.1, (last_end - first_offset) / 10_000_000)
        speaking_rate_wpm = round(len(words) / speaking_seconds * 60)

    return {
        "transcript": nbest.get("Display", ""),
        "pronunciation_score": round(float(assessment_raw.get("PronScore", 0) or 0), 1),
        "accuracy_score": round(float(assessment_raw.get("AccuracyScore", 0) or 0), 1),
        "fluency_score": round(float(assessment_raw.get("FluencyScore", 0) or 0), 1),
        "completeness_score": round(float(assessment_raw.get("CompletenessScore", 0) or 0), 1),
        "prosody_score": round(float(assessment_raw.get("ProsodyScore", 0) or 0), 1),
        "speaking_rate_wpm": speaking_rate_wpm,
        "words": words,
    }


ERROR_TYPE_TO_KEY = {
    "Omission": "omisiones",
    "Insertion": "inserciones",
    "Mispronunciation": "pronunciaciones_incoherentes",
    "UnexpectedBreak": "interrupcion_inesperada",
    "MissingBreak": "falta_un_descanso",
    "Monotone": "monotona",
}


def build_pron_payload(result):
    """Convierte el resultado (claves en inglés) al formato en español que usa el frontend."""
    inspeccion = {key: 0 for key in ERROR_TYPE_TO_KEY.values()}
    palabras = []
    for word in result["words"]:
        error_key = ERROR_TYPE_TO_KEY.get(word.get("error_type"))
        if error_key:
            inspeccion[error_key] += 1
        palabras.append({
            "palabra": word.get("word", ""),
            "precision": word.get("accuracy", 0),
            "fonemas": [
                {"fonema": p.get("phoneme", ""), "precision": p.get("accuracy", 0)}
                for p in word.get("phonemes", [])
            ],
        })

    return {
        "transcript": result.get("transcript", ""),
        "puntuacion_global": result.get("pronunciation_score", 0),
        "precision": result.get("accuracy_score", 0),
        "fluidez": result.get("fluency_score", 0),
        "completitud": result.get("completeness_score", 0),
        "prosodia": result.get("prosody_score", 0),
        "velocidad_wpm": result.get("speaking_rate_wpm", 0),
        "palabras": palabras,
        "inspeccion": inspeccion,
    }


PASS_THRESHOLD = 60  # puntuación mínima para aprobar una lección

# ---------------------------------------------------------------------------
#  RUTA DE APRENDIZAJE v2 — currículo fijo (sin costo de IA) + lecciones de varios pasos
# ---------------------------------------------------------------------------
CURRICULUM_TEXT = r'''@unit first_steps|1|A1|🚀|First Steps|Your first words and phrases to survive any introduction.|general
# hello_bye|Hello & goodbye
n Usa "Hi" con amigos y "Hello" en situaciones más formales.
w hello|hola|👋
w goodbye|adiós|👋
w good morning|buenos días|🌅
w good night|buenas noches|🌙
w see you later|hasta luego|🙂
w friend|amigo|🧑‍🤝‍🧑
p Hello, nice to meet you.|Hola, mucho gusto.
p Good morning, how are you?|Buenos días, ¿cómo estás?
p See you tomorrow.|Nos vemos mañana.
d Good morning!|Good morning! How are you?|Goodbye, my friend.|It is blue.
# i_am|I am… / You are…
n En inglés el sujeto es obligatorio: "I am", no solo "am".
w I am|yo soy / estoy
w you are|tú eres / estás
w he is|él es / está
w she is|ella es / está
w we are|nosotros somos
w they are|ellos son
p I am from Mexico.|Soy de México.
p She is my sister.|Ella es mi hermana.
p We are students.|Somos estudiantes.
d Where are you from?|I am from Spain.|She is my sister.|We are tired.
# please_thanks|Please & thank you
n "Excuse me" para llamar la atención; "Sorry" para disculparte.
w please|por favor
w thank you|gracias
w you are welcome|de nada
w sorry|perdón
w excuse me|disculpe
w help|ayuda|🆘
p Thank you very much.|Muchas gracias.
p Excuse me, can you help me?|Disculpe, ¿me puede ayudar?
p I am sorry, I do not understand.|Lo siento, no entiendo.
d Thank you very much!|You are welcome.|Good night.|I am a student.
# yes_no|Yes, no, and questions
w yes|sí
w no|no
w maybe|quizás
w what|qué
w where|dónde
w how much|cuánto
p Do you speak English?|¿Hablas inglés?
p What is your name?|¿Cómo te llamas?
p Can you repeat that, please?|¿Puedes repetirlo, por favor?
d Do you speak English?|A little, but I am learning.|Yes, it is red.|My name is on the table.
# spell_it|Spell your name
n Practica decir tu nombre letra por letra: es lo que te piden en hoteles y bancos.
w name|nombre
w last name|apellido
w letter|letra
w spell|deletrear
w phone number|número de teléfono|📱
w email|correo electrónico|📧
p How do you spell your name?|¿Cómo se deletrea tu nombre?
p My name is Ana Lopez.|Me llamo Ana López.
p Could you spell that, please?|¿Podría deletrearlo, por favor?
d How do you spell your last name?|L-O-P-E-Z.|It is Monday.|I am fine.
@unit everyday_english|2|A1|🏠|Everyday English|Greetings, routines, and small talk.|general
# greetings|Greetings & introductions
n "How are you?" es un saludo; la respuesta corta es "Fine, thanks. And you?".
w nice to meet you|mucho gusto
w how are you|cómo estás
w I am fine|estoy bien
w my name is|me llamo
w where are you from|de dónde eres
w I live in|vivo en
p Hi, my name is Carlos. Nice to meet you.|Hola, me llamo Carlos. Mucho gusto.
p I am fine, thanks. And you?|Estoy bien, gracias. ¿Y tú?
p I live in Monterrey.|Vivo en Monterrey.
d How are you today?|I am fine, thanks. And you?|I live in a house.|My name is Tuesday.
# routines|Daily routines
n La rutina usa presente simple: "I wake up", "she works". Con he/she/it se añade -s.
w wake up|despertarse|⏰
w take a shower|bañarse|🚿
w have breakfast|desayunar|🥣
w go to work|ir al trabajo|🏢
w come home|llegar a casa|🏡
w go to bed|irse a dormir|🛏️
p I wake up at seven every day.|Me despierto a las siete todos los días.
p She goes to work by bus.|Ella va al trabajo en autobús.
p We have dinner at eight.|Cenamos a las ocho.
d What time do you wake up?|I wake up at six.|I am from Chile.|She is my friend.
# family|Family & friends
w mother|madre|👩
w father|padre|👨
w brother|hermano
w sister|hermana
w grandmother|abuela|👵
w cousin|primo / prima
p I have two brothers and one sister.|Tengo dos hermanos y una hermana.
p My grandmother lives with us.|Mi abuela vive con nosotros.
p He is my best friend.|Él es mi mejor amigo.
d Do you have brothers or sisters?|Yes, I have one sister.|I live in a big house.|It is nine o'clock.
# smalltalk|Small talk
n "How is it going?" y "What's up?" son saludos muy comunes y informales.
w weather|clima|⛅
w weekend|fin de semana
w busy|ocupado
w tired|cansado|😴
w by the way|por cierto
w really|de verdad
p How was your weekend?|¿Cómo estuvo tu fin de semana?
p It is a beautiful day, isn't it?|Es un día hermoso, ¿no?
p I am a little tired today.|Estoy un poco cansado hoy.
d How was your weekend?|It was great, thanks for asking.|My name is Peter.|I have a red car.
# numbers_time|Numbers & time
n Para la hora: "It is half past three" = 3:30.
w twenty|veinte
w fifty|cincuenta
w one hundred|cien
w o'clock|en punto
w half past|y media
w quarter to|menos cuarto
p What time is it?|¿Qué hora es?
p It is half past three.|Son las tres y media.
p The meeting is at ten o'clock.|La reunión es a las diez en punto.
d What time is it?|It is a quarter to six.|It is my sister.|I am from Peru.
@unit home_and_city|3|A1|🏙️|Home & City|Talk about your home, your neighborhood, and getting around.|general
# rooms_home|Rooms & furniture
w kitchen|cocina|🍳
w bedroom|recámara|🛏️
w bathroom|baño|🚽
w living room|sala|🛋️
w window|ventana|🪟
w door|puerta|🚪
p My bedroom is upstairs.|Mi recámara está arriba.
p There is a table in the kitchen.|Hay una mesa en la cocina.
p The bathroom is on the left.|El baño está a la izquierda.
d Where is the bathroom?|It is on the left.|I wake up at six.|He is my uncle.
# things_around|Things around you
n "There is" para uno, "there are" para varios.
w table|mesa
w chair|silla|🪑
w phone|teléfono|📱
w key|llave|🔑
w bag|bolsa|👜
w book|libro|📕
p There are three chairs in the room.|Hay tres sillas en el cuarto.
p Where are my keys?|¿Dónde están mis llaves?
p My phone is in my bag.|Mi teléfono está en mi bolsa.
d Where are my keys?|They are on the table.|I am very tired.|It is half past two.
# places_city|Places in the city
w bank|banco|🏦
w supermarket|supermercado|🛒
w park|parque|🌳
w hospital|hospital|🏥
w pharmacy|farmacia|💊
w school|escuela|🏫
p The bank is next to the supermarket.|El banco está junto al supermercado.
p Is there a pharmacy near here?|¿Hay una farmacia cerca de aquí?
p I go to the park on Sundays.|Voy al parque los domingos.
d Is there a pharmacy near here?|Yes, it is on the corner.|I like pizza.|She is a doctor.
# transport|Getting around
w bus|autobús|🚌
w train|tren|🚆
w taxi|taxi|🚕
w subway|metro|🚇
w ticket|boleto|🎫
w stop|parada
p How do I get to the train station?|¿Cómo llego a la estación de tren?
p The bus stops here every ten minutes.|El autobús para aquí cada diez minutos.
p One ticket, please.|Un boleto, por favor.
d How much is a ticket?|It is two dollars.|It is sunny today.|My name is Luis.
# weather|Weather & seasons
n "It is hot" (hace calor): en inglés se usa el verbo "to be", no "to do".
w sunny|soleado|☀️
w rainy|lluvioso|🌧️
w cold|frío|🥶
w hot|caliente / calor|🥵
w windy|con viento|💨
w umbrella|paraguas|☂️
p It is going to rain tomorrow.|Va a llover mañana.
p It is very hot in summer.|Hace mucho calor en verano.
p Take an umbrella, just in case.|Lleva un paraguas, por si acaso.
d What is the weather like today?|It is cold and windy.|I live near the park.|He is my friend.
@unit at_the_restaurant|4|A2|🍽️|At the Restaurant|Order food, talk about flavors, and handle the bill.|travel
# ordering|Ordering food
n "I'd like…" es más cortés que "I want…".
w menu|menú|📋
w waiter|mesero|🧑‍🍳
w appetizer|entrada
w main course|plato fuerte
w dessert|postre|🍰
w drink|bebida|🥤
p I would like the chicken, please.|Quisiera el pollo, por favor.
p Can I see the menu?|¿Puedo ver el menú?
p Could we have some water?|¿Nos podría traer agua?
d Are you ready to order?|Yes, I would like the chicken.|It is on the left.|I live near here.
# menu|Understanding a menu
w grilled|a la parrilla
w fried|frito
w spicy|picante|🌶️
w vegetarian|vegetariano|🥗
w sauce|salsa
w side dish|guarnición
p Does this dish have nuts?|¿Este platillo lleva nueces?
p I am allergic to shellfish.|Soy alérgico a los mariscos.
p What do you recommend?|¿Qué me recomienda?
d What do you recommend?|The grilled fish is excellent.|I am from Peru.|It is five o'clock.
# preferences|Likes & dislikes
n "I'd rather…" = prefiero. "I can't stand…" = no soporto.
w I like|me gusta
w I love|me encanta
w I don't like|no me gusta
w I prefer|prefiero
w delicious|delicioso
w too salty|demasiado salado
p I love Italian food.|Me encanta la comida italiana.
p I do not like spicy food.|No me gusta la comida picante.
p I prefer tea to coffee.|Prefiero el té al café.
d Do you like spicy food?|Not really, I prefer mild food.|Yes, it is on the table.|He is my brother.
# complaints|Complaints & requests
w cold (food)|frío|🥶
w overcooked|pasado de cocción
w mistake|error
w manager|gerente
w refund|reembolso
w replace|reemplazar
p Excuse me, this is not what I ordered.|Disculpe, esto no es lo que pedí.
p The soup is cold. Could you heat it up?|La sopa está fría. ¿Podría calentarla?
p Could I speak to the manager?|¿Podría hablar con el gerente?
d Is everything okay with your meal?|Actually, my soup is cold.|I wake up at seven.|It is windy today.
# paying|Paying the bill
n En Estados Unidos la propina (tip) suele ser del 15 al 20 por ciento.
w bill|cuenta|🧾
w tip|propina
w cash|efectivo|💵
w credit card|tarjeta de crédito|💳
w change|cambio
w receipt|recibo
p Can we have the bill, please?|¿Nos trae la cuenta, por favor?
p Can I pay by card?|¿Puedo pagar con tarjeta?
p Keep the change.|Quédese con el cambio.
d How would you like to pay?|By card, please.|I like pizza.|It is on the left.
@unit shopping_and_money|5|A2|🛍️|Shopping & Money|Buy clothes, ask for prices, and handle returns.|general
# clothes|Clothes
w shirt|camisa|👕
w pants|pantalones|👖
w dress|vestido|👗
w shoes|zapatos|👟
w jacket|chamarra|🧥
w socks|calcetines|🧦
p I am looking for a black jacket.|Busco una chamarra negra.
p Do you have this shirt in blue?|¿Tiene esta camisa en azul?
p These shoes are very comfortable.|Estos zapatos son muy cómodos.
d Can I help you?|Yes, I am looking for a jacket.|I am at home.|She is my cousin.
# sizes_try|Sizes & fitting
w size|talla
w small|chico
w large|grande
w fitting room|probador
w too tight|muy apretado
w too big|muy grande
p Can I try this on?|¿Me lo puedo probar?
p Do you have a larger size?|¿Tiene una talla más grande?
p It fits me perfectly.|Me queda perfecto.
d How does it fit?|It is a little tight. Do you have a larger size?|It is half past six.|My name is Eva.
# prices_pay|Prices & discounts
n "How much is it?" para un precio; "How much are they?" para varios.
w price|precio
w cheap|barato
w expensive|caro
w discount|descuento
w on sale|en oferta
w total|total
p How much is this?|¿Cuánto cuesta esto?
p It is too expensive for me.|Es demasiado caro para mí.
p Is there a discount?|¿Hay algún descuento?
d How much is this bag?|It is forty dollars.|It is very sunny.|I am from Chile.
# returns_refunds|Returns & refunds
w return|devolver
w exchange|cambiar
w receipt|ticket de compra
w broken|roto
w warranty|garantía
w store credit|saldo a favor
p I would like to return this item.|Quisiera devolver este artículo.
p It does not work. Can I exchange it?|No funciona. ¿Puedo cambiarlo?
p Do you have the receipt?|¿Tiene el ticket de compra?
d What seems to be the problem?|It is broken. I would like a refund.|I live in Madrid.|It is a quarter to five.
# online_shop|Shopping online
w cart|carrito|🛒
w order|pedido|📦
w shipping|envío
w delivery|entrega
w track|rastrear
w out of stock|agotado
p When will my order arrive?|¿Cuándo llegará mi pedido?
p This item is out of stock.|Este artículo está agotado.
p Is shipping free?|¿El envío es gratis?
d When will my order arrive?|It should arrive in three days.|I am a student.|It is my sister.
@unit travel_and_tourism|6|A2|✈️|Travel & Tourism|Airports, hotels, directions, and sightseeing.|travel
# airport|At the airport
n "Boarding pass" = pase de abordar; "gate" = puerta de embarque.
w passport|pasaporte|🛂
w boarding pass|pase de abordar
w gate|puerta de embarque
w luggage|equipaje|🧳
w flight|vuelo|✈️
w delayed|retrasado
p Where is the check-in counter?|¿Dónde está el mostrador de registro?
p My flight is delayed.|Mi vuelo está retrasado.
p Do you have anything to declare?|¿Tiene algo que declarar?
d What is the purpose of your visit?|I am here on vacation.|I like tea.|It is cold today.
# hotel|Checking into a hotel
w reservation|reservación
w check in|registrarse
w check out|salir del hotel
w single room|habitación sencilla
w key card|tarjeta llave
w breakfast included|desayuno incluido
p I have a reservation under Lopez.|Tengo una reservación a nombre de López.
p What time is check-out?|¿A qué hora es la salida?
p Is breakfast included?|¿Incluye desayuno?
d Good evening. Do you have a reservation?|Yes, under the name Lopez.|I am a doctor.|It is on the table.
# directions|Asking for directions
n "Go straight" = sigue derecho. "Turn left/right" = da vuelta a la izquierda/derecha.
w turn left|gira a la izquierda|⬅️
w turn right|gira a la derecha|➡️
w go straight|sigue derecho|⬆️
w corner|esquina
w block|cuadra
w far|lejos
p Excuse me, how do I get to the museum?|Disculpe, ¿cómo llego al museo?
p Go straight and turn left at the corner.|Siga derecho y gire a la izquierda en la esquina.
p Is it far from here?|¿Está lejos de aquí?
d How do I get to the museum?|Go straight, then turn left.|I have two brothers.|It costs ten dollars.
# sightseeing|Sightseeing
w museum|museo|🏛️
w tour|recorrido
w guide|guía
w souvenir|recuerdo
w view|vista|🏞️
w entrance fee|costo de entrada
p What time does the tour start?|¿A qué hora empieza el recorrido?
p Can you take a photo of us?|¿Nos puede tomar una foto?
p The view from here is amazing.|La vista desde aquí es increíble.
d Can you take a photo of us?|Sure, smile!|I am from Cuba.|It is a red car.
# emergencies|Travel emergencies
n En Estados Unidos y México el número de emergencias es 911.
w emergency|emergencia|🚨
w police|policía|👮
w lost|perdido
w stolen|robado
w ambulance|ambulancia|🚑
w embassy|embajada
p Help! I lost my passport.|¡Ayuda! Perdí mi pasaporte.
p My wallet was stolen.|Me robaron la cartera.
p Please call an ambulance.|Por favor llame a una ambulancia.
d What happened?|I lost my wallet on the bus.|I like soup.|It is half past nine.
@unit health_and_body|7|A2|🩺|Health & Body|Describe symptoms, visit the doctor, and stay healthy.|personal
# body_parts|Body parts
w head|cabeza
w stomach|estómago
w throat|garganta
w back|espalda
w arm|brazo
w knee|rodilla
p My head hurts.|Me duele la cabeza.
p I have a pain in my back.|Tengo dolor de espalda.
p She hurt her knee.|Ella se lastimó la rodilla.
d What is wrong?|My stomach hurts.|I am from Texas.|It is sunny.
# symptoms|Symptoms
n "I have a headache" (no "I have pain of head").
w fever|fiebre|🤒
w cough|tos
w headache|dolor de cabeza
w sore throat|dolor de garganta
w dizzy|mareado
w sick|enfermo
p I have had a fever since yesterday.|Tengo fiebre desde ayer.
p I feel dizzy and tired.|Me siento mareado y cansado.
p I have a sore throat and a cough.|Tengo dolor de garganta y tos.
d How are you feeling?|I have a fever and a cough.|I am on the bus.|It is my phone.
# pharmacy|At the pharmacy
w medicine|medicina|💊
w prescription|receta médica
w pills|pastillas
w painkiller|analgésico
w allergy|alergia
w side effects|efectos secundarios
p Do I need a prescription for this?|¿Necesito receta para esto?
p Take one pill twice a day.|Tome una pastilla dos veces al día.
p Are there any side effects?|¿Tiene efectos secundarios?
d How often should I take this?|Twice a day after meals.|It is next to the bank.|I like blue.
# doctor_visit|At the doctor
w appointment|cita
w doctor|doctor|🧑‍⚕️
w check-up|revisión médica
w blood test|análisis de sangre
w treatment|tratamiento
w rest|descansar
p I would like to make an appointment.|Quisiera hacer una cita.
p How long have you had these symptoms?|¿Desde cuándo tiene estos síntomas?
p You need to rest and drink water.|Necesita descansar y tomar agua.
d How long have you felt this way?|About three days.|Two brothers.|It is in the kitchen.
# healthy_habits|Healthy habits
w exercise|ejercicio|🏃
w sleep|dormir
w diet|dieta|🥗
w stress|estrés
w water|agua|💧
w healthy|saludable
p I try to exercise three times a week.|Intento hacer ejercicio tres veces por semana.
p You should sleep at least seven hours.|Deberías dormir al menos siete horas.
p Drinking water is good for you.|Tomar agua es bueno para ti.
d How do you stay healthy?|I exercise and sleep well.|I am at the bank.|It is a taxi.
@unit work_and_business|8|B1|💼|Work & Business|Meetings, emails, interviews, and office talk.|work
# interview|Job interviews
n "Tell me about yourself" casi siempre es la primera pregunta: prepara 3 frases.
w experience|experiencia
w strength|fortaleza
w weakness|debilidad
w skills|habilidades
w resume|currículum
w salary|salario|💰
p I have five years of experience in marketing.|Tengo cinco años de experiencia en mercadotecnia.
p My greatest strength is teamwork.|Mi mayor fortaleza es el trabajo en equipo.
p Why do you want to work here?|¿Por qué quiere trabajar aquí?
d Tell me about yourself.|I am a marketing specialist with five years of experience.|I live near the park.|It is half past two.
# meetings|Meetings
w agenda|agenda
w deadline|fecha límite
w schedule|programar
w attend|asistir
w minutes|minuta
w follow up|dar seguimiento
p Let's start with the agenda.|Empecemos con la agenda.
p Could you share your screen, please?|¿Podrías compartir tu pantalla, por favor?
p We need to finish this by Friday.|Necesitamos terminar esto para el viernes.
d Can everyone hear me?|Yes, we can hear you clearly.|I am from Chile.|It is my birthday.
# emails|Writing emails
n "I am writing to…" abre un correo formal. "Best regards" lo cierra.
w attachment|archivo adjunto|📎
w regards|saludos
w reply|responder
w forward|reenviar
w subject|asunto
w urgent|urgente
p I am writing to ask about the project.|Le escribo para preguntar sobre el proyecto.
p Please find the report attached.|Adjunto encontrará el reporte.
p I look forward to hearing from you.|Quedo atento a su respuesta.
d Did you get my email?|Yes, I will reply this afternoon.|It is very cold.|I like Italian food.
# smalltalk_office|Office small talk
w coworker|compañero de trabajo
w coffee break|pausa para el café|☕
w lunch break|hora de comer
w busy week|semana ocupada
w promotion|ascenso
w deadline pressure|presión por entregas
p How was your weekend?|¿Cómo estuvo tu fin de semana?
p Do you want to grab a coffee?|¿Quieres ir por un café?
p It has been a really busy week.|Ha sido una semana muy ocupada.
d Do you want to grab a coffee?|Sure, I need a break.|I am a doctor.|It is on the corner.
# presentations|Presentations
w slide|diapositiva
w audience|audiencia
w topic|tema
w goal|objetivo
w conclusion|conclusión
w questions|preguntas
p Today I will talk about our sales results.|Hoy hablaré sobre nuestros resultados de ventas.
p Let me move on to the next slide.|Paso a la siguiente diapositiva.
p Thank you for listening. Any questions?|Gracias por escuchar. ¿Alguna pregunta?
d Does anyone have questions?|Yes, could you explain the last slide?|I am from Peru.|It is five dollars.
@unit social_life|9|B1|🎉|Social Life|Invite people, share opinions, and tell stories.|personal
# invitations|Invitations
w invite|invitar
w party|fiesta|🎉
w come over|venir a casa
w available|disponible
w busy|ocupado
w RSVP|confirmar asistencia
p Would you like to come to my party?|¿Te gustaría venir a mi fiesta?
p I would love to, but I am busy that day.|Me encantaría, pero ese día estoy ocupado.
p What time should I be there?|¿A qué hora debo llegar?
d Are you free on Saturday?|Yes, I would love to come.|It is a red bag.|I wake up at six.
# hobbies|Hobbies & free time
w hobby|pasatiempo
w hiking|senderismo|🥾
w painting|pintura|🎨
w gym|gimnasio|🏋️
w movie|película|🎬
w in my free time|en mi tiempo libre
p In my free time, I like to read.|En mi tiempo libre me gusta leer.
p I have been playing guitar for two years.|Llevo dos años tocando guitarra.
p What do you do for fun?|¿Qué haces para divertirte?
d What do you do for fun?|I play soccer on weekends.|I live in Mexico.|It is raining.
# opinions|Giving opinions
n "I think that…" y "In my opinion…" son tus mejores amigos para opinar.
w I think|yo pienso
w in my opinion|en mi opinión
w I agree|estoy de acuerdo
w I disagree|no estoy de acuerdo
w maybe|tal vez
w to be honest|para ser honesto
p In my opinion, this movie is great.|En mi opinión, esta película es genial.
p I agree with you completely.|Estoy completamente de acuerdo contigo.
p To be honest, I do not like it.|Para ser honesto, no me gusta.
d What do you think about this idea?|I think it is a good plan.|It is next to the bank.|He is my uncle.
# plans_future|Making plans
n "I am going to" = plan decidido. "I will" = decisión en el momento.
w I am going to|voy a
w next week|la próxima semana
w tomorrow|mañana
w plan|plan
w decide|decidir
w probably|probablemente
p I am going to travel next month.|Voy a viajar el próximo mes.
p We will probably stay home tonight.|Probablemente nos quedemos en casa esta noche.
p What are you doing this weekend?|¿Qué vas a hacer este fin de semana?
d What are your plans for the weekend?|I am going to visit my family.|I was at work yesterday.|It is a blue shirt.
# past_stories|Telling stories
n Pasado simple: "I went", "I saw", "I ate". Muchos verbos son irregulares.
w yesterday|ayer
w last year|el año pasado
w went|fui / fue
w saw|vi / vio
w happened|sucedió
w suddenly|de repente
p Last year I went to Canada.|El año pasado fui a Canadá.
p Suddenly, the lights went out.|De repente, se apagaron las luces.
p I could not believe what happened.|No podía creer lo que sucedió.
d What did you do last weekend?|I went to the beach with my friends.|I am going to sleep.|It is my phone.
@unit fluent_moves|10|B2|🗣️|Fluent Moves|Phone calls, negotiating, and polite disagreement.|work
# phone_calls|Phone calls
n "Hold on" y "Hang on" significan espera un momento.
w hold on|espera un momento
w speak up|hablar más fuerte
w voicemail|buzón de voz
w call back|devolver la llamada
w bad connection|mala conexión
w extension|extensión
p Could you speak a little louder, please?|¿Podría hablar un poco más fuerte, por favor?
p I will call you back in ten minutes.|Te devuelvo la llamada en diez minutos.
p The line is breaking up.|Se está cortando la llamada.
d Hello, may I speak to Mr. Smith?|One moment, please. I will transfer you.|I am from Peru.|It is on the table.
# negotiating|Negotiating
w offer|oferta
w deal|trato
w compromise|llegar a un acuerdo
w budget|presupuesto
w terms|condiciones
w counteroffer|contraoferta
p That is a little higher than our budget.|Eso es un poco más de nuestro presupuesto.
p Could we meet in the middle?|¿Podríamos llegar a un punto medio?
p We have a deal.|Tenemos un trato.
d Can you lower the price?|I can offer a ten percent discount.|I am at the bank.|It is quarter to six.
# disagree_politely|Disagreeing politely
n Suaviza el desacuerdo: "I see your point, but…" suena mucho mejor que "You are wrong".
w I see your point|entiendo tu punto
w however|sin embargo
w on the other hand|por otro lado
w I am not sure|no estoy seguro
w that said|dicho eso
w fair enough|es justo
p I see your point, but I have a different view.|Entiendo tu punto, pero tengo otra opinión.
p On the other hand, it could be expensive.|Por otro lado, podría ser costoso.
p I am not sure that is the best option.|No estoy seguro de que esa sea la mejor opción.
d I think we should cancel the project.|I see your point, but let's give it another week.|I like soup.|It is a taxi.
# describing_problems|Describing problems
w issue|problema
w fix|arreglar
w not working|no funciona
w keeps happening|sigue pasando
w as soon as possible|lo antes posible
w workaround|solución alternativa
p The app keeps crashing every time I open it.|La app se cierra cada vez que la abro.
p Could you look into this as soon as possible?|¿Podría revisarlo lo antes posible?
p We found a temporary workaround.|Encontramos una solución temporal.
d What seems to be the issue?|The system keeps freezing.|I am from Brazil.|It is my sister.
# idioms|Everyday idioms
n Los modismos no se traducen literalmente: "break the ice" = romper el hielo.
w break the ice|romper el hielo|🧊
w piece of cake|pan comido|🍰
w under the weather|enfermo, indispuesto
w hit the books|ponerse a estudiar
w call it a day|dar por terminado el día
w once in a blue moon|muy rara vez
p That exam was a piece of cake.|Ese examen fue pan comido.
p I am feeling a bit under the weather.|Me siento un poco mal.
p Let's call it a day.|Terminemos por hoy.
d How was the test?|It was a piece of cake.|It is on the left.|I live in Cuba.
@unit big_ideas|11|B2|💡|Big Ideas|Discuss technology, the environment, news, and culture.|study
# technology|Technology
w device|dispositivo
w software|programa
w update|actualización
w artificial intelligence|inteligencia artificial|🤖
w privacy|privacidad
w download|descargar
p Technology has changed the way we work.|La tecnología ha cambiado la forma en que trabajamos.
p I always update my apps.|Siempre actualizo mis aplicaciones.
p Privacy online is very important.|La privacidad en línea es muy importante.
d How has technology changed your life?|It helps me learn faster.|It is on the corner.|I am a doctor.
# environment|Environment
w climate change|cambio climático|🌍
w recycle|reciclar|♻️
w pollution|contaminación
w renewable energy|energía renovable
w waste|desperdicio
w sustainable|sustentable
p We should reduce plastic waste.|Deberíamos reducir los desechos de plástico.
p Solar energy is renewable.|La energía solar es renovable.
p Small actions can make a big difference.|Las pequeñas acciones pueden hacer una gran diferencia.
d What can we do to protect the planet?|We can recycle and use less plastic.|I am from Spain.|It is a red car.
# news_media|News & media
w headline|titular
w journalist|periodista
w source|fuente
w fake news|noticias falsas
w broadcast|transmisión
w trend|tendencia
p Did you see the news this morning?|¿Viste las noticias esta mañana?
p You should always check your sources.|Siempre debes verificar tus fuentes.
p That story is trending on social media.|Esa historia es tendencia en redes sociales.
d Did you read the news today?|Yes, the headline was surprising.|I like tea.|It is half past nine.
# culture|Culture & traditions
w tradition|tradición
w festival|festival
w customs|costumbres
w celebrate|celebrar|🎊
w heritage|patrimonio
w local|local
p In my country, we celebrate the Day of the Dead.|En mi país celebramos el Día de Muertos.
p Every culture has its own traditions.|Cada cultura tiene sus propias tradiciones.
p I would love to learn more about your customs.|Me encantaría aprender más sobre tus costumbres.
d What is a tradition in your country?|We celebrate with music and food.|It is a quarter to six.|I am at home.
# future_goals|Goals & the future
w goal|meta
w achieve|lograr
w improve|mejorar
w career|carrera
w dream|sueño
w in the long run|a largo plazo
p My goal is to be fluent in English next year.|Mi meta es hablar inglés con fluidez el próximo año.
p I hope to achieve my dreams.|Espero lograr mis sueños.
p In the long run, practice makes perfect.|A largo plazo, la práctica hace al maestro.
d Where do you see yourself in five years?|I see myself leading a team.|It is raining.|He is my brother.
'''

LEVEL_TO_RANK = {"A1": 0, "A2": 1, "B1": 2, "B2": 3}
PROFILE_LEVEL_RANK = {"beginner": 0, "elementary": 1, "intermediate": 2, "advanced": 3}
GOAL_LABELS = {"work": "Work", "travel": "Travel", "study": "Study", "exams": "Exams", "personal": "Personal growth"}

SECTION_DEFS = [
    {"code": "foundations", "title": "Foundations", "level": "A1", "units": ["first_steps", "everyday_english", "home_and_city"]},
    {"code": "real_life", "title": "Real Life", "level": "A2", "units": ["at_the_restaurant", "shopping_and_money", "travel_and_tourism", "health_and_body"]},
    {"code": "career_social", "title": "Career & Social", "level": "B1", "units": ["work_and_business", "social_life"]},
    {"code": "fluency", "title": "Fluency", "level": "B2", "units": ["fluent_moves", "big_ideas"]},
]


def _parse_curriculum(text):
    units, unit, lesson = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@unit "):
            code, order, level, icon, title, desc, goal = line[6:].split("|")
            unit = {"code": code, "order": int(order), "level": level, "icon": icon, "title": title,
                    "description": desc, "goal": goal, "xp_required": 0, "lessons": []}
            units.append(unit)
            lesson = None
            continue
        tag, _, rest = line.partition(" ")
        f = rest.split("|")
        if tag == "#":
            lesson = {"id": f[0], "title": f[1], "note": "", "words": [], "phrases": [], "dialogs": []}
            unit["lessons"].append(lesson)
        elif tag == "n":
            lesson["note"] = rest
        elif tag == "w":
            lesson["words"].append({"en": f[0], "es": f[1], "emoji": f[2] if len(f) > 2 else ""})
        elif tag == "p":
            lesson["phrases"].append({"en": f[0], "es": f[1]})
        elif tag == "d":
            lesson["dialogs"].append({"q": f[0], "a": f[1], "wrong": f[2:]})
    for si, sec in enumerate(SECTION_DEFS):
        for code in sec["units"]:
            for u in units:
                if u["code"] == code:
                    u["section"] = si
    for u in units:
        # "topics" se conserva por compatibilidad: cada lección es un tema, más el reto final de la unidad.
        u["topics"] = [{"id": l["id"], "title": l["title"]} for l in u["lessons"]]
        u["topics"].append({"id": "challenge", "title": "Unit challenge", "challenge": True})
    return units


LEARNING_UNITS = _parse_curriculum(CURRICULUM_TEXT)

LEARNING_TOOL_LABELS = {
    "pronunciation": "Pronunciation",
    "writing": "Writing",
    "reading": "Reading",
    "dictado": "Listening",
}


def get_unit(code):
    return next((u for u in LEARNING_UNITS if u["code"] == code), None)


def get_topic(unit, topic_id):
    return next((t for t in (unit or {}).get("topics", []) if t["id"] == topic_id), None)


def get_lesson(unit, lesson_id):
    return next((l for l in (unit or {}).get("lessons", []) if l["id"] == lesson_id), None)


def fetch_learning_progress(user_id):
    """Devuelve un dict {(unit_code, topic_id): fila} solo con los temas completados."""
    client = supabase_admin or supabase
    if not client:
        return {}
    try:
        rows = (
            client.table("learning_progress")
            .select("unit_code,topic_id,tool,score,completed")
            .eq("user_id", user_id)
            .execute()
        ).data or []
    except Exception as exc:
        print(f"[LEARNING PROGRESS] {exc}")
        return {}
    return {(r["unit_code"], r["topic_id"]): r for r in rows if r.get("completed")}


def _upsert_progress(client, user_id, unit_code, topic_id, tool, score, passed):
    """Guarda/actualiza el mejor puntaje. Devuelve (ya_estaba_completado, mejor_puntaje).
    OJO: se usa .limit(1) y no .maybe_single(), porque maybe_single devuelve None cuando no hay filas
    y eso hacía que el primer intento de cada tema nunca se guardara."""
    res = (
        client.table("learning_progress").select("id,completed,score")
        .eq("user_id", user_id).eq("unit_code", unit_code).eq("topic_id", topic_id)
        .limit(1).execute()
    )
    rows = getattr(res, "data", None) or []
    if rows:
        row = rows[0]
        already_done = bool(row.get("completed"))
        best = max(score, row.get("score") or 0)
        client.table("learning_progress").update({
            "tool": tool, "score": best, "completed": already_done or passed,
        }).eq("id", row["id"]).execute()
        return already_done, best
    client.table("learning_progress").insert({
        "user_id": user_id, "unit_code": unit_code, "topic_id": topic_id,
        "tool": tool, "score": score, "completed": passed,
    }).execute()
    return False, score


def record_learning_progress(user_id, unit_code, topic_id, tool, score):
    """Compatibilidad con las herramientas sueltas (escritura, lectura...). Devuelve None si no aplica."""
    if not unit_code or not topic_id:
        return None
    unit = get_unit(unit_code)
    if not unit or not get_topic(unit, topic_id):
        return None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None
    client = supabase_admin or supabase
    if not client:
        return None
    passed = score >= PASS_THRESHOLD
    try:
        already_done, _best = _upsert_progress(client, user_id, unit_code, topic_id, tool, score, passed)
    except Exception as exc:
        print(f"[LEARNING PROGRESS SAVE] {exc}")
        return None
    newly_completed = passed and not already_done
    if newly_completed:
        award_xp(user_id, 30)
    progress = fetch_learning_progress(user_id)
    total = len(unit["topics"])
    completed_count = sum(1 for t in unit["topics"] if (unit_code, t["id"]) in progress)
    return {"passed": passed, "newly_completed": newly_completed, "unit_completed": completed_count == total,
            "completed_topics": completed_count, "total_topics": total}


def stars_for(score):
    if score is None:
        return 0
    return 3 if score >= 90 else 2 if score >= 75 else 1 if score >= PASS_THRESHOLD else 0


def daily_target_lessons(minutes):
    try:
        return max(1, min(8, round(int(minutes) / 5)))
    except (TypeError, ValueError):
        return 2


# ---------------------------------------------------------------------------
#  Registro de sesiones (tabla opcional learning_sessions; si no existe, todo sigue funcionando)
# ---------------------------------------------------------------------------
def _xp_allowed(user_id):
    """Anti-farmeo: máximo 60 sesiones con XP por día y por usuario (un humano no llega ahí)."""
    ok, _w = _rate_hit((user_id, "xp_day"), 60, 86400)
    return ok


def _log_session(user_id, kind, unit_code, lesson_id, score, stars, xp, mistakes, seconds):
    client = supabase_admin or supabase
    if not client:
        return
    try:
        client.table("learning_sessions").insert({
            "user_id": user_id, "kind": kind, "unit_code": unit_code, "lesson_id": lesson_id,
            "score": score, "stars": stars, "xp": xp, "mistakes": mistakes or [], "seconds": seconds,
        }).execute()
    except Exception as exc:
        print(f"[LEARNING SESSION LOG] {exc}")


def sessions_today(user_id):
    client = supabase_admin or supabase
    if not client:
        return 0
    try:
        start = datetime.now(timezone.utc).date().isoformat()
        rows = (client.table("learning_sessions").select("id,kind").eq("user_id", user_id)
                .gte("created_at", start).limit(80).execute()).data or []
        return sum(1 for r in rows if r.get("kind") not in ("plan_bonus", "level_change"))
    except Exception:
        return 0


def session_days(user_id, since_iso):
    """Fechas (ISO) en las que hubo lecciones, para la racha semanal."""
    client = supabase_admin or supabase
    out = set()
    if not client:
        return out
    try:
        rows = (client.table("learning_sessions").select("created_at").eq("user_id", user_id)
                .gte("created_at", since_iso).limit(500).execute()).data or []
        for r in rows:
            ca = r.get("created_at")
            if ca:
                try:
                    out.add(datetime.fromisoformat(ca.replace("Z", "+00:00")).date().isoformat())
                except Exception:
                    pass
    except Exception:
        pass
    return out


def recent_mistakes(user_id, limit=8):
    """Palabras/frases falladas en las últimas lecciones (las más recientes primero, sin repetir)."""
    client = supabase_admin or supabase
    if not client:
        return []
    try:
        rows = (client.table("learning_sessions").select("mistakes,created_at").eq("user_id", user_id)
                .order("created_at", desc=True).limit(12).execute()).data or []
    except Exception:
        return []
    seen, out = set(), []
    for r in rows:
        for m in (r.get("mistakes") or []):
            if isinstance(m, dict) and m.get("en") and m["en"].lower() not in seen:
                seen.add(m["en"].lower())
                out.append({"en": m["en"], "es": m.get("es", "")})
                if len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------------------
#  Estado de la ruta: qué está abierto, qué sigue, qué se recomienda
# ---------------------------------------------------------------------------
def _profile_for_path(user_id):
    client = supabase_admin or supabase
    out = {"cefr_level": "", "learning_goal": "", "daily_goal_minutes": 10, "xp": 0}
    if not client:
        return out
    try:
        rows = (client.table("profiles").select("cefr_level,learning_goal,daily_goal_minutes,xp")
                .eq("id", user_id).limit(1).execute()).data or []
        if rows:
            r = rows[0]
            out.update({
                "cefr_level": (r.get("cefr_level") or "").lower(),
                "learning_goal": (r.get("learning_goal") or "").lower(),
                "daily_goal_minutes": r.get("daily_goal_minutes") or 10,
                "xp": r.get("xp") or 0,
            })
    except Exception as exc:
        print(f"[LEARNING PATH PROFILE] {exc}")
    return out


def _gem_unlocks(user_id):
    client = supabase_admin or supabase
    if not client:
        return set()
    try:
        rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user_id).execute().data or []
        return {r["unit_code"] for r in rows}
    except Exception as exc:
        print(f"[LEARNING PATH GEM UNLOCKS] {exc}")
        return set()


def compute_path(progress, level_rank, goal, gem_unlocked):
    """Calcula secciones, unidades y lecciones con su estado, y la 'siguiente lección' recomendada."""
    sections_out = []
    prev_pct = 1.0
    unit_by_code = {u["code"]: u for u in LEARNING_UNITS}
    for si, sdef in enumerate(SECTION_DEFS):
        sec_open = si == 0 or si <= level_rank or prev_pct >= 0.6
        placed = si < level_rank   # el examen/tu desempeño ya te ubicó por encima de esta sección
        units_out = []
        done_total = lesson_total = 0
        for code in sdef["units"]:
            u = unit_by_code[code]
            unit_open = sec_open or code in gem_unlocked
            lessons, prev_done = [], True
            for i, t in enumerate(u["topics"]):
                row = progress.get((code, t["id"]))
                completed = bool(row)
                avail = unit_open and (placed or i == 0 or lessons[i - 1]["completed"])  # en secciones superadas puedes repasar en cualquier orden
                lessons.append({
                    "id": t["id"], "title": t["title"], "challenge": bool(t.get("challenge")),
                    "completed": completed, "score": row.get("score") if row else None,
                    "stars": stars_for(row.get("score")) if row else 0,
                    "state": "done" if completed else ("available" if avail else "locked"),
                })
            done = sum(1 for l in lessons if l["completed"])
            done_total += done
            lesson_total += len(lessons)
            units_out.append({
                "code": code, "order": u["order"], "title": u["title"], "description": u["description"],
                "icon": u["icon"], "level": u["level"], "goal": u["goal"], "section": si,
                "total_topics": len(lessons), "completed_topics": done, "completed": done == len(lessons),
                "unlocked": unit_open, "xp_required": 0, "lessons": lessons,
                "recommended": bool(goal and u["goal"] == goal and unit_open and done < len(lessons)),
                "stars": sum(l["stars"] for l in lessons), "max_stars": 3 * len(lessons),
            })
        prev_pct = 1.0 if placed else ((done_total / lesson_total) if lesson_total else 0)
        sections_out.append({
            "code": sdef["code"], "title": sdef["title"], "level": sdef["level"], "open": sec_open, "placed": placed,
            "current": si == level_rank,
            "done": done_total, "total": lesson_total, "units": units_out,
        })

    # Siguiente lección: empieza por la sección que corresponde a su nivel; dentro de la sección,
    # primero las unidades que coinciden con su objetivo; las secciones anteriores quedan como repaso.
    order = list(range(level_rank, len(sections_out))) + list(range(0, level_rank))
    nxt = None
    for si in order:
        sec = sections_out[si]
        if not sec["open"]:
            continue
        units = sorted(sec["units"], key=lambda x: (0 if x["recommended"] else 1, x["order"]))
        for un in units:
            if not un["unlocked"] or un["completed"]:
                continue
            les = next((l for l in un["lessons"] if l["state"] == "available"), None)
            if les:
                if un["recommended"]:
                    reason = "Matches your goal: " + GOAL_LABELS.get(goal, goal.title())
                elif si == level_rank:
                    reason = "Picked for your level"
                else:
                    reason = "Next in your path"
                nxt = {"unit_code": un["code"], "unit_title": un["title"], "icon": un["icon"],
                       "lesson_id": les["id"], "lesson_title": les["title"], "challenge": les["challenge"],
                       "reason": reason}
                break
        if nxt:
            break
    return sections_out, nxt


# ---------------------------------------------------------------------------
#  Generador de ejercicios (determinista a partir de los datos del currículo)
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ'’-]+")


def _tokens(sentence):
    return _TOKEN_RE.findall(sentence)


def _norm(text):
    return " ".join(w.lower().replace("’", "'") for w in _tokens(text))


class _Cycle:
    def __init__(self, items, rng):
        self.items = list(items)
        self.rng = rng
        self.queue = []

    def next(self):
        if not self.items:
            return None
        if not self.queue:
            self.queue = list(self.items)
            self.rng.shuffle(self.queue)
        return self.queue.pop()


def _distractors(rng, answer, pool, n, key=lambda x: x):
    seen = {key(answer).lower()}
    cand = []
    for x in pool:
        k = key(x).lower()
        if k not in seen:
            seen.add(k)
            cand.append(x)
    rng.shuffle(cand)
    return cand[:n]


LESSON_RECIPE = ["pick_meaning", "pick_word", "listen_pick", "pick_meaning", "match", "build", "fill",
                 "speak", "listen_pick", "build", "dialog", "type_listen", "speak", "build"]
CHALLENGE_RECIPE = ["pick_meaning", "listen_pick", "pick_word", "match", "build", "fill", "speak", "dialog",
                    "build", "type_listen", "pick_word", "fill", "dialog", "build", "speak", "listen_pick"]
REVIEW_RECIPE = ["pick_meaning", "listen_pick", "pick_word", "build", "match", "pick_meaning", "type_listen",
                 "fill", "build", "pick_word"]


def build_exercises(unit, lessons, recipe, rng, diff=0, extra_words=None):
    """lessons: lecciones fuente. diff<0 = más fácil, diff>0 = más difícil (el estudiante supera la unidad)."""
    words = [dict(w, lesson=l["id"]) for l in lessons for w in l["words"]]
    phrases = [dict(p, lesson=l["id"]) for l in lessons for p in l["phrases"]]
    dialogs = [dict(d, lesson=l["id"]) for l in lessons for d in l["dialogs"]]
    if extra_words:
        words = [dict(w, lesson="review") for w in extra_words] + words
    unit_words = [w for l in unit["lessons"] for w in l["words"]]
    unit_phrases = [p for l in unit["lessons"] for p in l["phrases"]]
    word_cycle = _Cycle(words, rng)
    phrase_cycle = _Cycle(phrases, rng)
    dialog_cycle = _Cycle(dialogs, rng)
    single_tokens = sorted({t for w in unit_words for t in _tokens(w["en"]) if len(t) >= 3})
    out = []

    for n, kind in enumerate(recipe):
        ex = None
        if kind in ("pick_meaning", "pick_word", "listen_pick", "type_translate"):
            w = word_cycle.next()
            if not w:
                continue
            ref = {"en": w["en"], "es": w["es"]}
            if kind == "type_translate":
                ex = {"type": "type_translate", "q": w["es"], "answer": w["en"], "ref": ref}
            elif kind == "pick_word":
                d = _distractors(rng, w, unit_words, 3, key=lambda x: x["en"])
                opts = [w["en"]] + [x["en"] for x in d]
                rng.shuffle(opts)
                ex = {"type": "pick_word", "q": w["es"], "emoji": w.get("emoji", ""), "options": opts,
                      "answer": w["en"], "ref": ref}
            elif kind == "listen_pick":
                d = _distractors(rng, w, unit_words, 3, key=lambda x: x["en"])
                opts = [w["en"]] + [x["en"] for x in d]
                rng.shuffle(opts)
                ex = {"type": "listen_pick", "say": w["en"], "options": opts, "answer": w["en"], "ref": ref}
            else:
                if diff > 0 and n % 2 == 1:
                    ex = {"type": "type_translate", "q": w["es"], "answer": w["en"], "ref": ref}
                else:
                    d = _distractors(rng, w, unit_words, 3, key=lambda x: x["es"])
                    opts = [w["es"]] + [x["es"] for x in d]
                    rng.shuffle(opts)
                    ex = {"type": "pick_meaning", "q": w["en"], "say": w["en"], "emoji": w.get("emoji", ""),
                          "options": opts, "answer": w["es"], "ref": ref}
        elif kind == "match":
            picks = rng.sample(words, min(5, len(words)))
            seen, pairs = set(), []
            for w in picks:
                if w["en"].lower() not in seen and w["es"].lower() not in {p["es"].lower() for p in pairs}:
                    seen.add(w["en"].lower())
                    pairs.append({"en": w["en"], "es": w["es"]})
            if len(pairs) >= 3:
                ex = {"type": "match", "pairs": pairs}
        elif kind in ("build", "fill", "speak", "type_listen"):
            p = phrase_cycle.next()
            if not p:
                continue
            ref = {"en": p["en"], "es": p["es"]}
            if kind == "build":
                ans = _tokens(p["en"])
                extra = 4 if diff > 0 else (1 if diff < 0 else 2)
                low = {t.lower() for t in ans}
                spare = [t for t in single_tokens if t.lower() not in low]
                rng.shuffle(spare)
                bank = ans + spare[:extra]
                rng.shuffle(bank)
                ex = {"type": "build", "q": p["es"], "say": p["en"], "answer": p["en"],
                      "answer_tokens": ans, "bank": bank, "ref": ref}
            elif kind == "fill":
                lesson_tokens = {t.lower() for l in lessons for w in l["words"] for t in _tokens(w["en"]) if len(t) >= 3}
                toks = _tokens(p["en"])
                cands = [t for t in toks if t.lower() in lesson_tokens] or [t for t in toks if len(t) >= 4]
                if not cands:
                    continue
                target = max(cands, key=len)
                spare = [t for t in single_tokens if t.lower() != target.lower() and t.lower() not in {x.lower() for x in toks}]
                rng.shuffle(spare)
                opts = [target] + spare[:3]
                rng.shuffle(opts)
                sentence = p["en"].replace(target, "____", 1)
                ex = {"type": "fill", "sentence": sentence, "es": p["es"], "options": opts, "answer": target,
                      "say": p["en"], "ref": ref}
            elif kind == "speak":
                ex = {"type": "speak", "text": p["en"], "es": p["es"], "ref": ref}
            else:
                ex = {"type": "type_listen", "say": p["en"], "answer": p["en"], "es": p["es"], "ref": ref}
        elif kind == "dialog":
            d = dialog_cycle.next()
            if not d:
                continue
            opts = [d["a"]] + list(d["wrong"][:2])
            rng.shuffle(opts)
            ex = {"type": "dialog", "q": d["q"], "say": d["q"], "options": opts, "answer": d["a"],
                  "ref": {"en": d["a"], "es": ""}}
        if ex:
            ex["id"] = f"e{len(out) + 1}"
            out.append(ex)
    return out


def build_lesson_payload(unit, lesson_id, user_rank, mode="lesson", mistakes=None, seed=None):
    rng = random.Random(seed if seed is not None else time.time_ns())
    unit_rank = LEVEL_TO_RANK.get(unit["level"], 0)
    diff = user_rank - unit_rank
    diff = -1 if diff < 0 else (1 if diff > 0 else 0)
    if mode == "review":
        pool_lessons = [l for l in unit["lessons"]]
        words = []
        for m in (mistakes or [])[:8]:
            if m.get("es"):
                words.append({"en": m["en"], "es": m["es"], "emoji": ""})
        ex = build_exercises(unit, pool_lessons, REVIEW_RECIPE, rng, diff=diff, extra_words=words)
        return {"title": "Review: your tricky words", "note": "", "teach": [], "exercises": ex, "challenge": False}
    if lesson_id == "challenge":
        ex = build_exercises(unit, unit["lessons"], CHALLENGE_RECIPE, rng, diff=diff)
        return {"title": unit["title"] + " — Unit challenge", "note": "", "teach": [], "exercises": ex, "challenge": True}
    lesson = get_lesson(unit, lesson_id)
    ex = build_exercises(unit, [lesson], LESSON_RECIPE, rng, diff=diff)
    return {"title": lesson["title"], "note": lesson.get("note", ""), "teach": lesson["words"],
            "exercises": ex, "challenge": False, "difficulty": ["easy", "normal", "hard"][diff + 1]}


# ---------------------------------------------------------------------------
#  Laboratorio de sonidos (estilo ELSA): sonidos difíciles para hispanohablantes
# ---------------------------------------------------------------------------
SOUND_LAB = {
    "th": {"ipa": "θ", "name": "TH suave", "tip": "Saca la punta de la lengua entre los dientes y sopla aire sin voz. No es 't' ni 's'.",
           "words": ["think", "thank", "three", "thumb", "bath", "month"], "phrase": "Thank you for the three thick books."},
    "dh": {"ipa": "ð", "name": "TH sonora", "tip": "Lengua entre los dientes, pero con voz: debe vibrar. No es 'd'.",
           "words": ["this", "that", "mother", "weather", "they", "brother"], "phrase": "This is my mother and that is my brother."},
    "ih": {"ipa": "ɪ", "name": "I corta", "tip": "Más corta y relajada que la 'i' española. 'Ship' no es 'sheep'.",
           "words": ["sit", "ship", "big", "fish", "live", "bit"], "phrase": "Sit in this big chair."},
    "iy": {"ipa": "iː", "name": "I larga", "tip": "Estira la 'i' con los labios sonriendo. 'Sheep', 'seat'.",
           "words": ["seat", "sheep", "beach", "green", "leave", "feel"], "phrase": "Please leave the green sheep on the beach."},
    "ae": {"ipa": "æ", "name": "A abierta", "tip": "Abre la boca como para una 'a' pero con sonido de 'e'. 'Cat' no es 'ket'.",
           "words": ["cat", "black", "hat", "bad", "man", "apple"], "phrase": "The black cat sat on a flat map."},
    "ah": {"ipa": "ʌ", "name": "A corta", "tip": "Una 'a' corta y relajada desde la garganta. 'Cup' no es 'cop'.",
           "words": ["cup", "bus", "love", "sun", "up", "color"], "phrase": "My brother loves the sun and a cup of juice."},
    "sh": {"ipa": "ʃ", "name": "SH", "tip": "Como pedir silencio: 'shhh'. No es 'ch'.",
           "words": ["ship", "shoe", "fish", "wash", "shop", "nation"], "phrase": "She washes her shoes in the shop."},
    "jh": {"ipa": "dʒ", "name": "J inglesa", "tip": "Como una 'ch' pero con voz. 'Job', 'age'. No es la 'j' española.",
           "words": ["job", "juice", "age", "bridge", "general", "jacket"], "phrase": "Jack has a great job in June."},
    "v": {"ipa": "v", "name": "V", "tip": "Dientes superiores sobre el labio inferior y vibra. No es 'b'.",
          "words": ["very", "voice", "love", "visit", "never", "move"], "phrase": "I never visit Venice in November."},
    "z": {"ipa": "z", "name": "Z", "tip": "Una 's' con vibración en la garganta. 'Zoo', 'easy'.",
          "words": ["zoo", "easy", "busy", "because", "size", "lazy"], "phrase": "The lazy zebra is busy at the zoo."},
    "r": {"ipa": "ɹ", "name": "R inglesa", "tip": "La lengua no toca el paladar ni vibra: enróllala hacia atrás.",
          "words": ["red", "right", "car", "around", "story", "really"], "phrase": "The red car is really around the corner."},
    "h": {"ipa": "h", "name": "H suave", "tip": "Un soplo suave de aire, mucho más suave que la 'j' española.",
          "words": ["house", "happy", "who", "behind", "hello", "high"], "phrase": "Hello, how is your happy house?"},
    "ng": {"ipa": "ŋ", "name": "NG", "tip": "El sonido sale por la nariz; no pronuncies una 'g' fuerte al final.",
           "words": ["sing", "long", "morning", "thing", "young", "king"], "phrase": "Every morning the young king sings a long song."},
    "w": {"ipa": "w", "name": "W", "tip": "Redondea los labios como para decir 'u' y suéltalos rápido.",
          "words": ["water", "would", "we", "away", "window", "week"], "phrase": "We would walk away from the window this week."},
    "uh": {"ipa": "ʊ", "name": "U corta", "tip": "Una 'u' corta y relajada. 'Book', 'good'.",
           "words": ["book", "good", "look", "foot", "put", "cook"], "phrase": "Look at the good book the cook put down."},
    "uw": {"ipa": "uː", "name": "U larga", "tip": "Alarga la 'u' con los labios redondeados. 'Food', 'blue'.",
           "words": ["food", "blue", "moon", "true", "too", "school"], "phrase": "The blue moon is too bright at school."},
    "er": {"ipa": "ɝ", "name": "ER", "tip": "Una 'e' con la lengua curvada hacia atrás. 'Bird', 'work'.",
           "words": ["bird", "work", "learn", "first", "turn", "world"], "phrase": "The first bird learns to turn in the world."},
    "y": {"ipa": "j", "name": "Y suave", "tip": "Una 'i' rápida que se desliza: 'yes' no es 'jes'.",
          "words": ["yes", "you", "yellow", "young", "year", "yet"], "phrase": "Yes, you are young and yellow is your year."},
}
DEFAULT_SOUND_FOCUS = ["th", "ih", "v", "ae", "sh", "dh"]
_IPA_TO_SAPI = {
    "θ": "th", "ð": "dh", "ɪ": "ih", "i": "iy", "iː": "iy", "ʃ": "sh", "æ": "ae", "ʒ": "zh", "ʊ": "uh",
    "u": "uw", "uː": "uw", "tʃ": "ch", "dʒ": "jh", "ŋ": "ng", "ɛ": "eh", "ʌ": "ah", "ə": "ax", "ɔ": "ao",
    "ɑ": "aa", "ɝ": "er", "ɚ": "er", "ɹ": "r", "j": "y", "ɡ": "g", "eɪ": "ey", "oʊ": "ow", "aɪ": "ay",
}


def normalize_phoneme(p):
    p = (p or "").strip().lower()
    return _IPA_TO_SAPI.get(p, p)


def sound_info(sid):
    s = SOUND_LAB.get(sid)
    return {"id": sid, **s} if s else None


def weak_sounds_from_payload(payload, threshold=65):
    """Sonidos con baja precisión en un solo intento (para mostrar consejos al instante)."""
    found = {}
    for w in payload.get("palabras", []):
        for f in w.get("fonemas", []):
            sid = normalize_phoneme(f.get("fonema"))
            if sid in SOUND_LAB and (f.get("precision") or 0) < threshold:
                found[sid] = min(found.get(sid, 100), f.get("precision") or 0)
    return [{"id": s, "ipa": SOUND_LAB[s]["ipa"], "name": SOUND_LAB[s]["name"], "tip": SOUND_LAB[s]["tip"],
             "accuracy": a} for s, a in sorted(found.items(), key=lambda kv: kv[1])][:3]


def phoneme_stats(user_id, limit=40):
    """Promedio de precisión por fonema, leído del historial real de pronunciación."""
    client = supabase_admin or supabase
    stats = {}
    if not client:
        return stats
    try:
        rows = (client.table("historial_pronunciacion").select("detalles_json,created_at")
                .eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()).data or []
    except Exception as exc:
        print(f"[PHONEME STATS] {exc}")
        return stats
    for r in rows:
        d = r.get("detalles_json")
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                d = None
        if not isinstance(d, dict):
            continue
        for w in d.get("palabras", []) or []:
            for f in w.get("fonemas", []) or []:
                sid = normalize_phoneme(f.get("fonema"))
                acc = f.get("precision")
                if sid in SOUND_LAB and isinstance(acc, (int, float)):
                    s = stats.setdefault(sid, [0.0, 0])
                    s[0] += acc
                    s[1] += 1
    return {k: {"avg": round(v[0] / v[1], 1), "samples": v[1]} for k, v in stats.items() if v[1] > 0}


ALLOWED_AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@app.post("/api/perfil")
def update_profile():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    username = re.sub(r"[<>\u0000-\u001f\u007f]", "", str(body.get("username") or "")).strip()
    if not (2 <= len(username) <= 30):
        return json_error("El nombre debe tener entre 2 y 30 caracteres.")
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        client.table("profiles").update({"username": username}).eq("id", user.id).execute()
        return jsonify({"ok": True, "username": username})
    except Exception as exc:
        return json_error(_err_log("No se pudo guardar el nombre", exc), 500)


@app.post("/api/perfil/avatar")
def upload_avatar():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    file = request.files.get("avatar")
    if not file:
        return json_error("Selecciona una imagen.")
    mime = (file.mimetype or "").lower()
    ext = ALLOWED_AVATAR_TYPES.get(mime)
    if not ext:
        return json_error("Solo se permiten imágenes JPG, PNG o WEBP.")
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        file_bytes = file.read()
        if len(file_bytes) > 4 * 1024 * 1024:
            return json_error("La imagen no debe pesar más de 4 MB.")
        head = file_bytes[:12]
        real = ("jpg" if head[:3] == b"\xff\xd8\xff" else "png" if head[:8] == b"\x89PNG\r\n\x1a\n"
                else "webp" if (head[:4] == b"RIFF" and head[8:12] == b"WEBP") else None)
        if real is None or real != ext:
            return json_error("El archivo no es una imagen válida.")
        path = f"{user.id}/avatar.{ext}"
        client.storage.from_("avatars").upload(
            path, file_bytes, {"content-type": mime, "upsert": "true"}
        )
        public_url = client.storage.from_("avatars").get_public_url(path)
        public_url = f"{public_url.split('?')[0]}?v={int(datetime.now(timezone.utc).timestamp())}"
        client.table("profiles").update({"avatar_url": public_url}).eq("id", user.id).execute()
        return jsonify({"ok": True, "avatar_url": public_url})
    except Exception as exc:
        return json_error(_err_log("No se pudo subir la foto", exc), 500)


@app.get("/health")
def health():
    return jsonify({"ok": True})   # sin detalles de configuración (el panel de admin tiene el diagnóstico completo)


CEFR_LEVELS = {"beginner", "elementary", "intermediate", "advanced"}
LEARNING_GOALS = {"work", "travel", "study", "exams", "personal"}


@app.post("/api/onboarding")
def save_onboarding():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    goal = (body.get("learning_goal") or "").strip().lower()
    level = (body.get("cefr_level") or "").strip().lower()
    minutes = body.get("daily_goal_minutes")
    if goal not in LEARNING_GOALS:
        return json_error("Selecciona un objetivo válido.")
    if level not in CEFR_LEVELS:
        return json_error("Selecciona un nivel válido.")
    try:
        minutes = int(minutes)
        if minutes not in (5, 10, 15, 20, 30):
            raise ValueError
    except (TypeError, ValueError):
        return json_error("Selecciona una meta diaria válida.")

    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)
    try:
        client.table("profiles").update({
            "learning_goal": goal,
            "cefr_level": level,
            "daily_goal_minutes": minutes,
            "onboarded": True,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True})
    except Exception as exc:
        return json_error(_err_log("No se pudo guardar tu información", exc), 500)


@app.get("/api/uso")
def my_usage():
    """Consumo del alumno: cuántos créditos lleva en esta ventana de 5 h y hoy, y cuándo se renuevan."""
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    if is_admin_user(user):
        return jsonify({"ok": True, "ilimitado": True, "plan": "max", "plan_nombre": "Administrador"})
    plan = plan_key(_profile_access(user.id, fresh=True))
    snap = usage_snapshot(user.id, plan)
    planes = [{"id": k, "nombre": v["nombre"], "precio": v["precio"], "ventana": v["ventana"], "dia": v["dia"],
               "funciones": PLAN_FEATURES.get(k, {})} for k, v in PLANS.items()]
    return jsonify({"ok": True, **snap, "planes": planes, "ventana_horas": 5})


@app.get("/api/session")
def session_info():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return jsonify({"authenticated": False, "error": error[0]}), error[1]

    is_subscribed = False
    trial_dias_restantes = 0
    en_prueba = False
    username = None
    avatar_url = None
    onboarded = False
    cefr_level = None
    learning_goal = None
    daily_goal_minutes = None
    gems = 0
    avatar_frame = None
    client = supabase_admin or supabase
    if client:
        try:
            profile = (
                client.table("profiles")
                .select("is_subscribed,trial_ends_at,username,avatar_url,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems,avatar_frame")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            data = profile.data or {}
            is_paid = bool(data.get("is_subscribed"))
            username = data.get("username")
            avatar_url = data.get("avatar_url")
            onboarded = bool(data.get("onboarded"))
            cefr_level = data.get("cefr_level")
            learning_goal = data.get("learning_goal")
            daily_goal_minutes = data.get("daily_goal_minutes")
            gems = data.get("gems") or 0
            avatar_frame = data.get("avatar_frame")
            trial_ends_at = data.get("trial_ends_at")
            if trial_ends_at:
                try:
                    deadline = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                    remaining = deadline - datetime.now(timezone.utc)
                    if remaining.total_seconds() > 0:
                        en_prueba = True
                        trial_dias_restantes = max(1, round(remaining.total_seconds() / 86400))
                except ValueError:
                    pass
            is_subscribed = is_paid or en_prueba
        except Exception as exc:
            print(f"[SESSION PROFILE] {exc}")

    if is_admin_user(user):
        is_subscribed = True  # el administrador nunca se queda fuera de su propia app
    return jsonify({
        "authenticated": True,
        "is_subscribed": is_subscribed,
        "en_prueba": en_prueba,
        "trial_dias_restantes": trial_dias_restantes,
        "es_admin": is_admin_user(user),
        "user": {
            "id": user.id, "email": user.email, "miembro_desde": getattr(user, "created_at", None),
            "username": username, "avatar_url": avatar_url, "onboarded": onboarded,
            "cefr_level": cefr_level, "learning_goal": learning_goal, "daily_goal_minutes": daily_goal_minutes,
            "gems": gems, "avatar_frame": avatar_frame,
        },
    })


_tts_cache = OrderedDict()
_tts_lock = threading.Lock()


@app.post("/api/sintetizar-audio")
def synthesize_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return json_error("El servicio de voz no está configurado en el servidor.", 500)

    body = request.get_json(silent=True) or {}
    text = (body.get("texto") or body.get("text") or "").strip()
    if not text:
        return json_error("No hay texto para convertir a audio.")
    if len(text) > 600:
        text = text[:600]

    voice = (body.get("voz") or "en-US-AvaMultilingualNeural").strip()
    # Solo voces neuronales estándar en inglés (evita voces HD que cuestan más).
    if not re.fullmatch(r"en-[A-Z]{2}-[A-Za-z]+Neural", voice):
        voice = "en-US-AvaMultilingualNeural"

    cache_key = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()
    with _tts_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
    if cached is not None:
        return Response(cached, mimetype="audio/mpeg")

    config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    config.speech_synthesis_voice_name = voice
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detail = getattr(result, "cancellation_details", None)
        message = detail.error_details if detail else "No se pudo generar el audio."
        print(f"[TTS] {message}")
        return json_error("No se pudo generar el audio. Inténtalo de nuevo.", 500)

    audio_bytes = bytes(result.audio_data)
    if len(audio_bytes) <= 200_000:
        with _tts_lock:
            _tts_cache[cache_key] = audio_bytes
            while len(_tts_cache) > 80:
                _tts_cache.popitem(last=False)
    return Response(audio_bytes, mimetype="audio/mpeg")


_VARIETY_THEMES = ["ordering food", "the weather", "a job interview", "at the airport", "shopping for clothes", "a doctor's visit", "talking about family",
    "weekend plans", "public transport", "a hotel stay", "technology and phones", "hobbies and sports", "cooking at home", "school and studying", "making friends",
    "a phone call", "directions in a city", "health and exercise", "movies and music", "the office", "a restaurant bill", "moving to a new city", "a birthday party",
    "the news", "money and saving", "pets and animals", "travel plans", "a complaint at a store", "learning a language", "nature and the environment"]
_VARIETY_FORMS = ["a question", "a polite request", "a statement with a time word", "a sentence with 'because'", "a sentence with a contrast (but/although)",
    "a suggestion", "a sentence in the present perfect", "a sentence about the future", "a sentence with a comparison", "an opinion"]
_VARIETY_SOUNDS = ["", "", "th", "r", "v vs b", "sh and ch", "short i vs long ee", "final -ed endings", "s + consonant clusters", "w", "j (as in job)", "h", "-ing endings"]
_recent_gen = {}


def _variety(user_id, kind):
    """Elige tema/forma/sonido al azar y recuerda lo último que se generó, para que no se repita ni se parezca."""
    dq = _recent_gen.setdefault((user_id, kind), deque(maxlen=12))
    if len(_recent_gen) > 4000:
        _recent_gen.clear()
    return dq, random.choice(_VARIETY_THEMES), random.choice(_VARIETY_FORMS), random.choice(_VARIETY_SOUNDS)


def _avoid_line(dq):
    return (" Do NOT repeat or closely paraphrase any of these: " + " | ".join(dq)) if dq else ""


@app.get("/nueva-frase")
def new_phrase():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    dq, theme, form, sound = _variety(user.id, "frase")
    lvl = {"beginner": "A1-A2, simple words", "elementary": "A2", "intermediate": "B1", "advanced": "B2-C1"}.get(_profile_for_path(user.id).get("cefr_level"), "A2-B1")
    try:
        data = ai_json(
            "Create one natural English sentence for pronunciation practice. Return JSON only with exact keys: frase (the English sentence), traduccion (Spanish translation).",
            f"Theme: {theme}. Type: {form}. Level: {lvl}. " + (f"Include several words with the sound '{sound}'. " if sound else "") +
            "Between 8 and 18 words. Avoid slang and proper names." + _avoid_line(dq),
            temperature=1.0,
        )
        if data.get("frase"):
            dq.append(str(data["frase"])[:120])
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar la frase", exc), 500)


@app.get("/nuevo-tema-libre")
def new_free_topic():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    dq, theme, form, _s = _variety(user.id, "tema")
    try:
        data = ai_json(
            "Create a speaking practice topic for an English learner. Return JSON only with exact keys: tema (the topic, in English), instrucciones (short instructions in Spanish on what to talk about and for how long).",
            f"Area: {theme}. Style: {form}. Give a practical topic that encourages 45-90 seconds of speaking." + _avoid_line(dq),
            temperature=1.0,
        )
        if data.get("tema"):
            dq.append(str(data["tema"])[:120])
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el tema", exc), 500)


@app.get("/nuevo-trabalenguas")
def new_twister():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    dq, theme, _f, sound = _variety(user.id, "twister")
    sound = sound or random.choice(["th", "r", "sh and s", "v and w", "ch and j", "p and b"])
    try:
        data = ai_json(
            "Create a short English tongue twister suitable for pronunciation practice. Return JSON only with exact keys: trabalenguas (the tongue twister, in English), enfoque (short description in Spanish of which sounds it targets).",
            f"Generate one original tongue twister, 8-18 words, challenging but pronounceable, targeting the sound(s): {sound}. Loose theme: {theme}." + _avoid_line(dq),
            temperature=1.0,
        )
        if data.get("trabalenguas"):
            dq.append(str(data["trabalenguas"])[:120])
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el trabalenguas", exc), 500)


READING_LIBRARY = [
    {"id": "ny_day", "title": "A Day in New York", "level": "intermediate", "topic": "a typical day exploring New York City", "minutes": 6},
    {"id": "travel_alone", "title": "Traveling Alone", "level": "beginner", "topic": "the experience of traveling alone for the first time", "minutes": 4},
    {"id": "future_tech", "title": "The Future of Technology", "level": "advanced", "topic": "how technology might change everyday life in the future", "minutes": 8},
    {"id": "healthy_habits", "title": "Healthy Habits", "level": "intermediate", "topic": "building healthy daily habits", "minutes": 5},
    {"id": "power_of_habits", "title": "The Power of Habits", "level": "advanced", "topic": "how small habits shape our lives, in a reflective tone", "minutes": 7},
    {"id": "environment", "title": "Environment and You", "level": "intermediate", "topic": "small everyday actions that help the environment", "minutes": 5},
]


def get_reading_entry(entry_id):
    return next((x for x in READING_LIBRARY if x["id"] == entry_id), None)


@app.get("/api/reading/library")
def reading_library():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    return jsonify({"ok": True, "items": [
        {"id": x["id"], "title": x["title"], "level": x["level"], "minutes": x["minutes"]}
        for x in READING_LIBRARY
    ]})


@app.get("/api/reading/library/<entry_id>")
def reading_library_item(entry_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    entry = get_reading_entry(entry_id)
    if not entry:
        return json_error("Lectura no encontrada.", 404)
    try:
        data = ai_json(
            "Create an informational English reading passage for a learner. Return JSON only with exact keys: texto (the reading passage, in English, 180-260 words), titulo (short title), nivel (CEFR level), vocabulario (array of 5 objects with keys 'palabra' and 'significado', useful vocabulary words with brief English definitions).",
            f"Create 180-260 words about {entry['topic']}, at a {entry['level']} level. Do not include questions or Spanish translation in the passage itself.",
        )
        data["entry_id"] = entry_id
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar la lectura", exc), 500)


@app.get("/nuevo-texto-lectura")
def new_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an informational English reading passage for a learner. Return JSON only with exact keys: texto (the reading passage, in English, 180-260 words), titulo (short title), nivel (CEFR level), vocabulario (array of 5 objects with keys 'palabra' and 'significado', useful vocabulary words with brief English definitions).",
            "Create 180-260 words about a real-world topic. Do not include questions or Spanish translation in the passage itself.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar la lectura", exc), 500)


LISTENING_LIBRARY = [
    {"id": "daily_conv", "title": "Daily Conversations", "level": "beginner", "topic": "a casual daily conversation between friends"},
    {"id": "restaurant", "title": "At the Restaurant", "level": "intermediate", "topic": "ordering food at a restaurant"},
    {"id": "airport", "title": "At the Airport", "level": "intermediate", "topic": "checking in and going through security at an airport"},
    {"id": "meeting_people", "title": "Meeting New People", "level": "beginner", "topic": "introducing yourself to someone new"},
    {"id": "job_interview", "title": "Job Interview", "level": "advanced", "topic": "answering a question in a job interview"},
    {"id": "business_meeting", "title": "Business Meeting", "level": "advanced", "topic": "a short update given during a business meeting"},
]


def get_listening_entry(entry_id):
    return next((x for x in LISTENING_LIBRARY if x["id"] == entry_id), None)


@app.get("/api/listening/library")
def listening_library():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    return jsonify({"ok": True, "items": [
        {"id": x["id"], "title": x["title"], "level": x["level"]}
        for x in LISTENING_LIBRARY
    ]})


@app.get("/api/listening/library/<entry_id>")
def listening_library_item(entry_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    entry = get_listening_entry(entry_id)
    if not entry:
        return json_error("Audio no encontrado.", 404)
    try:
        data = ai_json(
            "Create an English dictation sentence for a learner. Return JSON only with exact keys: texto (the sentence, in English, 12-22 words), nivel (CEFR level).",
            f"Create one natural sentence of 12-22 words about {entry['topic']}, at a {entry['level']} level.",
        )
        data["entry_id"] = entry_id
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el audio", exc), 500)


@app.get("/nuevo-dictado")
def new_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        data = ai_json(
            "Create an English dictation sentence for an intermediate learner. Return JSON only with exact keys: texto (the sentence, in English, 12-22 words), nivel (CEFR level).",
            "Create one natural sentence of 12-22 words.",
        )
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el dictado", exc), 500)


@app.post("/analizar-audio-real")
def analyze_real_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    upload = request.files.get("audio")
    reference = (request.form.get("frase_esperada") or request.form.get("reference") or "").strip()
    mode = (request.form.get("modo") or "").strip()
    topic = (request.form.get("topic") or "").strip()
    lp_unit_code = (request.form.get("unit_code") or "").strip()
    lp_topic_id = (request.form.get("topic_id") or "").strip()
    fast = (request.form.get("fast") or "").strip() in ("1", "true")
    if not upload:
        return json_error("No se recibió audio.")
    if (request.form.get("shadow") or "") == "1" and not is_admin_user(user):
        lim = PLAN_FEATURES[_user_plan(user)]["shadowing_dia"]
        ok_s, _w = _rate_hit((user.id, "shadow"), lim, 86400)
        if not ok_s:
            return _gate(user, f"Llegaste a tus {lim} intentos de shadowing de hoy. Vuelve mañana o sube de plan.", refund=False)
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        raw_result = assess_pronunciation(wav_path, reference or None)
        payload = build_pron_payload(raw_result)
        payload["weak_sounds"] = weak_sounds_from_payload(payload)
        if payload["transcript"] and not fast:
            try:
                coach = ai_json(
                    "You are a supportive English pronunciation coach. Return concise JSON with keys 'consejos' (array of 3 short tips, in Spanish) and 'comentario' (short encouraging comment, in Spanish).",
                    f"Transcript: {payload['transcript']}\nReference: {reference}\nScores: {json.dumps(payload, ensure_ascii=False)}\nGive 3 actionable tips and a short encouraging comment, all in Spanish.",
                    temperature=0.4,
                )
                payload["coach"] = coach
            except Exception as exc:
                print(f"[AI COACH] {exc}")
            if mode == "habla_libre":
                try:
                    content = ai_json(
                        "You grade the content of unscripted spoken English. Return JSON only with exact keys: grammar_score (0-100 number), vocabulary_score (0-100 number).",
                        f"Topic: {topic}\nTranscript: {payload['transcript']}\nGrade grammar_score and vocabulary_score.",
                        temperature=0.3,
                    )
                    payload["content_assessment"] = content
                    payload["gramatica"] = content.get("grammar_score")
                    payload["vocabulario"] = content.get("vocabulary_score")
                except Exception as exc:
                    print(f"[CONTENT ASSESSMENT] {exc}")
        save_history("historial_pronunciacion", user.id, {
            "frase_esperada": reference,
            "puntuacion_global": payload["puntuacion_global"],
            "precision_fonemas": payload["precision"],
            "fluidez": payload["fluidez"],
            "completitud": payload["completitud"],
            "detalles_json": payload,
        })
        if not fast:
            award_xp(user.id, 15)
            lp_result = record_learning_progress(user.id, lp_unit_code, lp_topic_id, "pronunciation", payload["puntuacion_global"])
            if lp_result:
                payload["learning_path"] = lp_result
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        return json_error(_err_log("No se pudo analizar el audio", exc), 500)
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


@app.post("/api/assess-reading")
def assess_reading_audio():
    return analyze_real_audio()


@app.post("/api/assess-unscripted")
def assess_unscripted_audio():
    return analyze_real_audio()


WRITING_LEVEL_LABELS = {
    "easy": "A2 beginner-friendly",
    "intermediate": "B1-B2 intermediate",
    "advanced": "C1 advanced",
}


@app.get("/api/writing/challenge")
def writing_challenge():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    nivel = (request.args.get("nivel") or "intermediate").strip().lower()
    if nivel not in WRITING_LEVEL_LABELS:
        nivel = "intermediate"
    try:
        data = ai_json(
            "You create short, engaging English writing challenges/prompts for language learners. Return JSON only with exact key: prompt (one or two sentences, in English, appropriate for the requested level).",
            f"Create a writing challenge for a {WRITING_LEVEL_LABELS[nivel]} learner. Make it concrete and specific, not generic.",
        )
        return jsonify({"ok": True, "prompt": data.get("prompt"), "nivel": nivel})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el reto", exc), 500)


@app.post("/analizar-escritura")
def analyze_writing():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    text = (body.get("texto") or body.get("text") or "").strip()[:4000]
    lp_unit_code = (body.get("unit_code") or "").strip()
    lp_topic_id = (body.get("topic_id") or "").strip()
    if not text:
        return json_error("Escribe algo antes de evaluar.")
    try:
        data = ai_json(
            "You are an expert but encouraging English writing teacher. Return JSON only with exact keys: puntuacion (0-100 number), gramatica (0-100 number), vocabulario (0-100 number), coherencia (0-100 number), resumen (short summary in Spanish), correcciones (array of short strings in Spanish describing each error and its correction), version_mejorada (corrected version of the text, in English).",
            f"Analyze this learner text:\n{text}",
            temperature=0.3,
        )
        save_history("historial_escritura", user.id, {
            "texto": text,
            "calificacion": data.get("puntuacion"),
            "gramatica": data.get("gramatica"),
            "vocabulario": data.get("vocabulario"),
            "coherencia": data.get("coherencia"),
            "resumen": data.get("resumen"),
            "version_mejorada": data.get("version_mejorada"),
        })
        award_xp(user.id, 20)
        lp_result = record_learning_progress(user.id, lp_unit_code, lp_topic_id, "writing", data.get("puntuacion"))
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo evaluar el texto", exc), 500)


@app.post("/evaluar-lectura")
def evaluate_reading():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    passage = (body.get("texto_original") or body.get("passage") or "").strip()[:6000]
    answer = (body.get("respuesta") or body.get("answer") or "").strip()[:3000]
    if not passage or not answer:
        return json_error("Faltan la lectura o tu respuesta.")
    try:
        data = ai_json(
            "You evaluate English reading comprehension. Return JSON only and be constructive, with exact keys: puntuacion (0-100 overall score), idea_principal (0-100, how well the main idea was understood), detalles (0-100, how well supporting details were understood), vocabulario (0-100, vocabulary usage), claridad (0-100, clarity of the learner's English), resumen (short summary in Spanish), aciertos (array of short strings in Spanish, what was understood correctly), mejoras (array of short strings in Spanish, missed ideas or things to improve), vocabulario_sugerido (array of 3-5 objects with keys 'palabra' and 'significado', useful vocabulary from the passage).",
            f"Passage:\n{passage}\n\nLearner's explanation in English:\n{answer}",
            temperature=0.3,
        )
        data.setdefault("precision", data.get("idea_principal"))
        data.setdefault("calidad_ingles", data.get("claridad"))
        save_history("historial_lectura", user.id, {
            "titulo": passage[:80],
            "calificacion": data.get("puntuacion"),
            "idea_principal": data.get("idea_principal"),
            "detalles": data.get("detalles"),
            "vocabulario": data.get("vocabulario"),
            "claridad": data.get("claridad"),
            "respuesta": answer,
        })
        award_xp(user.id, 20)
        lp_result = record_learning_progress(
            user.id,
            (body.get("unit_code") or "").strip(),
            (body.get("topic_id") or "").strip(),
            "reading",
            data.get("puntuacion"),
        )
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo evaluar la lectura", exc), 500)


@app.post("/evaluar-dictado")
def evaluate_dictation():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    expected = (body.get("texto_original") or body.get("expected") or "").strip()[:2000]
    answer = (body.get("respuesta") or body.get("answer") or "").strip()[:2000]
    if not expected or not answer:
        return json_error("Faltan el texto esperado o tu respuesta.")
    try:
        data = ai_json(
            "You are an English dictation teacher. Return JSON only with exact keys: puntuacion (0-100 number), palabras_correctas (integer count of correctly transcribed words), diferencias (integer count of incorrect/missing words), nivel (CEFR level as a short string), feedback (short feedback in Spanish with 2-3 brief tips).",
            f"Expected sentence:\n{expected}\n\nLearner transcription:\n{answer}",
            temperature=0.2,
        )
        save_history("historial_dictado", user.id, {
            "texto_esperado": expected,
            "respuesta": answer,
            "calificacion": data.get("puntuacion"),
            "palabras_correctas": data.get("palabras_correctas"),
            "diferencias": data.get("diferencias"),
            "nivel": data.get("nivel"),
        })
        award_xp(user.id, 15)
        lp_result = record_learning_progress(
            user.id,
            (body.get("unit_code") or "").strip(),
            (body.get("topic_id") or "").strip(),
            "dictado",
            data.get("puntuacion"),
        )
        if lp_result:
            data["learning_path"] = lp_result
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo evaluar el dictado", exc), 500)


def estimate_level(user_id):
    """Estima el nivel CEFR del alumno con base en el promedio de sus calificaciones recientes."""
    client = supabase_admin or supabase
    if not client:
        return None
    scores = []
    for table, col in [
        ("historial_escritura", "calificacion"),
        ("historial_lectura", "calificacion"),
        ("historial_dictado", "calificacion"),
        ("historial_pronunciacion", "puntuacion_global"),
    ]:
        try:
            rows = (
                client.table(table)
                .select(col)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ).data or []
            scores.extend(r[col] for r in rows if r.get(col) is not None)
        except Exception as exc:
            print(f"[LEVEL:{table}] {exc}")
    if not scores:
        try:
            profile = client.table("profiles").select("cefr_level").eq("id", user_id).maybe_single().execute()
            self_level = (profile.data or {}).get("cefr_level")
            return {"beginner": "A1", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(self_level)
        except Exception as exc:
            print(f"[LEVEL:self-reported] {exc}")
            return None
    avg = sum(scores) / len(scores)
    if avg >= 90:
        return "C1-C2"
    if avg >= 75:
        return "B2"
    if avg >= 60:
        return "B1"
    if avg >= 40:
        return "A2"
    return "A1"


def recent_tutor_context(user_id, limit=6):
    """Trae un resumen breve de conversaciones anteriores con el tutor, para darle memoria entre sesiones."""
    client = supabase_admin or supabase
    if not client:
        return ""
    try:
        rows = (
            client.table("historial_tutor")
            .select("mensaje_usuario,respuesta_tutor,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data or []
    except Exception as exc:
        print(f"[TUTOR CONTEXT] {exc}")
        return ""
    if not rows:
        return ""
    rows.reverse()
    lines = [f"- Student said: \"{r['mensaje_usuario'][:150]}\" | You replied: \"{r['respuesta_tutor'][:150]}\"" for r in rows]
    return "Summary of earlier sessions with this student (for continuity, do not repeat verbatim):\n" + "\n".join(lines)


@app.post("/api/transcribir-audio")
def transcribe_audio():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    upload = request.files.get("audio")
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        config = speech_config()
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
        result = recognizer.recognize_once()
        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return jsonify({"ok": True, "texto": ""})
        return jsonify({"ok": True, "texto": result.text})
    except Exception as exc:
        return json_error(_err_log("No se pudo transcribir el audio", exc), 500)
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


# ---------------------------------------------------------------------------
# LLAMADA EN VIVO (streaming): una sola petición por turno.
#   audio del alumno -> texto -> respuesta de la IA frase por frase -> voz de cada frase
# El navegador empieza a reproducir la 1.ª frase mientras la IA todavía escribe la 2.ª.
# ---------------------------------------------------------------------------
_tts_http = requests.Session()
_tts_http.mount("https://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=16))
_VOICE_RE = re.compile(r"en-[A-Z]{2}-[A-Za-z]+Neural")
_DEFAULT_VOICE = "en-US-AvaMultilingualNeural"


def tts_bytes(text, voice=_DEFAULT_VOICE):
    """MP3 de una frase (con la misma caché que /api/sintetizar-audio). Devuelve bytes o None."""
    text = (text or "").strip()[:600]
    if not text or not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return None
    if not _VOICE_RE.fullmatch(voice or ""):
        voice = _DEFAULT_VOICE
    cache_key = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()
    with _tts_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
            return cached
    audio = None
    try:
        ssml = f"<speak version='1.0' xml:lang='en-US'><voice name='{voice}'>{_xml_escape(text)}</voice></speak>"
        r = _tts_http.post(
            f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY, "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3", "User-Agent": "talvo-english"},
            data=ssml.encode("utf-8"), timeout=15)
        if r.status_code == 200 and r.content:
            audio = r.content
        else:
            print(f"[TTS REST] {r.status_code}")
    except Exception as exc:
        print(f"[TTS REST] {exc}")
    if audio is None:  # respaldo: el SDK de siempre
        try:
            config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
            config.speech_synthesis_voice_name = voice
            config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
            result = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None).speak_text_async(text).get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio = bytes(result.audio_data)
        except Exception as exc:
            print(f"[TTS SDK] {exc}")
    if audio and len(audio) <= 200_000:
        with _tts_lock:
            _tts_cache[cache_key] = audio
            while len(_tts_cache) > 80:
                _tts_cache.popitem(last=False)
    return audio


_SENT_END = re.compile(r"[.!?…]+[\"')\]]*\s")


def _cut_sentence(buf, min_len):
    """Si en el texto ya hay una frase completa (de al menos min_len letras), devuelve (frase, resto)."""
    for m in _SENT_END.finditer(buf):
        if m.end() >= min_len:
            return buf[:m.end()].strip(), buf[m.end():]
    return None, buf


def _ndjson(obj):
    return json.dumps(obj, ensure_ascii=False) + "\n"


@app.post("/api/llamada/turno")
def call_turn():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not ai_client:
        return json_error("Azure OpenAI no está configurado en el servidor.", 500)
    upload = request.files.get("audio")
    if not upload:
        return json_error("No se recibió audio.")
    try:
        history = json.loads(request.form.get("history") or "[]")
    except Exception:
        history = []
    safe_history = []
    for item in (history if isinstance(history, list) else [])[-12:]:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            safe_history.append({"role": role, "content": content[:1500]})
    voice = (request.form.get("voz") or _DEFAULT_VOICE).strip()
    uid = user.id

    # mientras se convierte y transcribe el audio, ya vamos pidiendo el contexto del alumno
    ctx_future = _ctx_pool.submit(_tutor_context, uid)
    try:
        wav_path = convert_audio_to_wav(upload)
    except Exception as exc:
        return json_error(_err_log("No se pudo leer el audio", exc), 500)

    def generate():
        said = ""
        try:
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config(),
                                                    audio_config=speechsdk.audio.AudioConfig(filename=wav_path))
            result = recognizer.recognize_once()
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                said = (result.text or "").strip()
        except Exception as exc:
            print(f"[CALL STT] {exc}")
            yield _ndjson({"type": "error", "message": "No se pudo transcribir el audio. Inténtalo de nuevo."})
            return
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass
        if not said:
            yield _ndjson({"type": "empty"})
            return
        yield _ndjson({"type": "user", "text": said})

        try:
            level, prior = ctx_future.result(timeout=10)
        except Exception:
            level, prior = None, ""
        system_prompt = build_tutor_system_prompt(level, prior, "llamada", "")
        full, buf, pending, first = "", "", [], True

        def push(sentence):
            pending.append((sentence, _tts_pool.submit(tts_bytes, sentence, voice)))

        def drain(wait=False):
            import base64
            while pending and (wait or pending[0][1].done()):
                sentence, fut = pending.pop(0)
                try:
                    audio = fut.result(timeout=20)
                except Exception:
                    audio = None
                yield _ndjson({"type": "ai", "text": sentence,
                               "audio": base64.b64encode(audio).decode("ascii") if audio else None})

        try:
            stream = ai_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "system", "content": system_prompt}, *safe_history, {"role": "user", "content": said[:1500]}],
                temperature=0.8, stream=True, timeout=40)
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if not delta:
                    continue
                full += delta
                buf += delta
                while True:
                    sentence, rest = _cut_sentence(buf, 14 if first else 24)
                    if not sentence:
                        break
                    buf, first = rest, False
                    push(sentence)
                yield from drain()
            if buf.strip():
                push(buf.strip())
            yield from drain(wait=True)
        except Exception as exc:
            print(f"[CALL LLM stream] {exc}")
            if not full:
                # respaldo: misma petición sin streaming (por si el modelo/versión no lo admite)
                try:
                    r = ai_client.chat.completions.create(
                        model=AZURE_OPENAI_DEPLOYMENT,
                        messages=[{"role": "system", "content": system_prompt}, *safe_history, {"role": "user", "content": said[:1500]}],
                        temperature=0.8, timeout=40)
                    full = (r.choices[0].message.content or "").strip()
                    buf = full + " "
                    first = True
                    while True:
                        sentence, rest = _cut_sentence(buf, 14 if first else 24)
                        if not sentence:
                            break
                        buf, first = rest, False
                        push(sentence)
                    if buf.strip():
                        push(buf.strip())
                    yield from drain(wait=True)
                except Exception as exc2:
                    print(f"[CALL LLM fallback] {exc2}")
                if not full:
                    yield _ndjson({"type": "error", "message": "El tutor no pudo responder. Inténtalo de nuevo."})
                    return
        reply = full.strip() or "Let's keep practicing. Tell me more."
        threading.Thread(target=save_history, args=("historial_tutor", uid, {
            "mensaje_usuario": said, "respuesta_tutor": reply}), daemon=True).start()
        yield _ndjson({"type": "done", "reply": reply})

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/resumen-llamada")
def call_summary():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    history = body.get("history") or []
    transcript_lines = []
    for item in history:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            speaker = "Student" if role == "user" else "Tutor"
            transcript_lines.append(f"{speaker}: {content.strip()}")
    if not transcript_lines:
        return json_error("No hay conversación para resumir.")

    try:
        data = ai_json(
            "You are an English teacher reviewing a call-practice transcript between a student and their AI tutor. Return JSON only, in Spanish (except the numeric keys), with exact keys: puntuacion_general (0-100 overall speaking score), fluidez (0-100), gramatica (0-100), vocabulario (0-100), pronunciacion_estimada (0-100, your best estimate of likely pronunciation quality based on word choice and phrasing patterns in the transcript), resumen_general (2-3 sentences), fortalezas (array of short strings), errores_comunes (array of short strings describing recurring mistakes, in Spanish, with a brief English example each), vocabulario_recomendado (array of 3-6 objects with keys 'palabra' and 'significado'), siguiente_paso (1-2 sentences suggesting what to practice next).",
            "\n".join(transcript_lines),
            temperature=0.3,
        )
        save_history("historial_tutor", user.id, {
            "mensaje_usuario": "[Resumen de llamada]",
            "respuesta_tutor": json.dumps(data, ensure_ascii=False),
        })
        award_xp(user.id, 25)
        return jsonify({"ok": True, **data})
    except Exception as exc:
        return json_error(_err_log("No se pudo generar el resumen", exc), 500)


def notify_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5,
        )
    except Exception as exc:
        print(f"[TELEGRAM] {exc}")


@app.post("/api/soporte")
def soporte():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    tipo = (body.get("tipo") or "otro").strip()
    mensaje = (body.get("mensaje") or "").strip()
    if not mensaje:
        return json_error("Escribe tu mensaje antes de enviar.")

    save_history("soporte_mensajes", user.id, {
        "email": user.email,
        "tipo": tipo,
        "mensaje": mensaje,
    })
    notify_telegram(f"🛟 Nuevo mensaje de soporte ({tipo})\nDe: {user.email}\n\n{mensaje}")
    return jsonify({"ok": True})


# =============================================================================
# PANEL DE ADMINISTRACIÓN
# Todos los números salen de tus tablas reales. Si algo no se puede leer, el panel
# lo avisa en "warnings" en lugar de mostrar un 0 engañoso.
# =============================================================================
SERVER_STARTED = time.time()
PRICE_MXN = int(env("PRICE_MXN", "79") or 79)
try:
    LOCAL_TZ = ZoneInfo(env("APP_TIMEZONE", "America/Mexico_City"))
except Exception:
    LOCAL_TZ = timezone.utc

# (tipo, tabla, columna de calificación, columna de vista previa)
ACTIVITY_TABLES = [
    ("pronunciacion", "historial_pronunciacion", "puntuacion_global", "frase_esperada"),
    ("escritura", "historial_escritura", "calificacion", "texto"),
    ("lectura", "historial_lectura", "calificacion", "titulo"),
    ("dictado", "historial_dictado", "calificacion", "texto_esperado"),
    ("tutor", "historial_tutor", None, "mensaje_usuario"),
    ("leccion", "learning_sessions", "score", "kind"),   # Ruta de aprendizaje y Mis rutas
]
# Funciones de IA nuevas que no dejan historial propio: se leen de uso_ia (columna ruta)
_USO_TIPOS = {
    "/api/traducir": "traductor", "/api/diccionario": "diccionario", "/api/escenario/nuevo": "escenario",
    "/api/escenario/turno": "escenario", "/api/escenario/feedback": "escenario", "/api/rutas/crear": "ruta_nueva",
    "/api/reunion/analizar": "reunion", "/api/shadowing/tema": "shadowing_tema",
    "/api/clips/tema": "clip", "/api/presentacion/guion": "presentacion",
}
_USO_LABEL = {
    "/api/chat": "Tutor", "/api/traducir": "Traductor", "/api/diccionario": "Diccionario", "/api/escenario/nuevo": "Rol (nuevo)",
    "/api/escenario/turno": "Rol (turno)", "/api/llamada/turno": "Llamada (turno)", "/api/escenario/feedback": "Rol (feedback)", "/api/rutas/crear": "Crear ruta",
    "/api/reunion/analizar": "Reunión", "/api/shadowing/tema": "Shadowing (tema)", "/api/clips/tema": "Clip (tema)", "/api/presentacion/guion": "Presentación", "/analizar-audio-real": "Análisis de voz",
}
CALL_MARK = "[Resumen de llamada]"
LOG_TABLE = "admin_acciones"   # registro de cada cambio de acceso (ver admin_acciones.sql)


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _act_cols(table, score_col, prev_col):
    if table == "learning_sessions":
        return "created_at,kind,unit_code,lesson_id,score,xp,seconds"
    return "created_at," + prev_col + (f",{score_col}" if score_col else "")


def _act_norm(tipo, table, r, prev_col, score_col):
    """Convierte una fila de cualquier tabla de actividad a un evento común (o None si no cuenta)."""
    if table == "learning_sessions":
        k = str(r.get("kind") or "")
        if k in ("plan_bonus", "level_change"):
            return None
        det = " · ".join(x for x in (str(r.get("unit_code") or ""), str(r.get("lesson_id") or "")) if x) or k
        return {"tipo": "ruta" if k == "route" else ("clip" if k == "clip" else "leccion"), "detalle": det[:140], "score": _num(r.get("score")),
                "xp": int(_num(r.get("xp")) or 0), "seg": int(_num(r.get("seconds")) or 0)}
    prev = str(r.get(prev_col) or "")
    t = "llamada" if table == "historial_tutor" and prev.startswith(CALL_MARK) else tipo
    return {"tipo": t, "detalle": prev[:140], "score": _num(r.get(score_col)) if score_col else None, "xp": 0, "seg": 0}


def _fetch_uso(client, since_iso, uid=None, max_rows=20000):
    """Consumo de créditos (tabla uso_ia). Devuelve (filas, aviso)."""
    for cols in ("user_id,created_at,costo,ruta", "user_id,created_at,costo"):
        rows, start = [], 0
        try:
            while len(rows) < max_rows:
                q = client.table("uso_ia").select(cols).gte("created_at", since_iso)
                if uid:
                    q = q.eq("user_id", uid)
                data = q.order("created_at", desc=True).range(start, start + 999).execute().data or []
                rows.extend(data)
                if len(data) < 1000:
                    break
                start += 1000
            aviso = None if "ruta" in cols else "uso_ia no tiene la columna ruta: ejecuta admin_mejoras.sql para ver el consumo por función."
            return rows, aviso
        except Exception as exc:
            err = str(exc)[:100]
    return [], f"No se pudo leer uso_ia ({err}). Crea la tabla con admin_mejoras.sql."


def _parse_ts(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        s = str(v).replace("Z", "+00:00").replace(" ", "T", 1)
        s = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], s)
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _iso(dt):
    return dt.isoformat() if dt else None


def _day(dt):
    return dt.astimezone(LOCAL_TZ).date()


def admin_guard():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return None, json_error(error[0], error[1])
    if not is_admin_user(user):
        return None, json_error("No autorizado.", 403)
    return user, None


def _fetch_all(client, table, columns, order_col="created_at", max_rows=20000):
    rows, start, page = [], 0, 1000
    while len(rows) < max_rows:
        q = client.table(table).select(columns)
        if order_col:
            q = q.order(order_col, desc=True)
        data = q.range(start, start + page - 1).execute().data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return rows


def _list_auth_users(client):
    out, page = [], 1
    while page <= 30:
        batch = client.auth.admin.list_users(page=page, per_page=1000)
        items = list(batch) if isinstance(batch, (list, tuple)) else list(getattr(batch, "users", None) or [])
        out.extend(items)
        if len(items) < 1000:
            break
        page += 1
    return out


def _streak(days, today):
    if today in days:
        cur = today
    elif (today - timedelta(days=1)) in days:
        cur = today - timedelta(days=1)
    else:
        return 0
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def _build_admin_dataset():
    client = supabase_admin or supabase
    if not client:
        raise RuntimeError("Supabase no está configurado en el servidor.")
    warnings = []
    if not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == SUPABASE_KEY:
        warnings.append(
            "Falta la clave service_role (variable SUPABASE_SERVICE_KEY en Render). Sin ella Supabase oculta "
            "los datos de otros usuarios y las cifras salen incompletas."
        )
    now = datetime.now(timezone.utc)

    auth_users = {}
    try:
        for u in _list_auth_users(client):
            uid = str(getattr(u, "id", "") or "")
            if uid:
                auth_users[uid] = {
                    "email": getattr(u, "email", None) or "",
                    "created_at": _parse_ts(getattr(u, "created_at", None)),
                    "last_sign_in": _parse_ts(getattr(u, "last_sign_in_at", None)),
                    "confirmed": bool(getattr(u, "email_confirmed_at", None) or getattr(u, "confirmed_at", None)),
                }
    except Exception as exc:
        warnings.append(f"No se pudo leer la lista de cuentas de acceso ({exc}); se usan solo los perfiles.")

    profiles, ok, err = {}, False, None
    for cols in (
        "id,email,username,is_subscribed,trial_ends_at,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems",
        "id,username,is_subscribed,trial_ends_at,onboarded,cefr_level,learning_goal,daily_goal_minutes,gems",
        "id,is_subscribed,trial_ends_at",
    ):
        try:
            rows = _fetch_all(client, "profiles", cols, order_col=None)
            profiles = {str(r["id"]): r for r in rows if r.get("id")}
            ok = True
            break
        except Exception as exc:
            err = exc
    if not ok:
        warnings.append(f"No se pudo leer la tabla de perfiles ({err}). Estados de pago y prueba no disponibles.")

    events = []
    for tipo, table, score_col, prev_col in ACTIVITY_TABLES:
        cols = "user_id," + _act_cols(table, score_col, prev_col)
        try:
            rows = _fetch_all(client, table, cols)
        except Exception as exc:
            warnings.append(f"No se pudo leer {table} ({str(exc)[:90]}); la actividad de ese tipo sale incompleta.")
            continue
        for r in rows:
            ts, uid = _parse_ts(r.get("created_at")), r.get("user_id")
            if not ts or not uid:
                continue
            n = _act_norm(tipo, table, r, prev_col, score_col)
            if n:
                events.append({"uid": str(uid), "ts": ts, **n})
    uso_rows, uso_warn = _fetch_uso(client, (now - timedelta(days=30)).isoformat())
    if uso_warn:
        warnings.append(uso_warn)
    uso = []
    for r in uso_rows:
        ts, uid = _parse_ts(r.get("created_at")), r.get("user_id")
        if not ts or not uid:
            continue
        ruta = str(r.get("ruta") or "")
        c = _num(r.get("costo")) or 0
        uso.append({"uid": str(uid), "ts": ts, "ruta": ruta, "costo": c})
        t = _USO_TIPOS.get(ruta)
        if t:
            events.append({"uid": str(uid), "ts": ts, "tipo": t, "detalle": f"{_USO_LABEL.get(ruta, ruta)} · {c:g} créditos",
                           "score": None, "xp": 0, "seg": 0})
    events.sort(key=lambda e: e["ts"], reverse=True)

    vocab = defaultdict(int)
    try:
        for r in _fetch_all(client, "vocabulario_usuario", "user_id", order_col=None):
            vocab[str(r.get("user_id"))] += 1
    except Exception as exc:
        warnings.append(f"No se pudo leer vocabulario_usuario ({exc}).")

    # Registro de acciones del admin (si la tabla existe): permite saber cuándo vence cada pago.
    log_ok, ult_accion, ult_pago = True, {}, {}
    try:
        for r in _fetch_all(client, LOG_TABLE, "user_id,created_at,accion,vence_at", max_rows=5000):
            uid = str(r.get("user_id") or "")
            if uid and uid not in ult_accion:          # las filas vienen de la más reciente a la más antigua
                ult_accion[uid] = r.get("accion")
                ult_pago[uid] = _parse_ts(r.get("vence_at"))
    except Exception:
        log_ok = False

    by_user = defaultdict(list)
    for e in events:
        by_user[e["uid"]].append(e)

    today = _day(now)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    d1 = now - timedelta(days=1)
    uso_by_user = defaultdict(list)
    for x in uso:
        uso_by_user[x["uid"]].append(x)
    users = {}
    for uid in set(auth_users) | set(profiles):
        a, p = auth_users.get(uid, {}), profiles.get(uid, {})
        email = a.get("email") or p.get("email") or ""
        trial_end = _parse_ts(p.get("trial_ends_at"))
        dias = None
        if p.get("is_subscribed"):
            estado = "pagado"
        elif trial_end and trial_end > now:
            estado = "prueba"
            dias = max(1, round((trial_end - now).total_seconds() / 86400))
        else:
            estado = "vencido"
        evs = by_user.get(uid, [])
        vence_pago, dias_renovar = None, None
        if estado == "pagado" and ult_accion.get(uid) in ("activar", "renovar") and ult_pago.get(uid):
            vence_pago = ult_pago[uid]
            dias_renovar = math.ceil((vence_pago - now).total_seconds() / 86400)
        scores = [e["score"] for e in evs if e["score"] is not None]
        hoy_evs = [e for e in evs if _day(e["ts"]) == today]
        e7 = [e for e in evs if e["ts"] >= d7]
        u_uso = uso_by_user.get(uid, [])
        por_func = defaultdict(float)
        for x in u_uso:
            if x["ts"] >= d7:
                por_func[_USO_LABEL.get(x["ruta"], x["ruta"] or "Otras")] += x["costo"]
        tipos = defaultdict(int)
        for e in evs:
            tipos[e["tipo"]] += 1
        users[uid] = {
            "id": uid, "email": email, "username": p.get("username") or "",
            "es_admin": email.lower() in ADMIN_EMAILS,
            "estado": estado, "dias_restantes": dias, "trial_ends_at": trial_end,
            "created_at": a.get("created_at"), "last_sign_in": a.get("last_sign_in"),
            "confirmado": a.get("confirmed"),
            "onboarded": bool(p.get("onboarded")), "cefr_level": p.get("cefr_level") or "",
            "learning_goal": p.get("learning_goal") or "", "daily_goal_minutes": p.get("daily_goal_minutes"),
            "gems": p.get("gems") or 0,
            "total": len(evs), "act_7d": sum(1 for e in evs if e["ts"] >= d7), "act_30d": sum(1 for e in evs if e["ts"] >= d30),
            "last_activity": evs[0]["ts"] if evs else None,
            "prom_score": round(sum(scores) / len(scores), 1) if scores else None,
            "tipos": dict(tipos), "palabras": vocab.get(uid, 0),
            "racha": _streak({_day(e["ts"]) for e in evs}, today),
            "vence_pago": vence_pago, "dias_renovar": dias_renovar,
            "act_hoy": len(hoy_evs), "min_hoy": round(sum(e["seg"] for e in hoy_evs) / 60, 1),
            "min_7d": round(sum(e["seg"] for e in e7) / 60, 1), "xp_7d": sum(e["xp"] for e in e7),
            "creditos_24h": round(sum(x["costo"] for x in u_uso if x["ts"] >= d1), 2),
            "creditos_7d": round(sum(x["costo"] for x in u_uso if x["ts"] >= d7), 2),
            "por_funcion_7d": {k: round(v, 2) for k, v in sorted(por_func.items(), key=lambda kv: -kv[1])},
        }
    return {"now": now, "users": users, "events": events, "uso": uso, "warnings": warnings, "log_ok": log_ok}


_admin_cache = {"t": 0.0, "data": None}
_admin_lock = threading.Lock()


def admin_dataset(force=False):
    with _admin_lock:
        if not force and _admin_cache["data"] and time.time() - _admin_cache["t"] < 45:
            return _admin_cache["data"]
        data = _build_admin_dataset()
        _admin_cache["t"], _admin_cache["data"] = time.time(), data
        return data


def _user_json(u):
    return {
        "id": u["id"], "email": u["email"], "username": u["username"], "es_admin": u["es_admin"],
        "estado": u["estado"], "dias_restantes": u["dias_restantes"], "trial_ends_at": _iso(u["trial_ends_at"]),
        "created_at": _iso(u["created_at"]), "last_sign_in": _iso(u["last_sign_in"]), "confirmado": u["confirmado"],
        "onboarded": u["onboarded"], "cefr_level": u["cefr_level"], "learning_goal": u["learning_goal"],
        "daily_goal_minutes": u["daily_goal_minutes"], "gems": u["gems"],
        "total": u["total"], "act_7d": u["act_7d"], "act_30d": u["act_30d"],
        "last_activity": _iso(u["last_activity"]), "prom_score": u["prom_score"],
        "tipos": u["tipos"], "palabras": u["palabras"], "racha": u["racha"],
        "vence_pago": _iso(u["vence_pago"]), "dias_renovar": u["dias_renovar"],
        "act_hoy": u.get("act_hoy", 0), "min_hoy": u.get("min_hoy", 0), "min_7d": u.get("min_7d", 0), "xp_7d": u.get("xp_7d", 0),
        "creditos_24h": u.get("creditos_24h", 0), "creditos_7d": u.get("creditos_7d", 0), "por_funcion_7d": u.get("por_funcion_7d", {}),
    }


def _soporte_resumen(client, now):
    try:
        try:
            rows = client.table("soporte_mensajes").select("*").order("created_at", desc=True).limit(200).execute().data or []
        except Exception:
            rows = client.table("soporte_mensajes").select("*").limit(200).execute().data or []
    except Exception:
        return None
    sem = now - timedelta(days=7)
    rec = [r for r in rows if (_parse_ts(r.get("created_at")) or now) >= sem]
    return {
        "total_7d": len(rec),
        "pago_7d": sum(1 for r in rec if str(r.get("tipo") or "") == "pago"),
        "recientes": [{"email": r.get("email"), "tipo": r.get("tipo"), "fecha": r.get("created_at"),
                       "mensaje": str(r.get("mensaje") or "")[:140]} for r in rec[:5]],
    }


def _admin_overview(ds):
    now, events = ds["now"], ds["events"]
    users = [u for u in ds["users"].values() if not u["es_admin"]]
    ids = {u["id"] for u in users}
    events = [e for e in events if e["uid"] in ids]
    h15, d1, d7, d30 = now - timedelta(minutes=15), now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)

    def uniq(since):
        return len({e["uid"] for e in events if e["ts"] >= since})

    def nuevos(since):
        return sum(1 for u in users if u["created_at"] and u["created_at"] >= since)

    estados = {"pagado": 0, "prueba": 0, "vencido": 0}
    for u in users:
        estados[u["estado"]] += 1
    por_vencer = sorted(
        [u for u in users if u["estado"] == "prueba" and u["dias_restantes"] is not None and u["dias_restantes"] <= 3],
        key=lambda u: u["dias_restantes"],
    )
    today = _day(now)
    dias = [today - timedelta(days=i) for i in range(13, -1, -1)]
    ev_dia, us_dia, reg_dia = defaultdict(int), defaultdict(set), defaultdict(int)
    for e in events:
        if e["ts"] >= now - timedelta(days=16):
            d = _day(e["ts"])
            ev_dia[d] += 1
            us_dia[d].add(e["uid"])
    for u in users:
        if u["created_at"]:
            reg_dia[_day(u["created_at"])] += 1
    serie = [{"fecha": d.isoformat(), "eventos": ev_dia[d], "usuarios": len(us_dia[d]), "registros": reg_dia[d]} for d in dias]

    t7, t24 = defaultdict(int), defaultdict(int)
    for e in events:
        if e["ts"] >= d7:
            t7[e["tipo"]] += 1
        if e["ts"] >= d1:
            t24[e["tipo"]] += 1

    con_act = sum(1 for u in users if u["total"] > 0)
    elegibles = [u for u in users if u["created_at"] and u["created_at"] <= d7]
    retenidos = sum(1 for u in elegibles if u["act_7d"] > 0)
    niveles, objetivos = defaultdict(int), defaultdict(int)
    for u in users:
        niveles[u["cefr_level"] or "sin definir"] += 1
        objetivos[u["learning_goal"] or "sin definir"] += 1
    top = sorted([u for u in users if u["act_7d"] > 0], key=lambda u: (-u["act_7d"], -u["total"]))[:10]
    sin_act = [u for u in users if u["total"] == 0 and u["created_at"] and u["created_at"] <= now - timedelta(days=3)]

    ev_hoy = [e for e in events if _day(e["ts"]) == today]
    por_u = defaultdict(list)
    for e in ev_hoy:
        por_u[e["uid"]].append(e)
    mail = {u["id"]: u["email"] for u in users}
    lista_hoy = []
    for uid_, es in sorted(por_u.items(), key=lambda kv: -len(kv[1]))[:40]:
        tp = defaultdict(int)
        for e in es:
            tp[e["tipo"]] += 1
        lista_hoy.append({"id": uid_, "email": mail.get(uid_, uid_[:8]), "n": len(es), "tipos": dict(tp),
                          "min": round(sum(e["seg"] for e in es) / 60, 1), "xp": sum(e["xp"] for e in es),
                          "ultima": _iso(max(e["ts"] for e in es))})
    t_hoy = defaultdict(int)
    for e in ev_hoy:
        t_hoy[e["tipo"]] += 1
    uso_ok = [x for x in ds.get("uso", []) if x["uid"] in ids]
    cr_func, cr_user = defaultdict(float), defaultdict(float)
    for x in uso_ok:
        if x["ts"] >= d7:
            cr_func[_USO_LABEL.get(x["ruta"], x["ruta"] or "Otras")] += x["costo"]
        if x["ts"] >= d1:
            cr_user[x["uid"]] += x["costo"]
    por_hora = [0] * 24
    for e in ev_hoy:
        por_hora[e["ts"].astimezone(LOCAL_TZ).hour] += 1
    hoy = {"fecha": today.isoformat(), "usuarios": len(por_u), "eventos": len(ev_hoy), "minutos": round(sum(e["seg"] for e in ev_hoy) / 60, 1),
           "xp": sum(e["xp"] for e in ev_hoy), "tipos": dict(t_hoy), "lista": lista_hoy, "por_hora": por_hora,
           "nuevos": sum(1 for u in users if u["created_at"] and _day(u["created_at"]) == today)}
    creditos = {"total_24h": round(sum(x["costo"] for x in uso_ok if x["ts"] >= d1), 2), "total_7d": round(sum(x["costo"] for x in uso_ok if x["ts"] >= d7), 2),
                "por_funcion_7d": {k: round(v, 2) for k, v in sorted(cr_func.items(), key=lambda kv: -kv[1])},
                "top_24h": [{"id": k, "email": mail.get(k, k[:8]), "creditos": round(v, 2)} for k, v in sorted(cr_user.items(), key=lambda kv: -kv[1])[:8]]}
    pagados = [u for u in users if u["estado"] == "pagado"]
    por_renovar = sorted([u for u in pagados if u["dias_renovar"] is not None and u["dias_renovar"] <= 5],
                         key=lambda u: u["dias_renovar"])
    return {
        "ok": True, "generado": _iso(now), "precio_mxn": PRICE_MXN,
        "pagos": {
            "registro_activo": ds.get("log_ok", False),
            "por_renovar": [{"id": u["id"], "email": u["email"], "dias": u["dias_renovar"]} for u in por_renovar[:20]],
            "sin_fecha": sum(1 for u in pagados if u["dias_renovar"] is None),
        },
        "soporte": _soporte_resumen(supabase_admin or supabase, now),
        "usuarios": {
            "total": len(users), "confirmados": sum(1 for u in users if u["confirmado"]),
            "nuevos_24h": nuevos(d1), "nuevos_7d": nuevos(d7), "nuevos_30d": nuevos(d30),
        },
        "actividad": {
            "ahora_15min": uniq(h15), "activos_24h": uniq(d1), "activos_7d": uniq(d7), "activos_30d": uniq(d30),
            "eventos_24h": sum(t24.values()), "eventos_7d": sum(t7.values()),
        },
        "estados": estados, "mrr_estimado": estados["pagado"] * PRICE_MXN,
        "por_vencer": [{"id": u["id"], "email": u["email"], "dias": u["dias_restantes"]} for u in por_vencer[:15]],
        "embudo": [
            {"paso": "Registrados", "n": len(users)},
            {"paso": "Correo confirmado", "n": sum(1 for u in users if u["confirmado"])},
            {"paso": "Terminaron el onboarding", "n": sum(1 for u in users if u["onboarded"])},
            {"paso": "Hicieron ≥1 actividad", "n": con_act},
            {"paso": "Pagan", "n": estados["pagado"]},
        ],
        "retencion_7d": {"elegibles": len(elegibles), "retenidos": retenidos,
                         "pct": round(retenidos / len(elegibles) * 100) if elegibles else None},
        "sin_actividad_3d": len(sin_act),
        "hoy": hoy, "creditos": creditos, "zona_horaria": str(LOCAL_TZ),
        "serie_14d": serie, "tipos_7d": dict(t7), "tipos_24h": dict(t24),
        "niveles": dict(niveles), "objetivos": dict(objetivos),
        "top_7d": [{"id": u["id"], "email": u["email"], "act_7d": u["act_7d"], "total": u["total"]} for u in top],
        "warnings": ds["warnings"],
        "nota": "Las cifras no incluyen cuentas de administrador. 'Activos' = usuarios con alguna práctica registrada en esa ventana.",
    }


def _admin_users(ds, q, estado, orden, limit, offset):
    rows = list(ds["users"].values())
    q = (q or "").strip().lower()
    if q:
        rows = [u for u in rows if q in u["email"].lower() or q in (u["username"] or "").lower() or q == u["id"]]
    if estado in ("pagado", "prueba", "vencido"):
        rows = [u for u in rows if u["estado"] == estado]
    elif estado == "inactivo":
        rows = [u for u in rows if u["total"] == 0]
    elif estado == "por_renovar":
        rows = [u for u in rows if u["estado"] == "pagado" and u["dias_renovar"] is not None and u["dias_renovar"] <= 5]
    elif estado == "por_vencer":
        rows = [u for u in rows if u["estado"] == "prueba" and u["dias_restantes"] is not None and u["dias_restantes"] <= 3]
    floor = datetime.min.replace(tzinfo=timezone.utc)
    if orden == "actividad":
        rows.sort(key=lambda u: (-u["act_7d"], -u["total"]))
    elif orden == "registro":
        rows.sort(key=lambda u: u["created_at"] or floor, reverse=True)
    elif orden == "vence":
        rows.sort(key=lambda u: (u["dias_restantes"] is None, u["dias_restantes"] or 0))
    else:
        rows.sort(key=lambda u: u["last_activity"] or u["last_sign_in"] or u["created_at"] or floor, reverse=True)
    return len(rows), [_user_json(u) for u in rows[offset:offset + limit]]


def _recent_events_for(client, uid, per_table=12):
    out, warns = [], []
    for tipo, table, score_col, prev_col in ACTIVITY_TABLES:
        cols = _act_cols(table, score_col, prev_col)
        try:
            rows = client.table(table).select(cols).eq("user_id", uid).order("created_at", desc=True).limit(per_table).execute().data or []
        except Exception as exc:
            warns.append(f"{table}: {str(exc)[:80]}")
            continue
        for r in rows:
            n = _act_norm(tipo, table, r, prev_col, score_col)
            if n:
                out.append({"tipo": n["tipo"], "fecha": r.get("created_at"), "score": n["score"], "detalle": n["detalle"], "xp": n["xp"], "seg": n["seg"]})
    uso, w = _fetch_uso(client, (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(), uid=uid, max_rows=300)
    for r in uso:
        t = _USO_TIPOS.get(str(r.get("ruta") or ""))
        if t:
            out.append({"tipo": t, "fecha": r.get("created_at"), "score": None, "xp": 0, "seg": 0,
                        "detalle": f"{_USO_LABEL.get(r.get('ruta'), r.get('ruta'))} · {r.get('costo')} créditos"})
    out.sort(key=lambda e: e.get("fecha") or "", reverse=True)
    return out[:40], warns


@app.get("/api/admin/resumen")
def admin_resumen():
    _u, err = admin_guard()
    if err:
        return err
    try:
        return jsonify(_admin_overview(admin_dataset(force=request.args.get("fresh") == "1")))
    except Exception as exc:
        print(f"[ADMIN resumen] {exc}")
        return json_error(_err_log("No se pudo calcular el resumen", exc), 500)


@app.get("/api/admin/usuarios")
def admin_usuarios():
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset(force=request.args.get("fresh") == "1")
        limit = max(1, min(int(request.args.get("limit", 30) or 30), 100))
        offset = max(0, int(request.args.get("offset", 0) or 0))
        total, rows = _admin_users(ds, request.args.get("q"), request.args.get("estado", "todos"),
                                   request.args.get("orden", "reciente"), limit, offset)
        return jsonify({"ok": True, "total": total, "usuarios": rows, "warnings": ds["warnings"]})
    except Exception as exc:
        print(f"[ADMIN usuarios] {exc}")
        return json_error(_err_log("No se pudo cargar la lista de usuarios", exc), 500)


@app.get("/api/admin/usuario/<uid>")
def admin_usuario(uid):
    if not _is_uuid(uid):
        return json_error("Identificador no válido.", 400)
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset()
        u = ds["users"].get(uid)
        if not u:
            return json_error("Usuario no encontrado.", 404)
        client = supabase_admin or supabase
        recientes, warns = _recent_events_for(client, uid)
        palabras = []
        try:
            palabras = client.table("vocabulario_usuario").select("palabra,significado").eq("user_id", uid).limit(12).execute().data or []
        except Exception as exc:
            warns.append(f"vocabulario_usuario: {exc}")
        soporte = []
        if u["email"]:
            try:
                soporte = client.table("soporte_mensajes").select("*").eq("email", u["email"]).limit(10).execute().data or []
            except Exception as exc:
                warns.append(f"soporte_mensajes: {exc}")
        acciones = []
        if ds.get("log_ok"):
            try:
                acciones = (client.table(LOG_TABLE).select("created_at,accion,dias,vence_at,nota,admin_email")
                            .eq("user_id", uid).order("created_at", desc=True).limit(10).execute().data or [])
            except Exception as exc:
                warns.append(f"{LOG_TABLE}: {exc}")
        plan_u, uso_u = "gratis", None
        try:
            plan_u = plan_key(_profile_access(uid, fresh=True))
            _load_usage(uid)
            uso_u = usage_snapshot(uid, plan_u)
        except Exception as exc:
            warns.append(f"plan: {str(exc)[:80]}")
        hoy_d = _day(ds["now"])
        cnt = defaultdict(int)
        for e in ds["events"]:
            if e["uid"] == uid:
                cnt[_day(e["ts"])] += 1
        dias14 = [{"fecha": (hoy_d - timedelta(days=i)).isoformat(), "n": cnt[hoy_d - timedelta(days=i)]} for i in range(13, -1, -1)]
        return jsonify({"ok": True, "dias14": dias14, "usuario": _user_json(u), "recientes": recientes, "palabras": palabras,
                        "soporte": soporte, "acciones": acciones, "registro_activo": ds.get("log_ok", False),
                        "plan": plan_u, "uso": uso_u, "warnings": warns})
    except Exception as exc:
        print(f"[ADMIN usuario] {exc}")
        return json_error(_err_log("No se pudo cargar el usuario", exc), 500)


@app.get("/api/admin/planes")
def admin_planes_get():
    admin, err = admin_guard()
    if err:
        return err
    _load_config()
    now = time.time()
    while _global_use and now - _global_use[0][0] > 86400:
        _global_use.popleft()
    total = round(sum(c for _, c, _f in _global_use), 1)
    gratis = round(sum(c for _, c, f in _global_use if f), 1)
    users = (admin_dataset().get("users") or {}) if True else {}
    top = []
    for uid, q in list(_use.items()):
        cons = round(sum(c for t, c in q if now - t < 86400), 1)
        if cons > 0:
            top.append({"id": uid, "email": (users.get(uid) or {}).get("email") or uid[:8], "creditos": cons,
                        "plan": plan_key((_profile_cache.get(uid) or (0, {}))[1])})
    top.sort(key=lambda x: -x["creditos"])
    return jsonify({"ok": True, "config": _current_config(), "defecto": _DEFAULT_CFG,
                    "nombres": {k: v["nombre"] for k, v in PLANS.items()},
                    "guardado_permanente": _cfg_saved_ok, "ventana_horas": WINDOW_SECONDS // 3600,
                    "hoy": {"total": total, "gratis": gratis, "tope_total": GLOBAL_DAILY_CREDITS, "tope_gratis": FREE_GLOBAL_DAILY_CREDITS,
                            "pausa_gratis": gratis >= FREE_GLOBAL_DAILY_CREDITS or total >= GLOBAL_DAILY_CREDITS},
                    "top": top[:12]})


@app.post("/api/admin/planes")
def admin_planes_set():
    admin, err = admin_guard()
    if err:
        return err
    _load_config()
    body = request.get_json(silent=True) or {}
    if body.get("restaurar") is True:
        cfg = copy.deepcopy(_DEFAULT_CFG)
    else:
        cfg, bad = _validate_config(body.get("config"))
        if bad:
            return json_error(bad, 400)
    _apply_config(cfg)
    _profile_cache.clear()
    aviso = _save_config()
    try:
        notify_telegram(f"🔧 Admin {getattr(admin, 'email', '')} cambió los planes/límites.")
    except Exception:
        pass
    return jsonify({"ok": True, "mensaje": "Planes y límites actualizados.", "config": _current_config(),
                    "aviso": aviso, "guardado_permanente": _cfg_saved_ok})


@app.post("/api/admin/usuario/<uid>/acceso")
def admin_acceso(uid):
    if not _is_uuid(uid):
        return json_error("Identificador no válido.", 400)
    """Activa, renueva o quita el acceso de pago, o extiende la prueba. Siempre deja registro."""
    admin, err = admin_guard()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if body.get("confirmar") is not True:
        return json_error("Falta confirmar la acción.", 400)
    accion = (body.get("accion") or "").strip()
    if accion not in ("activar", "renovar", "desactivar", "extender_prueba", "cambiar_plan", "reiniciar_uso"):
        return json_error("Acción no válida.", 400)
    try:
        dias = int(body.get("dias") or 30)
    except (TypeError, ValueError):
        dias = 30
    dias = max(1, min(dias, 365))
    nota = str(body.get("nota") or "")[:200]
    client = supabase_admin or supabase
    if not client or not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == SUPABASE_KEY:
        return json_error("Falta la clave service_role en el servidor (SUPABASE_SERVICE_KEY): sin ella no se pueden cambiar accesos.", 500)
    try:
        res = client.table("profiles").select("id,is_subscribed,trial_ends_at").eq("id", uid).limit(1).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return json_error("Ese usuario no tiene perfil en la base de datos.", 404)
        perfil = rows[0]
        now = datetime.now(timezone.utc)
        vence, payload = None, {}
        if accion == "reiniciar_uso":
            _use[uid] = deque()
            _use_loaded.add(uid)
            try:
                client.table("uso_ia").delete().eq("user_id", uid).execute()
            except Exception as exc:
                print(f"[USO] reinicio sin tabla: {str(exc)[:100]}")
            return jsonify({"ok": True, "mensaje": "Cuota reiniciada: el alumno vuelve a tener todos sus mensajes."})
        if accion == "cambiar_plan":
            plan_nuevo = str(body.get("plan") or "").strip().lower()
            if plan_nuevo not in PLANS or plan_nuevo == "gratis":
                return json_error("Elige Básico, Pro o Max.", 400)
            if not _plan_col_ok:
                return json_error("Falta la columna profiles.plan: ejecuta planes_y_uso.sql en Supabase.", 500)
            payload = {"plan": plan_nuevo}
        elif accion in ("activar", "renovar"):
            base = now
            prev = (admin_dataset().get("users", {}).get(uid) or {}).get("vence_pago")
            if accion == "renovar" and prev and prev > now:
                base = prev                      # renovar a tiempo suma días al vencimiento actual
            vence = base + timedelta(days=dias)
            payload = {"is_subscribed": True}
            plan_nuevo = str(body.get("plan") or "").strip().lower()
            if plan_nuevo in PLANS and plan_nuevo != "gratis" and _plan_col_ok:
                payload["plan"] = plan_nuevo
        elif accion == "desactivar":
            payload = {"is_subscribed": False}
        else:
            actual = _parse_ts(perfil.get("trial_ends_at"))
            base = actual if actual and actual > now else now
            payload = {"trial_ends_at": (base + timedelta(days=dias)).isoformat()}
        upd = client.table("profiles").update(payload).eq("id", uid).execute()
        _profile_cache.pop(uid, None)
        if not (getattr(upd, "data", None) or []):
            return json_error("No se pudo actualizar el perfil (no se modificó ninguna fila).", 500)

        correo = (admin_dataset().get("users", {}).get(uid) or {}).get("email") or ""
        aviso = None
        try:
            client.table(LOG_TABLE).insert({
                "admin_email": (getattr(admin, "email", "") or "").lower(), "user_id": uid, "user_email": correo,
                "accion": accion, "dias": dias if accion in ("activar", "renovar", "extender_prueba") else None,
                "vence_at": vence.isoformat() if vence else None, "nota": nota or None,
            }).execute()
        except Exception as exc:
            aviso = ("El cambio se aplicó, pero no se pudo guardar el registro de la acción. "
                     f"Crea la tabla {LOG_TABLE} con admin_acciones.sql ({exc}).")
        try:
            notify_telegram(f"🔧 Admin {getattr(admin, 'email', '')}: {accion} → {correo or uid}"
                            + (f" ({dias} días)" if accion in ("activar", "renovar", "extender_prueba") else (f" → {payload.get('plan')}" if payload.get("plan") else "")))
        except Exception:
            pass
        ds = admin_dataset(force=True)
        u = ds["users"].get(uid)
        textos = {"cambiar_plan": f"Plan cambiado a {PLANS[payload.get('plan', 'basico')]['nombre']}.",
                  "activar": f"Acceso de pago activado por {dias} días.", "renovar": f"Pago renovado: +{dias} días.",
                  "desactivar": "Acceso de pago quitado.", "extender_prueba": f"Prueba extendida +{dias} días."}
        return jsonify({"ok": True, "mensaje": textos[accion], "usuario": _user_json(u) if u else None, "aviso": aviso})
    except Exception as exc:
        print(f"[ADMIN acceso] {exc}")
        return json_error(_err_log("No se pudo aplicar el cambio", exc), 500)


@app.get("/api/admin/actividad")
def admin_activity():
    _u, err = admin_guard()
    if err:
        return err
    try:
        ds = admin_dataset()
        client = supabase_admin or supabase
        tipo_f = (request.args.get("tipo") or "").strip()
        limit = max(10, min(int(request.args.get("limit", 100) or 100), 200))
        emails = {uid: u["email"] for uid, u in ds["users"].items()}
        events, warns = [], []
        for tipo, table, score_col, prev_col in ACTIVITY_TABLES:
            cols = "user_id," + _act_cols(table, score_col, prev_col)
            try:
                rows = client.table(table).select(cols).order("created_at", desc=True).limit(limit).execute().data or []
            except Exception as exc:
                warns.append(f"No se pudo leer {table}: {str(exc)[:90]}")
                continue
            for r in rows:
                n = _act_norm(tipo, table, r, prev_col, score_col)
                if not n or (tipo_f and n["tipo"] != tipo_f):
                    continue
                uid = str(r.get("user_id") or "")
                events.append({"tipo": n["tipo"], "uid": uid, "email": emails.get(uid) or uid[:8], "fecha": r.get("created_at"),
                               "score": n["score"], "detalle": n["detalle"], "xp": n["xp"], "seg": n["seg"]})
        for e in ds["events"]:
            if e["tipo"] in _USO_TIPOS.values() and (not tipo_f or e["tipo"] == tipo_f):
                events.append({"tipo": e["tipo"], "uid": e["uid"], "email": emails.get(e["uid"]) or e["uid"][:8], "fecha": _iso(e["ts"]),
                               "score": None, "detalle": e["detalle"], "xp": 0, "seg": 0})
        events.sort(key=lambda e: e.get("fecha") or "", reverse=True)
        ov = _admin_overview(ds)
        return jsonify({"ok": True, "eventos": events[:limit], "warnings": ds["warnings"] + warns,
                        "total_usuarios": ov["usuarios"]["total"], "en_prueba": ov["estados"]["prueba"],
                        "pagados": ov["estados"]["pagado"]})
    except Exception as exc:
        print(f"[ADMIN actividad] {exc}")
        return json_error(_err_log("No se pudo cargar la actividad", exc), 500)


@app.get("/api/admin/soporte")
def admin_soporte():
    _u, err = admin_guard()
    if err:
        return err
    client = supabase_admin or supabase
    try:
        try:
            rows = client.table("soporte_mensajes").select("*").order("created_at", desc=True).limit(50).execute().data or []
        except Exception:
            rows = client.table("soporte_mensajes").select("*").limit(50).execute().data or []
        return jsonify({"ok": True, "mensajes": rows})
    except Exception as exc:
        print(f"[ADMIN soporte] {exc}")
        return json_error(_err_log("No se pudieron leer los mensajes de soporte", exc), 500)


@app.get("/api/admin/sistema")
def admin_sistema():
    _u, err = admin_guard()
    if err:
        return err
    checks = []
    client = supabase_admin or supabase
    service_ok = bool(SUPABASE_SERVICE_KEY) and SUPABASE_SERVICE_KEY != SUPABASE_KEY
    checks.append({"nombre": "Clave service_role de Supabase", "ok": service_ok,
                   "detalle": "Configurada." if service_ok else "NO configurada: define SUPABASE_SERVICE_KEY en Render o el panel verá datos incompletos."})
    try:
        t0 = time.time()
        client.table("profiles").select("id").limit(1).execute()
        ms = round((time.time() - t0) * 1000)
        checks.append({"nombre": "Base de datos (Supabase)", "ok": True, "detalle": f"Responde en {ms} ms."})
    except Exception as exc:
        checks.append({"nombre": "Base de datos (Supabase)", "ok": False, "detalle": f"Error: {exc}"})
    try:
        client.auth.admin.list_users(page=1, per_page=1)
        checks.append({"nombre": "Lista de cuentas de acceso", "ok": True, "detalle": "Se pueden leer correos y fechas de registro."})
    except Exception as exc:
        checks.append({"nombre": "Lista de cuentas de acceso", "ok": False, "detalle": f"Error: {exc}. Se usarán los perfiles."})
    try:
        client.table(LOG_TABLE).select("id").limit(1).execute()
        checks.append({"nombre": "Registro de pagos (tabla admin_acciones)", "ok": True,
                       "detalle": "Activa: cada cambio de acceso queda guardado y se calcula cuándo vence cada pago."})
    except Exception:
        checks.append({"nombre": "Registro de pagos (tabla admin_acciones)", "ok": False,
                       "detalle": "No existe. Los botones funcionan, pero no se sabrá cuándo vence cada pago. Ejecuta admin_acciones.sql en el SQL Editor de Supabase."})
    checks.append({"nombre": "Azure OpenAI (tutor y correcciones)", "ok": bool(ai_client),
                   "detalle": "Configurado." if ai_client else "No configurado: el tutor y las evaluaciones no funcionarán."})
    checks.append({"nombre": "Azure Speech (voz y pronunciación)", "ok": bool(AZURE_SPEECH_KEY),
                   "detalle": f"Configurado (región {AZURE_SPEECH_REGION})." if AZURE_SPEECH_KEY else "No configurado."})
    checks.append({"nombre": "Cuentas de administrador", "ok": bool(ADMIN_EMAILS),
                   "detalle": f"{len(ADMIN_EMAILS)} configurada(s)."})
    checks.append({"nombre": "Avisos por Telegram (opcional)", "ok": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
                   "detalle": "Configurado." if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else "No configurado (no es obligatorio)."})
    up = int(time.time() - SERVER_STARTED)
    with _rate_lock:
        claves = len(_rate_hits)
    with _tts_lock:
        tts = len(_tts_cache)
    return jsonify({
        "ok": True, "checks": checks,
        "servidor": {
            "encendido_desde": datetime.fromtimestamp(SERVER_STARTED, timezone.utc).isoformat(),
            "uptime_seg": up, "python": platform.python_version(), "zona_horaria": str(LOCAL_TZ),
            "precio_mxn": PRICE_MXN, "planes": {k: {"precio": v["precio"], "ventana": v["ventana"], "dia": v["dia"]} for k, v in PLANS.items()}, "limite_general_min": GENERAL_PER_MINUTE,
            "audios_en_cache": tts, "contadores_de_limite": claves,
            "cache_panel_seg": int(time.time() - _admin_cache["t"]) if _admin_cache["data"] else None,
        },
    })


_ctx_cache = {}
_ctx_lock = threading.Lock()
_ctx_pool = ThreadPoolExecutor(max_workers=6)
_tts_pool = ThreadPoolExecutor(max_workers=8)


def _cached_call(key, ttl, fn, *args):
    now = time.time()
    with _ctx_lock:
        hit = _ctx_cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = fn(*args)
    with _ctx_lock:
        if len(_ctx_cache) > 3000:
            _ctx_cache.clear()
        _ctx_cache[key] = (now + ttl, value)
    return value


def _tutor_context(user_id):
    """(nivel, contexto previo) del alumno. Se piden a la vez y se guardan unos minutos:
    antes eran 5 consultas a Supabase una detrás de otra en cada mensaje."""
    f_level = _ctx_pool.submit(_cached_call, ("level", user_id), 300, estimate_level, user_id)
    f_prior = _ctx_pool.submit(_cached_call, ("prior", user_id), 120, recent_tutor_context, user_id)
    try:
        level = f_level.result(timeout=8)
    except Exception as exc:
        print(f"[LEVEL] {exc}")
        level = None
    try:
        prior = f_prior.result(timeout=8)
    except Exception as exc:
        print(f"[CONTEXT] {exc}")
        prior = ""
    return level, prior


def build_tutor_system_prompt(level, prior_context, modo="", categoria=""):
    """Prompt de Palanqueta. Lo usan el chat del tutor y la llamada en vivo."""
    level_line = f"Estimated student level: {level} (adapt vocabulary and grammar complexity to this level)." if level else "Student level unknown yet: keep it accessible (around B1) and adjust as you learn more from their messages."

    call_line = (
        "\n\nThis is a LIVE VOICE CALL, not a text chat: reply in 1-3 short spoken sentences, "
        "no lists, no markdown, no emojis — just natural words that sound good read aloud."
        if modo == "llamada" else ""
    )
    category_lines = {
        "grammar": "\n\nFocus this session on grammar: naturally work grammar points into the conversation, invite the student to build full sentences, and be a bit more explicit (but still kind) when correcting grammar patterns.",
        "vocabulary": "\n\nFocus this session on vocabulary: introduce a couple of useful new English words naturally in context each reply, and check that the student understood them.",
        "pronunciation": "\n\nFocus this session on pronunciation: ask the student to say or type short phrases, and since you cannot hear audio, give general tips on how tricky words or sounds in their message are typically pronounced.",
        "free": "\n\nThis is free-form conversation: follow the student's lead on whatever topic they bring up.",
    }
    category_line = category_lines.get(categoria, "")

    return (
        "You are Palanqueta, the friendly hen mascot and personal English conversation tutor at Talvo English. "
        "You can make a light, natural hen-themed joke or expression once in a while (e.g. comparing progress to 'hatching' a new skill), but never overdo it — you are a real tutor first, a character second. "
        "Your job is to have a real, engaging conversation in English — not to interrogate or lecture. "
        "Style: warm, encouraging, a little informal, like a good friend who happens to be a great teacher. Keep replies short (2-4 sentences), never a wall of text.\n\n"
        "How to correct mistakes: never list errors or break character to give a grammar lecture. "
        "Instead, use natural 'recasting' — if the student makes a mistake, weave the corrected form naturally into your own next sentence, the way a native speaker would casually rephrase, without pointing it out directly. "
        "Only explicitly flag a mistake if it is a significant, repeated pattern, and even then do it briefly and kindly, then move on.\n\n"
        "Conversation flow: always end your reply with one genuine follow-up question that keeps the conversation going and invites the student to speak more.\n\n"
        f"{level_line}\n\n"
        f"{prior_context}"
        f"{call_line}"
        f"{category_line}"
    )


@app.post("/api/tutor")
def tutor():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    message = (body.get("mensaje") or body.get("message") or "").strip()[:1500]
    history = body.get("history") or []
    modo = (body.get("modo") or "").strip()
    categoria = (body.get("categoria") or "").strip()
    if not message:
        return json_error("Escribe o di algo al tutor.")

    safe_history = []
    for item in history[-14:]:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and isinstance(content, str):
            safe_history.append({"role": role, "content": content[:2000]})

    level, prior_context = _tutor_context(user.id)
    system_prompt = build_tutor_system_prompt(level, prior_context, modo, categoria)

    try:
        response = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                *safe_history,
                {"role": "user", "content": message},
            ],
            temperature=0.8,
        )
        reply = response.choices[0].message.content or "Let's keep practicing. Tell me more."
        threading.Thread(target=save_history, args=("historial_tutor", user.id, {
            "mensaje_usuario": message,
            "respuesta_tutor": reply,
        }), daemon=True).start()
        return jsonify({"ok": True, "respuesta": reply})
    except Exception as exc:
        return json_error(_err_log("El tutor no pudo responder", exc), 500)


@app.get("/obtener-historial")
def history():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    tables = [
        ("pronunciation", "historial_pronunciacion"),
        ("writing", "historial_escritura"),
        ("reading", "historial_lectura"),
        ("dictation", "historial_dictado"),
        ("tutor", "historial_tutor"),
    ]
    SCORE_COLUMN = {
        "pronunciation": "puntuacion_global",
        "writing": "calificacion",
        "reading": "calificacion",
        "dictation": "calificacion",
    }
    client = supabase_admin or supabase
    combined = []
    for key, table in tables:
        try:
            rows = (
                client.table(table)
                .select("*")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            ).data or []
            score_col = SCORE_COLUMN.get(key)
            for row in rows:
                row["tipo"] = key
                if score_col and row.get(score_col) is not None:
                    row["puntuacion"] = row[score_col]
            combined.extend(rows)
        except Exception as exc:
            print(f"[HISTORY READ:{table}] {exc}")
    combined.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return jsonify({"ok": True, "historial": combined[:30]})


@app.get("/api/vocabulario/diario")
def vocab_daily():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        existing = (
            client.table("vocabulario_usuario")
            .select("id,palabra,significado,ejemplo,aprendida")
            .eq("user_id", user.id)
            .eq("origen", "diario")
            .eq("fecha", today)
            .execute()
        ).data or []
        want_more = request.args.get("mas") in ("1", "true", "si")
        if existing and not want_more:
            return jsonify({"ok": True, "palabras": existing})
        # Máximo 4 tandas de 5 palabras al día (controla el costo de IA).
        if existing and len(existing) >= 20:
            return jsonify({"ok": True, "palabras": existing, "limite": True})

        # Palabras que el alumno ya tiene: no se vuelven a ofrecer.
        known = set()
        try:
            prev = (
                client.table("vocabulario_usuario")
                .select("palabra")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(150)
                .execute()
            ).data or []
            known = {(r.get("palabra") or "").strip().lower() for r in prev if r.get("palabra")}
        except Exception as exc:
            print(f"[VOCAB KNOWN] {exc}")
        avoid = ", ".join(sorted(known)[:80])

        level = estimate_level(user.id) or "B1"
        data = ai_json(
            "You create a short daily English vocabulary list for a learner. Return JSON only with exact key: palabras, an array of exactly 6 objects each with keys 'palabra' (the English word), 'significado' (short definition in Spanish), 'ejemplo' (one example sentence in English using the word). Never repeat a word from the avoid list.",
            f"Student level: {level}. Give 6 useful, varied everyday words appropriate for this level. Avoid these words: {avoid or 'none'}.",
            temperature=0.7,
        )
        words = []
        seen_now = set(known)
        for w in data.get("palabras", []):
            key = (w.get("palabra") or "").strip().lower()
            if not key or key in seen_now:
                continue
            seen_now.add(key)
            words.append(w)
            if len(words) == 5:
                break
        inserted = []
        for w in words:
            row = {
                "user_id": user.id,
                "palabra": w.get("palabra", ""),
                "significado": w.get("significado", ""),
                "ejemplo": w.get("ejemplo", ""),
                "origen": "diario",
                "fecha": today,
            }
            try:
                res = client.table("vocabulario_usuario").insert(row).execute()
                inserted.append((res.data or [row])[0])
            except Exception as exc:
                print(f"[VOCAB INSERT] {exc}")
                inserted.append(row)
        return jsonify({"ok": True, "palabras": existing + inserted})
    except Exception as exc:
        return json_error(_err_log("No se pudieron generar las palabras del día", exc), 500)


@app.post("/api/vocabulario/guardar")
def vocab_save():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    palabra = (body.get("palabra") or "").strip()
    if not palabra:
        return json_error("Falta la palabra.")
    try:
        _c = supabase_admin or supabase
        dup = (_c.table("vocabulario_usuario").select("id").eq("user_id", user.id)
               .ilike("palabra", re.sub(r"([%_\\])", r"\\\1", palabra)).limit(1).execute()).data or []
        if dup:
            return jsonify({"ok": True, "duplicada": True})
    except Exception as exc:
        print(f"[VOCAB DUP] {exc}")
    save_history("vocabulario_usuario", user.id, {
        "palabra": palabra,
        "significado": (body.get("significado") or "").strip(),
        "ejemplo": (body.get("ejemplo") or "").strip(),
        "origen": body.get("origen") or "manual",
    })
    return jsonify({"ok": True})


@app.post("/api/vocabulario/marcar")
def vocab_mark():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    word_id = body.get("id")
    aprendida = bool(body.get("aprendida"))
    if not word_id:
        return json_error("Falta el identificador de la palabra.")
    client = supabase_admin or supabase
    try:
        client.table("vocabulario_usuario").update({"aprendida": aprendida}).eq("id", word_id).eq("user_id", user.id).execute()
        return jsonify({"ok": True})
    except Exception as exc:
        return json_error(_err_log("No se pudo actualizar", exc), 500)


def _unit_xp_and_progress(user_id):
    client = supabase_admin or supabase
    xp = 0
    gem_unlocked = set()
    if client:
        try:
            profile = client.table("profiles").select("xp").eq("id", user_id).maybe_single().execute()
            xp = (profile.data or {}).get("xp") or 0
        except Exception as exc:
            print(f"[LEARNING PATH XP] {exc}")
        try:
            rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user_id).execute().data or []
            gem_unlocked = {r["unit_code"] for r in rows}
        except Exception as exc:
            print(f"[LEARNING PATH GEM UNLOCKS] {exc}")
    return xp, fetch_learning_progress(user_id), gem_unlocked


AVATAR_FRAMES = {
    "gold": {"name": "Gold", "price": 100, "gradient": "linear-gradient(135deg,#f5c542,#ffb37a)"},
    "fire": {"name": "Fire", "price": 80, "gradient": "linear-gradient(135deg,#ff6b4a,#ff3d6e)"},
    "ocean": {"name": "Ocean", "price": 80, "gradient": "linear-gradient(135deg,#4ad0ff,#7180ff)"},
}
UNIT_UNLOCK_PRICES = {
    "at_the_restaurant": 60, "shopping_and_money": 60, "travel_and_tourism": 60, "health_and_body": 60,
    "work_and_business": 120, "social_life": 120,
    "fluent_moves": 200, "big_ideas": 200,
}
STREAK_FREEZE_PRICE = 50


def get_wallet(client, user_id):
    profile = (
        client.table("profiles")
        .select("gems,streak_freezes,avatar_frame,owned_frames")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return profile.data or {}


@app.get("/api/shop")
def shop_catalog():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    wallet = get_wallet(client, user.id)
    gems = wallet.get("gems") or 0
    owned_frames = wallet.get("owned_frames") or []

    xp = 0
    try:
        p = client.table("profiles").select("xp").eq("id", user.id).maybe_single().execute()
        xp = (p.data or {}).get("xp") or 0
    except Exception as exc:
        print(f"[SHOP XP] {exc}")

    already_unlocked = set()
    try:
        rows = client.table("gem_unit_unlocks").select("unit_code").eq("user_id", user.id).execute().data or []
        already_unlocked = {r["unit_code"] for r in rows}
    except Exception as exc:
        print(f"[SHOP UNLOCKS] {exc}")

    unit_offers = []
    try:
        prof, level_rank, _prog, gems_open, sections, _nx = _path_for_user(user.id)
        closed = next((sec for sec in sections if not sec["open"]), None)
        if closed:
            for un in closed["units"]:
                price = UNIT_UNLOCK_PRICES.get(un["code"])
                if price and un["code"] not in gems_open:
                    unit_offers.append({"unit_code": un["code"], "title": un["title"], "price": price})
    except Exception as exc:
        print(f"[SHOP OFFERS] {exc}")

    frames = [{"id": k, "name": v["name"], "price": v["price"], "gradient": v["gradient"], "owned": k in owned_frames} for k, v in AVATAR_FRAMES.items()]

    return jsonify({
        "ok": True,
        "gems": gems,
        "streak_freezes": wallet.get("streak_freezes") or 0,
        "avatar_frame": wallet.get("avatar_frame"),
        "streak_freeze_price": STREAK_FREEZE_PRICE,
        "frames": frames,
        "unit_offers": unit_offers,
    })


@app.post("/api/shop/buy")
def shop_buy():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    item = (body.get("item") or "").strip()
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    wallet = get_wallet(client, user.id)
    gems = wallet.get("gems") or 0

    if item == "streak_freeze":
        if gems < STREAK_FREEZE_PRICE:
            return json_error("No tienes suficientes gemas.")
        client.table("profiles").update({
            "gems": gems - STREAK_FREEZE_PRICE,
            "streak_freezes": (wallet.get("streak_freezes") or 0) + 1,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems - STREAK_FREEZE_PRICE})

    if item.startswith("frame:"):
        frame_id = item.split(":", 1)[1]
        frame = AVATAR_FRAMES.get(frame_id)
        if not frame:
            return json_error("Marco no encontrado.", 404)
        owned = wallet.get("owned_frames") or []
        if frame_id not in owned:
            if gems < frame["price"]:
                return json_error("No tienes suficientes gemas.")
            owned = owned + [frame_id]
            gems -= frame["price"]
        client.table("profiles").update({
            "gems": gems,
            "owned_frames": owned,
            "avatar_frame": frame_id,
        }).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems, "avatar_frame": frame_id})

    if item.startswith("unlock_unit:"):
        unit_code = item.split(":", 1)[1]
        unit = get_unit(unit_code)
        price = UNIT_UNLOCK_PRICES.get(unit_code)
        if not unit or not price:
            return json_error("Unidad no disponible para desbloquear con gemas.", 404)
        if gems < price:
            return json_error("No tienes suficientes gemas.")
        try:
            client.table("gem_unit_unlocks").insert({"user_id": user.id, "unit_code": unit_code}).execute()
        except Exception as exc:
            return json_error(_err_log("No se pudo desbloquear la unidad", exc), 500)
        client.table("profiles").update({"gems": gems - price}).eq("id", user.id).execute()
        return jsonify({"ok": True, "gems": gems - price})

    return json_error("Artículo no reconocido.")


def _clean_mistakes(raw):
    out = []
    for m in (raw or [])[:12]:
        if isinstance(m, dict):
            en = str(m.get("en") or "").strip()[:140]
            es = str(m.get("es") or "").strip()[:140]
            if en:
                out.append({"en": en, "es": es})
    return out


def _save_mistakes_as_vocab(user_id, mistakes):
    """Las palabras que fallaste pasan a tu vocabulario para repasarlas con repetición espaciada."""
    client = supabase_admin or supabase
    if not client:
        return
    for m in mistakes[:5]:
        if not m.get("es") or len(_tokens(m["en"])) > 4:
            continue
        try:
            exists = (client.table("vocabulario_usuario").select("id").eq("user_id", user_id)
                      .eq("palabra", m["en"]).limit(1).execute()).data or []
            if not exists:
                client.table("vocabulario_usuario").insert({
                    "user_id": user_id, "palabra": m["en"], "significado": m["es"], "ejemplo": "",
                    "origen": "ruta",
                }).execute()
        except Exception as exc:
            print(f"[LESSON VOCAB] {exc}")


def _path_for_user(user_id):
    prof = _profile_for_path(user_id)
    level_rank = PROFILE_LEVEL_RANK.get(prof["cefr_level"], 0)
    progress = fetch_learning_progress(user_id)
    gems = _gem_unlocks(user_id)
    sections, nxt = compute_path(progress, level_rank, prof["learning_goal"], gems)
    return prof, level_rank, progress, gems, sections, nxt


LEVEL_NAMES = ["beginner", "elementary", "intermediate", "advanced"]
LEVEL_LABEL = {"beginner": "A1 · Beginner", "elementary": "A2 · Elementary", "intermediate": "B1 · Intermediate", "advanced": "B2 · Advanced"}


def _adapt_level(user_id, level_rank):
    """Sube o baja tu nivel según tus últimas lecciones del nivel actual. Devuelve dict o None.
    Sube: 6+ lecciones de tu nivel con promedio >= 90 (y casi todas >= 80). Baja: 5+ con promedio <= 55."""
    client = supabase_admin or supabase
    if not client:
        return None
    try:
        rows = (client.table("learning_sessions").select("kind,unit_code,score,created_at").eq("user_id", user_id)
                .order("created_at", desc=True).limit(40).execute()).data or []
    except Exception as exc:
        print(f"[ADAPT] {exc}")
        return None
    recent = []
    for r in rows:                      # de la más nueva a la más vieja, hasta el último cambio de nivel
        if r.get("kind") == "level_change":
            break
        if r.get("kind") == "lesson" and r.get("score") is not None:
            u = get_unit(r.get("unit_code") or "")
            if u and LEVEL_TO_RANK.get(u["level"], 0) == level_rank:
                recent.append(float(r["score"]))
    new_rank = None
    if len(recent) >= 6 and level_rank < 3:
        last = recent[:6]
        if sum(last) / 6 >= 90 and sum(1 for x in last if x >= 80) >= 5:
            new_rank = level_rank + 1
    elif len(recent) >= 5 and level_rank > 0:
        last = recent[:5]
        if sum(last) / 5 <= 55:
            new_rank = level_rank - 1
    if new_rank is None:
        return None
    try:
        client.table("profiles").update({"cefr_level": LEVEL_NAMES[new_rank]}).eq("id", user_id).execute()
        _log_session(user_id, "level_change", LEVEL_NAMES[new_rank], None, 100, 0, 0, [], 0)
    except Exception as exc:
        print(f"[ADAPT SAVE] {exc}")
        return None
    return {"from": LEVEL_NAMES[level_rank], "to": LEVEL_NAMES[new_rank], "label": LEVEL_LABEL[LEVEL_NAMES[new_rank]],
            "direction": "up" if new_rank > level_rank else "down"}



@app.get("/api/learning-path")
def learning_path():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    prof, level_rank, progress, gems, sections, nxt = _path_for_user(user.id)
    units_flat = [u for s in sections for u in s["units"]]
    total_done = sum(s["done"] for s in sections)
    total = sum(s["total"] for s in sections)
    stars = sum(u["stars"] for u in units_flat)
    stats = phoneme_stats(user.id)
    weak = sorted([(v["avg"], k) for k, v in stats.items() if v["samples"] >= 3 and v["avg"] < 80])
    focus_ids = [k for _a, k in weak[:3]] or DEFAULT_SOUND_FOCUS[:3]
    mistakes = recent_mistakes(user.id)
    today = sessions_today(user.id)
    return jsonify({
        "ok": True, "xp": prof["xp"], "sections": sections, "units": units_flat, "next": nxt,
        "profile": {"level": prof["cefr_level"] or "beginner", "level_label": LEVEL_LABEL.get(prof["cefr_level"] or "beginner", ""), "goal": prof["learning_goal"],
                    "goal_label": GOAL_LABELS.get(prof["learning_goal"], ""),
                    "daily_minutes": prof["daily_goal_minutes"]},
        "today": {"lessons": today, "target": daily_target_lessons(prof["daily_goal_minutes"])},
        "totals": {"done": total_done, "total": total, "stars": stars,
                   "max_stars": sum(u["max_stars"] for u in units_flat)},
        "review": {"available": bool(mistakes) or total_done > 0, "mistakes": len(mistakes)},
        "sounds": {"personalized": bool(weak), "focus": [sound_info(s) for s in focus_ids]},
    })


@app.get("/api/learning-path/sounds")
def learning_path_sounds():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    stats = phoneme_stats(user.id)
    progress = fetch_learning_progress(user.id)
    items = []
    for sid, info in SOUND_LAB.items():
        st = stats.get(sid)
        avg = st["avg"] if st and st["samples"] >= 3 else None
        status = "new" if avg is None else ("weak" if avg < 75 else "ok")
        row = progress.get(("sound_lab", sid))
        items.append({"id": sid, **info, "avg": avg, "samples": st["samples"] if st else 0, "status": status,
                      "best": row.get("score") if row else None})
    personalized = any(i["status"] == "weak" for i in items)

    def sort_key(i):
        if i["status"] == "weak":
            return (0, i["avg"])
        if personalized:
            return (2 if i["status"] == "ok" else 1, 0)
        d = DEFAULT_SOUND_FOCUS.index(i["id"]) if i["id"] in DEFAULT_SOUND_FOCUS else 99
        return (1, d)
    items.sort(key=sort_key)
    return jsonify({"ok": True, "personalized": personalized, "sounds": items})


@app.get("/api/learning-path/lesson/<unit_code>/<lesson_id>")
def learning_path_lesson(unit_code, lesson_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    unit = get_unit(unit_code)
    if not unit:
        return json_error("Unidad no encontrada.", 404)
    mode = (request.args.get("mode") or "lesson").strip()
    prof, level_rank, progress, gems, sections, _nxt = _path_for_user(user.id)
    if mode == "review":
        mistakes = [m for m in recent_mistakes(user.id) if m.get("es")]
        data = build_lesson_payload(unit, "review", level_rank, mode="review", mistakes=mistakes)
    else:
        if lesson_id != "challenge" and not get_lesson(unit, lesson_id):
            return json_error("Lección no encontrada.", 404)
        lesson_state = None
        for s in sections:
            for u in s["units"]:
                if u["code"] == unit_code:
                    lesson_state = next((l for l in u["lessons"] if l["id"] == lesson_id), None)
        if not lesson_state or lesson_state["state"] == "locked":
            return json_error("Esta lección todavía está bloqueada. Completa la anterior primero.", 403)
        data = build_lesson_payload(unit, lesson_id, level_rank)
        data["replay"] = lesson_state["completed"]
        data["best_score"] = lesson_state["score"]
    data.update({"unit_code": unit_code, "unit_title": unit["title"], "icon": unit["icon"], "lesson_id": lesson_id, "mode": mode})
    if not data["exercises"]:
        return json_error("No se pudo preparar la lección.", 500)
    return jsonify({"ok": True, **data})


@app.post("/api/learning-path/review")
def learning_path_review_alias():
    return json_error("Usa /api/learning-path/lesson con mode=review.", 404)


@app.post("/api/learning-path/complete")
def learning_path_complete():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    kind = (body.get("kind") or "lesson").strip()
    if kind not in ("lesson", "review", "sound", "focus"):
        return json_error("Tipo de sesión no válido.")
    try:
        seconds = max(0, min(7200, int(body.get("seconds") or 0)))
        correct = int(body.get("correct") or 0)
        total = int(body.get("total") or 0)
    except (TypeError, ValueError):
        return json_error("Datos de la lección no válidos.")
    mistakes = _clean_mistakes(body.get("mistakes"))
    client = supabase_admin or supabase
    if not client:
        return json_error("Supabase no está configurado.", 500)

    unit_code = (body.get("unit_code") or "").strip()
    lesson_id = (body.get("lesson_id") or "").strip()
    unit = None
    if kind == "sound":
        sid = (body.get("sound_id") or "").strip()
        if sid not in SOUND_LAB:
            return json_error("Sonido no encontrado.", 404)
        try:
            score = max(0.0, min(100.0, float(body.get("score") or 0)))
        except (TypeError, ValueError):
            score = 0.0
        unit_code, lesson_id = "sound_lab", sid
    else:
        total = max(1, min(40, total))
        correct = max(0, min(total, correct))
        score = round(100 * correct / total, 1)
        if kind == "lesson":
            unit = get_unit(unit_code)
            if not unit or (lesson_id != "challenge" and not get_lesson(unit, lesson_id)):
                return json_error("Lección no encontrada.", 404)
            prof, level_rank, progress_before, gems, sections, _n = _path_for_user(user.id)
            st = None
            for s in sections:
                for u in s["units"]:
                    if u["code"] == unit_code:
                        st = next((l for l in u["lessons"] if l["id"] == lesson_id), None)
            if not st or st["state"] == "locked":
                return json_error("Esta lección todavía está bloqueada.", 403)

    passed = score >= PASS_THRESHOLD
    stars = stars_for(score)
    first_time = False
    xp = 0
    unit_bonus = 0
    unit_completed = False
    best = score
    if kind in ("lesson", "sound"):
        try:
            already, best = _upsert_progress(client, user.id, unit_code, lesson_id,
                                             "lesson" if kind == "lesson" else "sound", score, passed)
        except Exception as exc:
            print(f"[LEARNING COMPLETE SAVE] {exc}")
            return json_error("No se pudo guardar tu progreso. Inténtalo de nuevo.", 500)
        first_time = passed and not already
        if seconds >= 15 and passed:
            if kind == "lesson":
                xp = (15 + 5 * stars) if first_time else 8
            else:
                xp = 12 if first_time else 5
        if kind == "lesson" and first_time and unit:
            progress_after = fetch_learning_progress(user.id)
            unit_completed = all((unit_code, t["id"]) in progress_after for t in unit["topics"])
            if unit_completed:
                unit_bonus = 30
                xp += unit_bonus
    else:  # review / focus
        if seconds >= 15 and total >= 6:
            xp = 10
        if kind == "focus":
            unit_code, lesson_id = "focus", (lesson_id if lesson_id in FOCUS_SKILLS else "mixed")

    if xp and not _xp_allowed(user.id):
        xp = 0
    if xp:
        award_xp(user.id, xp)
    _log_session(user.id, kind, unit_code or None, lesson_id or None, score, stars, xp, mistakes, seconds)
    if kind != "sound":
        _save_mistakes_as_vocab(user.id, mistakes)

    level_change = None
    if kind == "lesson":
        try:
            level_change = _adapt_level(user.id, PROFILE_LEVEL_RANK.get(_profile_for_path(user.id).get("cefr_level"), 0))
        except Exception as exc:
            print(f"[ADAPT] {exc}")
    next_step = None
    try:
        next_step = _path_for_user(user.id)[5]
    except Exception as exc:
        print(f"[LEARNING NEXT] {exc}")
    plan_bonus = 0
    try:
        plan = _daily_plan(user.id)
        if plan["complete"] and not plan["bonus"]["claimed"]:
            award_xp(user.id, PLAN_BONUS_XP)
            _log_session(user.id, "plan_bonus", None, None, 100, 0, PLAN_BONUS_XP, [], 0)
            plan_bonus = PLAN_BONUS_XP
    except Exception as exc:
        print(f"[DAILY PLAN BONUS] {exc}")
    return jsonify({
        "ok": True, "kind": kind, "score": score, "best": best, "stars": stars, "passed": passed,
        "first_time": first_time, "xp": xp, "unit_bonus": unit_bonus, "unit_completed": unit_completed,
        "mistakes": len(mistakes), "next": next_step, "plan_bonus": plan_bonus, "level_change": level_change,
    })


# ---------------------------------------------------------------------------
#  Plan diario personalizado + práctica enfocada (se abre desde los resultados de cada herramienta)
# ---------------------------------------------------------------------------
FOCUS_SKILLS = ("speaking", "listening", "writing", "reading", "vocabulary")
FOCUS_LABELS = {"speaking": "Speaking", "listening": "Listening", "writing": "Writing",
                "reading": "Reading", "vocabulary": "Vocabulary"}
FOCUS_NOTES = {
    "speaking": "Repeat phrases you already know until they flow. Fluency comes from rhythm, not speed.",
    "listening": "Train your ear with words and phrases from your own lessons, plus the ones you missed.",
    "writing": "Build and type sentences from your own lessons. Grammar sticks when you produce it.",
    "reading": "Mixed comprehension practice using what you have learned and what you missed.",
    "vocabulary": "Recall the words that gave you trouble, in different ways, until they stick.",
}
FOCUS_RECIPES = {
    "listening": ["listen_pick", "type_listen", "listen_pick", "dialog", "type_listen", "listen_pick", "type_listen", "dialog"],
    "writing": ["build", "fill", "type_translate", "build", "fill", "type_translate", "build", "fill"],
    "reading": ["pick_meaning", "fill", "dialog", "match", "fill", "dialog", "pick_meaning", "fill"],
    "vocabulary": ["pick_word", "pick_meaning", "match", "type_translate", "listen_pick", "pick_word", "type_translate", "match"],
    "speaking": ["speak", "speak", "speak", "speak", "speak"],
}
PLAN_BONUS_XP = 15


def _skill_scores(user_id):
    client = supabase_admin or supabase
    tables = {"speaking": ("historial_pronunciacion", "puntuacion_global"),
              "listening": ("historial_dictado", "calificacion"),
              "reading": ("historial_lectura", "calificacion"),
              "writing": ("historial_escritura", "calificacion")}
    out = {}
    if not client:
        return out
    for key, (table, col) in tables.items():
        try:
            rows = (client.table(table).select(col).eq("user_id", user_id)
                    .order("created_at", desc=True).limit(10).execute()).data or []
            vals = [r[col] for r in rows if r.get(col) is not None]
            if vals:
                out[key] = round(sum(vals) / len(vals))
        except Exception as exc:
            print(f"[SKILL SCORES:{table}] {exc}")
    return out


def _weakest_skill(scores):
    if scores:
        return min(scores, key=lambda k: scores[k])
    return ["speaking", "listening", "writing", "reading"][datetime.now(timezone.utc).weekday() % 4]


def _focus_sources(user_id):
    """Lecciones que la persona ya vio (o las primeras de su nivel si aún no hay ninguna)."""
    prof, level_rank, progress, gems, sections, nxt = _path_for_user(user_id)
    done = []
    for (ucode, lid), _row in progress.items():
        u = get_unit(ucode)
        l = get_lesson(u, lid) if u else None
        if l:
            done.append((u, l))
    random.shuffle(done)
    chosen = done[:6]
    if not chosen and nxt:
        u = get_unit(nxt["unit_code"])
        chosen = [(u, l) for l in u["lessons"][:2]]
    if not chosen:
        u = LEARNING_UNITS[0]
        chosen = [(u, l) for l in u["lessons"][:2]]
    units = {}
    for u, _l in chosen:
        units[u["code"]] = u
    pseudo = {"lessons": [l for u in units.values() for l in u["lessons"]], "level": chosen[0][0]["level"]}
    return pseudo, [l for _u, l in chosen], level_rank


def build_focus(user_id, skill):
    if skill == "speaking":
        stats = phoneme_stats(user_id, limit=15)
        weak = sorted((v["avg"], k) for k, v in stats.items() if v["samples"] >= 2 and v["avg"] < 80)
        if weak:
            sid = weak[0][1]
            return {"mode": "sound", "skill": skill, "sound": sound_info(sid), "avg": weak[0][0]}
    pseudo, lessons, level_rank = _focus_sources(user_id)
    mistakes = [m for m in recent_mistakes(user_id) if m.get("es")]
    extra = [{"en": m["en"], "es": m["es"], "emoji": ""} for m in mistakes[:6]]
    rng = random.Random(time.time_ns())
    diff = level_rank - LEVEL_TO_RANK.get(pseudo["level"], 0)
    diff = -1 if diff < 0 else (1 if diff > 0 else 0)
    ex = build_exercises(pseudo, lessons, FOCUS_RECIPES[skill], rng, diff=diff, extra_words=extra)
    return {"mode": "exercises", "skill": skill, "title": "Focus: " + FOCUS_LABELS[skill], "note": FOCUS_NOTES[skill],
            "teach": [], "exercises": ex, "challenge": False, "unit_code": "focus", "lesson_id": skill,
            "from_mistakes": len(extra)}


def _today_sessions(user_id):
    client = supabase_admin or supabase
    if not client:
        return []
    try:
        start = datetime.now(timezone.utc).date().isoformat()
        return (client.table("learning_sessions").select("kind,score,xp,created_at").eq("user_id", user_id)
                .gte("created_at", start).limit(80).execute()).data or []
    except Exception:
        return []


def _daily_plan(user_id):
    prof, level_rank, progress, gems, sections, nxt = _path_for_user(user_id)
    scores = _skill_scores(user_id)
    weakest = _weakest_skill(scores)
    mistakes = recent_mistakes(user_id)
    sessions = _today_sessions(user_id)

    def did(kinds, need_pass=False):
        for r in sessions:
            if r.get("kind") in kinds and ((r.get("xp") or 0) > 0 or (r.get("score") or 0) >= PASS_THRESHOLD):
                return True
        return False

    steps = []
    if mistakes or progress:
        steps.append({"id": "warmup", "kind": "review", "icon": "🔁", "title": "Warm-up: tricky words",
                      "desc": (str(len(mistakes)) + " items to refresh") if mistakes else "Refresh what you learned",
                      "done": did(("review",))})
    sc = scores.get(weakest)
    steps.append({"id": "focus", "kind": "focus", "skill": weakest, "icon": "🎯", "title": "Focus: " + FOCUS_LABELS[weakest],
                  "desc": ("Your lowest skill lately · " + str(sc) + "%") if sc is not None else "Build this skill today",
                  "done": did(("focus", "sound"))})
    if nxt:
        steps.append({"id": "lesson", "kind": "lesson", "icon": "🚀", "title": nxt["lesson_title"],
                      "desc": nxt["unit_title"], "unit_code": nxt["unit_code"], "lesson_id": nxt["lesson_id"],
                      "done": did(("lesson",))})
    claimed = any(r.get("kind") == "plan_bonus" for r in sessions)
    complete = bool(steps) and all(s["done"] for s in steps)
    return {"steps": steps, "done": sum(1 for s in steps if s["done"]), "total": len(steps), "complete": complete,
            "bonus": {"xp": PLAN_BONUS_XP, "claimed": claimed}, "scores": scores, "weakest": weakest}


@app.get("/api/learning-path/daily-plan")
def learning_path_daily_plan():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        return jsonify({"ok": True, **_daily_plan(user.id)})
    except Exception as exc:
        print(f"[DAILY PLAN] {exc}")
        return json_error("No se pudo preparar tu plan de hoy.", 500)


@app.get("/api/learning-path/focus")
def learning_path_focus():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    skill = (request.args.get("skill") or "").strip().lower()
    if skill not in FOCUS_SKILLS:
        return json_error("Habilidad no válida.")
    try:
        data = build_focus(user.id, skill)
    except Exception as exc:
        print(f"[FOCUS] {exc}")
        return json_error("No se pudo preparar tu práctica personalizada.", 500)
    if data["mode"] == "exercises" and not data["exercises"]:
        return json_error("No se pudo preparar tu práctica personalizada.", 500)
    return jsonify({"ok": True, **data})


@app.get("/api/vocabulario")
def vocab_list():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase
    try:
        rows = (
            client.table("vocabulario_usuario")
            .select("id,palabra,significado,ejemplo,origen,aprendida,created_at")
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        ).data or []
        # Una sola entrada por palabra (la más reciente); si alguna copia está aprendida, cuenta como aprendida.
        unique, order = {}, []
        for r in rows:
            key = (r.get("palabra") or "").strip().lower()
            if not key:
                continue
            if key not in unique:
                unique[key] = dict(r)
                order.append(key)
            else:
                if r.get("aprendida"):
                    unique[key]["aprendida"] = True
                if not unique[key].get("ejemplo") and r.get("ejemplo"):
                    unique[key]["ejemplo"] = r["ejemplo"]
        rows = [unique[k] for k in order]
        learned = sum(1 for r in rows if r.get("aprendida"))
        return jsonify({"ok": True, "palabras": rows, "total": len(rows), "aprendidas": learned})
    except Exception as exc:
        return json_error(_err_log("No se pudo cargar tu vocabulario", exc), 500)


@app.get("/api/achievements")
def achievements():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase

    streak = 0
    try:
        profile = (
            client.table("profiles")
            .select("streak_days")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        streak = (profile.data or {}).get("streak_days") or 0
    except Exception as exc:
        print(f"[ACHIEVEMENTS PROFILE] {exc}")

    counts = {}
    bests = {}
    for key, (table, col) in {
        "pronunciacion": ("historial_pronunciacion", "puntuacion_global"),
        "escritura": ("historial_escritura", "calificacion"),
        "lectura": ("historial_lectura", "calificacion"),
        "dictado": ("historial_dictado", "calificacion"),
        "tutor": ("historial_tutor", None),
    }.items():
        try:
            select_cols = col if col else "id"
            rows = (
                client.table(table)
                .select(select_cols)
                .eq("user_id", user.id)
                .execute()
            ).data or []
            counts[key] = len(rows)
            if col:
                vals = [r[col] for r in rows if r.get(col) is not None]
                bests[key] = max(vals) if vals else 0
        except Exception as exc:
            print(f"[ACHIEVEMENTS:{table}] {exc}")
            counts[key] = 0
            bests[key] = 0

    total = sum(counts.get(k, 0) for k in ["pronunciacion", "escritura", "lectura", "dictado"])

    def pct(value, target):
        return min(100, round(value / target * 100)) if target else 0

    items = [
        {"code": "first_lesson", "title": "First Lesson", "icon": "🏆",
         "unlocked": total >= 1, "progress": pct(total, 1)},
        {"code": "streak_7", "title": "7 Day Streak", "icon": "🔥",
         "unlocked": streak >= 7, "progress": pct(streak, 7)},
        {"code": "streak_30", "title": "30 Day Streak", "icon": "🎯",
         "unlocked": streak >= 30, "progress": pct(streak, 30)},
        {"code": "first_conversation", "title": "First Conversation", "icon": "🗣️",
         "unlocked": counts.get("tutor", 0) >= 1, "progress": pct(counts.get("tutor", 0), 1)},
        {"code": "writing_master", "title": "Writing Master", "icon": "✍️",
         "unlocked": counts.get("escritura", 0) >= 10 or bests.get("escritura", 0) >= 90,
         "progress": max(pct(counts.get("escritura", 0), 10), pct(bests.get("escritura", 0), 90))},
        {"code": "listening_pro", "title": "Listening Pro", "icon": "🎧",
         "unlocked": counts.get("dictado", 0) >= 10, "progress": pct(counts.get("dictado", 0), 10)},
        {"code": "reading_explorer", "title": "Reading Explorer", "icon": "📖",
         "unlocked": counts.get("lectura", 0) >= 10, "progress": pct(counts.get("lectura", 0), 10)},
        {"code": "speaking_star", "title": "Speaking Star", "icon": "⭐",
         "unlocked": counts.get("pronunciacion", 0) >= 10 or bests.get("pronunciacion", 0) >= 90,
         "progress": max(pct(counts.get("pronunciacion", 0), 10), pct(bests.get("pronunciacion", 0), 90))},
    ]

    return jsonify({"ok": True, "achievements": items, "unlocked_count": sum(1 for i in items if i["unlocked"])})


@app.get("/api/dashboard")
def dashboard():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    client = supabase_admin or supabase

    xp, streak, daily_minutes = 0, 0, 10
    try:
        profile = (
            client.table("profiles")
            .select("xp,streak_days,last_activity_date,daily_goal_minutes")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        pdata = profile.data or {}
        daily_minutes = pdata.get("daily_goal_minutes") or 10
        xp = pdata.get("xp") or 0
        streak = pdata.get("streak_days") or 0
        last = pdata.get("last_activity_date")
        if last:
            last_date = datetime.fromisoformat(last).date()
            today = datetime.now(timezone.utc).date()
            if last_date < today - timedelta(days=1):
                streak = 0  # la racha se rompió, aunque el contador guardado aún no lo refleje
    except Exception as exc:
        print(f"[DASHBOARD PROFILE] {exc}")

    xp_per_level = 150
    level = xp // xp_per_level + 1
    xp_into_level = xp % xp_per_level

    skill_tables = {
        "speaking": ("historial_pronunciacion", "puntuacion_global"),
        "listening": ("historial_dictado", "calificacion"),
        "reading": ("historial_lectura", "calificacion"),
        "writing": ("historial_escritura", "calificacion"),
    }
    skills = {}
    today_count = 0
    today_str = datetime.now(timezone.utc).date().isoformat()
    for key, (table, col) in skill_tables.items():
        try:
            rows = (
                client.table(table)
                .select(f"{col},created_at")
                .eq("user_id", user.id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ).data or []
            vals = [r[col] for r in rows if r.get(col) is not None]
            skills[key] = round(sum(vals) / len(vals)) if vals else 0
            today_count += sum(1 for r in rows if (r.get("created_at") or "").startswith(today_str))
        except Exception as exc:
            print(f"[DASHBOARD:{table}] {exc}")
            skills[key] = 0

    today_count += sessions_today(user.id)  # las lecciones de la Ruta también cuentan para la meta diaria
    daily_goal_activities = max(2, daily_target_lessons(daily_minutes))
    daily_goal_pct = min(100, round(today_count / daily_goal_activities * 100))

    today_date = datetime.now(timezone.utc).date()
    week_start = today_date - timedelta(days=6)
    active_days = set()
    for table, _col in skill_tables.values():
        try:
            rows_week = (
                client.table(table)
                .select("created_at")
                .eq("user_id", user.id)
                .gte("created_at", week_start.isoformat())
                .execute()
            ).data or []
            for r in rows_week:
                ca = r.get("created_at")
                if not ca:
                    continue
                try:
                    active_days.add(datetime.fromisoformat(ca.replace("Z", "+00:00")).date().isoformat())
                except Exception:
                    pass
        except Exception as exc:
            print(f"[DASHBOARD WEEK:{table}] {exc}")
    active_days |= session_days(user.id, week_start.isoformat())
    week = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "active": d.isoformat() in active_days,
            "is_today": d == today_date,
        })

    return jsonify({
        "week": week,
        "ok": True,
        "xp": xp,
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_per_level": xp_per_level,
        "streak_days": streak,
        "skills": skills,
        "daily_goal_pct": daily_goal_pct,
        "today_activities": today_count,
    })


@app.get("/api/progreso")
def progress():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    table_map = {
        "pronunciacion": ("historial_pronunciacion", "puntuacion_global"),
        "escritura": ("historial_escritura", "calificacion"),
        "lectura": ("historial_lectura", "calificacion"),
        "dictado": ("historial_dictado", "calificacion"),
    }
    client = supabase_admin or supabase
    counts = {}
    all_rows = []
    for key, (table, score_col) in table_map.items():
        try:
            rows = (
                client.table(table)
                .select(f"created_at,{score_col}")
                .eq("user_id", user.id)
                .order("created_at", desc=False)
                .limit(50)
                .execute()
            ).data or []
            counts[key] = len(rows)
            for row in rows:
                all_rows.append({"created_at": row.get("created_at"), "score": row.get(score_col)})
        except Exception as exc:
            print(f"[PROGRESS:{table}] {exc}")
            counts[key] = 0

    all_rows.sort(key=lambda r: r.get("created_at") or "")
    scores = [r.get("score") for r in all_rows[-20:] if r.get("score") is not None]

    return jsonify({
        "ok": True,
        "total_actividades": sum(counts.values()),
        "pronunciacion": counts.get("pronunciacion", 0),
        "escritura": counts.get("escritura", 0),
        "lectura": counts.get("lectura", 0),
        "puntuaciones_recientes": scores,
    })


# ===========================================================================
#  NUEVAS FUNCIONES (Traductor en vivo · Rutas por tema · Escenarios de rol)
#  Cada una gasta créditos (ver CREDIT_COST) y tiene límites por plan (ver PLAN_FEATURES).
# ===========================================================================
import uuid as _uuid

# Qué incluye cada plan. Cambia estos números para mover una función de plan.
#   rutas          = cuántas rutas personalizadas puede tener guardadas a la vez
#   lecciones_ruta = lecciones por ruta (más lecciones = más tokens de IA al crearla)
#   escenarios     = "basicos" (los 4 marcados gratis) o "todos"
#   escenario_libre= puede inventar su propia situación de rol
#   traductor_max  = máximo de caracteres por traducción
#   shadowing_dia  = intentos de shadowing por día (cada uno usa Azure Speech, no créditos)
#   shadowing_tema = shadowing con temas propios (usa IA, 0.5 créditos) · reunion = grabar reunión (6 créditos)
PLAN_FEATURES = {
    "gratis": {"rutas": 1,  "lecciones_ruta": 3, "escenarios": "basicos", "escenario_libre": False, "traductor_max": 300, "shadowing_dia": 15, "shadowing_tema": False, "reunion": False, "clips_dia": 5, "clip_tema": False, "presentacion": False, "presentacion_slides": 0},
    "basico": {"rutas": 3,  "lecciones_ruta": 5, "escenarios": "todos",   "escenario_libre": False, "traductor_max": 600, "shadowing_dia": 60, "shadowing_tema": True, "reunion": False, "clips_dia": 15, "clip_tema": True, "presentacion": True, "presentacion_slides": 6},
    "pro":    {"rutas": 8,  "lecciones_ruta": 6, "escenarios": "todos",   "escenario_libre": True,  "traductor_max": 1000, "shadowing_dia": 200, "shadowing_tema": True, "reunion": True, "clips_dia": 40, "clip_tema": True, "presentacion": True, "presentacion_slides": 12},
    "max":    {"rutas": 20, "lecciones_ruta": 8, "escenarios": "todos",   "escenario_libre": True,  "traductor_max": 1500, "shadowing_dia": 500, "shadowing_tema": True, "reunion": True, "clips_dia": 100, "clip_tema": True, "presentacion": True, "presentacion_slides": 20},
}


def _user_plan(user):
    if is_admin_user(user):
        return "max"
    try:
        return plan_key(_profile_access(user.id))
    except Exception:
        return "gratis"


def _gate(user, message, refund=True):
    """Función de un plan superior: responde 429 con el aviso de planes (el front muestra el modal)."""
    plan = _user_plan(user)
    g.limit_info = {"tipo": "funcion", "plan": plan, "plan_nombre": PLANS[plan]["nombre"], "reinicia_seg": 0, **_limit_extra(plan)}
    try:  # no cobres créditos por algo que no se pudo usar
        if not refund:
            raise RuntimeError
        q = _use.get(user.id)
        if q:
            q.pop()
        if _global_use:
            _global_use.pop()
    except Exception:
        pass
    return json_error(message, 429)


def _short(v, n):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


# ---------------------------------------------------------------------------
#  1) TRADUCTOR EN VIVO
# ---------------------------------------------------------------------------
_TR_CACHE = OrderedDict()


@app.post("/api/traducir")
def translate_text():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    feat = PLAN_FEATURES[_user_plan(user)]
    text = _short(body.get("texto"), feat["traductor_max"] + 1)
    if not text:
        return json_error("Escribe o di algo para traducir.")
    if len(text) > feat["traductor_max"]:
        return _gate(user, f"Tu plan permite hasta {feat['traductor_max']} caracteres por traducción. Divide el texto o sube de plan.")
    src = body.get("de") if body.get("de") in ("es", "en") else "auto"
    tone = body.get("tono") if body.get("tono") in ("formal", "casual") else "neutral"
    key = (src, tone, text.lower())
    if key in _TR_CACHE:
        _TR_CACHE.move_to_end(key)
        return jsonify({"ok": True, **_TR_CACHE[key], "cache": True})
    if not ai_client:
        return json_error("La traducción no está disponible ahora mismo.", 503)
    forced = {"es": "The input is Spanish: translate to English.", "en": "The input is English: translate to Spanish."}.get(src, "Detect whether the input is Spanish or English and translate to the other one.")
    try:
        data = ai_json(
            "You are a precise Spanish<->English translator inside a language-learning app. " + forced +
            " Use natural, idiomatic phrasing (neutral Latin-American Spanish). Register: " + tone + ". Never add explanations inside the translation. "
            "Return JSON only with keys: detected ('es' or 'en'), translation (string), alternatives (array of up to 2 other natural ways to say it in the target language, [] if none), "
            "literal (word-for-word translation only if it differs a lot, else ''), note (one short tip IN SPANISH <=140 chars about nuance, false friends or register; '' if none), "
            "ipa (IPA of the English side, only when that English side is 1-3 words; else ''), "
            "examples (when the input is 1-3 words: 2 objects {en, es} using the English word in a simple sentence; else []).",
            text, temperature=0.2)
    except Exception as exc:
        print(f"[TRANSLATE] {exc}")
        return json_error("No se pudo traducir ahora. Inténtalo de nuevo.", 500)
    det = "en" if str(data.get("detected")) == "en" else "es"
    out = {
        "detected": det, "target": "es" if det == "en" else "en",
        "translation": _short(data.get("translation"), 2000),
        "alternatives": [_short(a, 400) for a in (data.get("alternatives") or [])[:2] if a],
        "literal": _short(data.get("literal"), 400), "note": _short(data.get("note"), 200),
        "ipa": _short(data.get("ipa"), 60),
        "examples": [{"en": _short(e.get("en"), 200), "es": _short(e.get("es"), 200)} for e in (data.get("examples") or [])[:2] if isinstance(e, dict) and e.get("en")],
    }
    if not out["translation"]:
        return json_error("No se pudo traducir ahora. Inténtalo de nuevo.", 500)
    _TR_CACHE[key] = out
    while len(_TR_CACHE) > 400:
        _TR_CACHE.popitem(last=False)
    return jsonify({"ok": True, **out})


# ---------------------------------------------------------------------------
#  2) ESCENARIOS DE ROL (coach con IA; voz con el navegador = costo de audio cero)
# ---------------------------------------------------------------------------
SCENARIOS = [
    # tier: "gratis" = disponible en todos los planes · "basico" = desde Básico
    {"id": "restaurant", "cat": "life", "icon": "🍽️", "tier": "gratis", "es": "En el restaurante", "desc": "Pide la comida, pregunta por el menú y pide la cuenta.",
     "setup": "A busy but friendly restaurant. The student is a customer.", "ai_role": "a friendly waiter", "user_role": "a customer", "goal": "Order a meal with a drink, ask one question about the menu and ask for the bill.",
     "opening": "Good evening! Welcome in. Can I get you something to drink while you look at the menu?"},
    {"id": "airport", "cat": "travel", "icon": "✈️", "tier": "gratis", "es": "Aeropuerto y check-in", "desc": "Documentos, equipaje y puerta de embarque.",
     "setup": "An airline check-in desk at the airport.", "ai_role": "an airline check-in agent", "user_role": "a passenger", "goal": "Check in, ask about baggage and find out the boarding gate.",
     "opening": "Good morning! May I see your passport, please? Where are you flying today?"},
    {"id": "smalltalk", "cat": "life", "icon": "💬", "tier": "gratis", "es": "Conversación casual", "desc": "Conoce a alguien nuevo y mantén una charla natural.",
     "setup": "A relaxed coffee break at a networking event.", "ai_role": "a friendly stranger named Sam", "user_role": "an attendee", "goal": "Introduce yourself, ask about their work and keep the conversation going for a few turns.",
     "opening": "Hi there! I don't think we've met. I'm Sam. What brings you to this event?"},
    {"id": "hotel", "cat": "travel", "icon": "🏨", "tier": "gratis", "es": "En el hotel", "desc": "Reserva, quejas y pedir ayuda en recepción.",
     "setup": "The front desk of a hotel.", "ai_role": "a hotel receptionist", "user_role": "a guest", "goal": "Check in, ask about breakfast and report a small problem with your room.",
     "opening": "Welcome to the Grand Plaza! Do you have a reservation with us?"},
    {"id": "sales", "cat": "work", "icon": "💼", "tier": "basico", "es": "Llamada de ventas", "desc": "Presenta tu producto y maneja objeciones.",
     "setup": "A sales call. The student sells a product to a potential client who is interested but cautious about price.", "ai_role": "a potential client who is cautious about price", "user_role": "a salesperson", "goal": "Present the product, answer an objection about price and close with a next step.",
     "opening": "Hello, this is Alex speaking. I got your email about your product. Can you tell me a bit more?"},
    {"id": "negotiation", "cat": "work", "icon": "🤝", "tier": "basico", "es": "Negociación", "desc": "Precio, plazos y condiciones: llega a un acuerdo.",
     "setup": "A business negotiation about price and delivery time for a big order.", "ai_role": "a supplier who wants a higher price and a longer deadline", "user_role": "a buyer", "goal": "Negotiate a better price or a shorter deadline and agree on the terms politely.",
     "opening": "Thanks for meeting me. For this order, our best price is 12 dollars per unit, with delivery in six weeks."},
    {"id": "interview", "cat": "work", "icon": "🧑‍💼", "tier": "basico", "es": "Entrevista de trabajo", "desc": "Preséntate, habla de tu experiencia y fortalezas.",
     "setup": "A job interview for a position the student is interested in.", "ai_role": "a hiring manager", "user_role": "a job candidate", "goal": "Introduce yourself, describe your experience, mention a strength and ask one question about the job.",
     "opening": "Hi, thanks for coming in today. Please, have a seat. Tell me a little about yourself."},
    {"id": "meeting", "cat": "work", "icon": "📊", "tier": "basico", "es": "Reunión de equipo", "desc": "Da avances, opina y propón ideas.",
     "setup": "A weekly team meeting.", "ai_role": "a team manager", "user_role": "a team member", "goal": "Give a short progress update, mention one problem and suggest a solution.",
     "opening": "Okay everyone, let's get started. Can you give us a quick update on your project?"},
    {"id": "presentation", "cat": "work", "icon": "🎤", "tier": "basico", "es": "Presentación / pitch", "desc": "Presenta una idea y responde preguntas del público.",
     "setup": "A short presentation of an idea to a small audience that asks questions.", "ai_role": "an attentive audience member who asks questions", "user_role": "the presenter", "goal": "Present your idea in a few sentences and answer two questions clearly.",
     "opening": "Welcome, everyone. Whenever you're ready, please tell us about your idea."},
    {"id": "conflict", "cat": "work", "icon": "🕊️", "tier": "basico", "es": "Manejo de conflictos", "desc": "Resuelve un desacuerdo con calma y respeto.",
     "setup": "A calm conversation to solve a disagreement about missed deadlines.", "ai_role": "a coworker who is a bit defensive", "user_role": "a coworker", "goal": "Explain the problem politely, listen and agree on a solution.",
     "opening": "Hey, you wanted to talk to me? Honestly, I've been really busy lately."},
    {"id": "date", "cat": "life", "icon": "💞", "tier": "basico", "es": "Primera cita", "desc": "Rompe el hielo y habla de gustos e intereses.",
     "setup": "A friendly first date at a café. Keep it light, respectful and PG.", "ai_role": "a friendly date named Jordan", "user_role": "a date", "goal": "Ask and answer questions about hobbies, travel and food and keep the conversation flowing.",
     "opening": "Hi! You made it. I love this place. So, tell me, what do you like to do for fun?"},
    {"id": "speech", "cat": "work", "icon": "🎙️", "tier": "basico", "es": "Oratoria", "desc": "Habla ante un público con confianza y claridad.",
     "setup": "A short speech in front of a friendly audience that reacts and asks one question at the end.", "ai_role": "an audience member and moderator", "user_role": "the speaker", "goal": "Give a clear 4-5 sentence speech with an opening, a main point and a closing, then answer one question.",
     "opening": "Good afternoon, everyone. Our next speaker is going to talk about something they care about. Whenever you are ready, the floor is yours."},
    {"id": "opic", "cat": "life", "icon": "🎓", "tier": "basico", "es": "Examen oral OPIc", "desc": "Practica preguntas al estilo OPIc con seguimiento.",
     "setup": "An OPIc-style oral proficiency interview: a personal background conversation with follow-up questions that get a bit harder.", "ai_role": "an OPIc examiner", "user_role": "the test taker", "goal": "Answer each question with detail (what, when, why) in 3-5 sentences, including a short story or example.",
     "opening": "Hello, and welcome to the interview. Let's begin. Could you please introduce yourself and tell me a little about where you live?"},
    {"id": "doctor", "cat": "life", "icon": "🩺", "tier": "basico", "es": "En el médico", "desc": "Describe síntomas y entiende las indicaciones.",
     "setup": "A doctor's appointment for a minor illness.", "ai_role": "a doctor", "user_role": "a patient", "goal": "Describe your symptoms, answer the doctor's questions and understand the advice.",
     "opening": "Hello, come in. What brings you in today? How are you feeling?"},
]
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}
_SAFE_SCENE = ("Keep the scene appropriate for a language-learning app (work or daily life). If the setup is sexual, violent, illegal or abusive, "
               "ignore it and run a neutral friendly small-talk scene instead.")


def _scenario_public(s, plan):
    feat = PLAN_FEATURES[plan]
    locked = s["tier"] != "gratis" and feat["escenarios"] != "todos"
    return {"id": s["id"], "cat": s["cat"], "icon": s["icon"], "es": s["es"], "desc": s["desc"], "goal": s["goal"],
            "opening": s["opening"], "ai_role": s["ai_role"], "user_role": s["user_role"], "bloqueado": locked}


@app.get("/api/escenarios")
def scenarios_list():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    plan = _user_plan(user)
    feat = PLAN_FEATURES[plan]
    return jsonify({"ok": True, "escenarios": [_scenario_public(s, plan) for s in SCENARIOS],
                    "libre": feat["escenario_libre"], "plan": plan, "plan_nombre": PLANS[plan]["nombre"]})


def _resolve_scenario(user, body):
    """Devuelve (escenario, error_response). Valida el plan y evita que el cliente invente permisos."""
    plan = _user_plan(user)
    feat = PLAN_FEATURES[plan]
    sid = _short(body.get("escenario_id"), 40)
    rid = _short(body.get("ruta_id"), 60)
    if sid:
        s = SCENARIO_BY_ID.get(sid)
        if not s:
            return None, json_error("Escenario no encontrado.", 404)
        if s["tier"] != "gratis" and feat["escenarios"] != "todos":
            return None, _gate(user, "Este escenario está disponible desde el plan Básico.")
        return s, None
    if rid:
        route = _route_get(user.id, rid)
        rp = (route or {}).get("roleplay") or {}
        if not route or not rp.get("setup"):
            return None, json_error("Esa ruta no tiene práctica de conversación.", 404)
        return {"id": "route", "setup": rp["setup"], "ai_role": rp.get("ai_role") or "the other person",
                "user_role": rp.get("user_role") or "the student", "goal": rp.get("goal") or "Have a natural conversation.",
                "opening": rp.get("opening") or "Hello! How can I help you?"}, None
    c = body.get("custom") if isinstance(body.get("custom"), dict) else None
    if c:
        if not feat["escenario_libre"]:
            return None, _gate(user, "Crear tus propias situaciones de rol está disponible en el plan Pro.")
        return {"id": "custom", "setup": _short(c.get("setup"), 300), "ai_role": _short(c.get("ai_role"), 120),
                "user_role": _short(c.get("user_role"), 120), "goal": _short(c.get("goal"), 240),
                "opening": _short(c.get("opening"), 300)}, None
    return None, json_error("Falta el escenario.")


def _clean_history(raw, n=14):
    out = []
    for item in (raw or [])[-n:]:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant") and isinstance(item.get("content"), str):
            out.append({"role": item["role"], "content": item["content"][:600]})
    return out


@app.post("/api/escenario/nuevo")
def scenario_custom_create():
    """Convierte lo que el alumno escribe ('quiero practicar pedir un aumento') en una situación de rol."""
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not PLAN_FEATURES[_user_plan(user)]["escenario_libre"]:
        return _gate(user, "Crear tus propias situaciones de rol está disponible en el plan Pro.")
    desc = _short((request.get_json(silent=True) or {}).get("descripcion"), 300)
    if len(desc) < 8:
        return json_error("Cuéntame un poco más de la situación (qué quieres practicar y con quién).")
    try:
        d = ai_json(
            "You design a spoken English role-play for a Spanish-speaking learner from their request. " + _SAFE_SCENE +
            " Return JSON only: {title_es (<=40 chars, Spanish), emoji, setup (1-2 sentences, English), ai_role (who the AI plays), user_role (who the student plays), "
            "goal (what the student should achieve, English, <=160 chars), opening (the AI's first spoken line, 1-2 short sentences)}.", desc, temperature=0.6)
    except Exception as exc:
        print(f"[SCENARIO NEW] {exc}")
        return json_error("No se pudo crear la situación. Inténtalo de nuevo.", 500)
    sc = {"id": "custom", "icon": _short(d.get("emoji"), 4) or "🎭", "es": _short(d.get("title_es"), 60) or "Tu situación",
          "setup": _short(d.get("setup"), 300), "ai_role": _short(d.get("ai_role"), 120), "user_role": _short(d.get("user_role"), 120),
          "goal": _short(d.get("goal"), 240), "opening": _short(d.get("opening"), 300)}
    if not sc["setup"] or not sc["opening"]:
        return json_error("No se pudo crear la situación. Inténtalo de nuevo.", 500)
    return jsonify({"ok": True, "escenario": sc})


@app.post("/api/escenario/turno")
def scenario_turn():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    sc, err = _resolve_scenario(user, body)
    if err:
        return err
    msg = _short(body.get("mensaje"), 700)
    if not msg:
        return json_error("Di o escribe algo para continuar.")
    hist = _clean_history(body.get("history"))
    lvl = (_profile_for_path(user.id).get("cefr_level") or "")
    lvl_line = {"beginner": "A1 (very simple words and short sentences)", "elementary": "A2 (simple words)", "intermediate": "B1", "advanced": "B2+"}.get(lvl, "unknown, assume A2-B1")
    system = (
        "You are role-playing a spoken English scenario to help a Spanish-speaking student practice. " + _SAFE_SCENE + "\n"
        f"Scene: {sc['setup']}\nYou play: {sc['ai_role']}.\nThe student plays: {sc['user_role']}.\nStudent's goal: {sc['goal']}\n"
        f"Student level: {lvl_line}. Match your vocabulary to it.\n"
        "Stay in character. Reply in 1-3 short, natural spoken sentences (no markdown, no emojis). Keep the scene moving with realistic details or a small challenge; do not solve the task for the student. "
        "Return JSON only with keys: reply (your in-character line), "
        "correction (null, or {said, better, why_es} when the student's LAST message has a real grammar/word-choice mistake or sounds unnatural; 'why_es' is a short reason in Spanish <=110 chars; do not correct tiny typos or punctuation), "
        "tip_es (a short Spanish hint <=110 chars about what the student could do next, or ''), "
        "suggestion_en (one example of a good next reply by the student, <=20 words), "
        "goal_reached (true only if the student has already achieved the goal and the scene can naturally end)."
    )
    try:
        resp = ai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "system", "content": system}, *hist, {"role": "user", "content": msg}],
            temperature=0.7, response_format={"type": "json_object"})
        d = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        print(f"[SCENARIO TURN] {exc}")
        return json_error("El coach no pudo responder. Inténtalo de nuevo.", 500)
    corr = d.get("correction") if isinstance(d.get("correction"), dict) else None
    if corr and not (corr.get("said") and corr.get("better")):
        corr = None
    return jsonify({"ok": True, "reply": _short(d.get("reply"), 600) or "Could you say that again, please?",
                    "correction": ({"said": _short(corr.get("said"), 300), "better": _short(corr.get("better"), 300), "why_es": _short(corr.get("why_es"), 160)} if corr else None),
                    "tip_es": _short(d.get("tip_es"), 160), "suggestion_en": _short(d.get("suggestion_en"), 200),
                    "goal_reached": bool(d.get("goal_reached"))})


@app.post("/api/escenario/feedback")
def scenario_feedback():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    sc, err = _resolve_scenario(user, body)
    if err:
        return err
    hist = _clean_history(body.get("history"), 24)
    lines = [("Student: " if m["role"] == "user" else "Partner: ") + m["content"] for m in hist]
    if sum(1 for m in hist if m["role"] == "user") < 2:
        return json_error("Conversa un poco más (al menos 2 respuestas tuyas) para poder evaluarte.")
    try:
        d = ai_json(
            "You are an English coach reviewing a role-play conversation. Scene: " + sc["setup"] + " The student's goal: " + sc["goal"] + ". "
            "Judge ONLY the student's lines. Return JSON only, in Spanish unless a key says English, with keys: "
            "puntuacion (0-100 overall), fluidez (0-100), gramatica (0-100), vocabulario (0-100), objetivo_logrado (true/false), "
            "resumen (2 sentences), fortalezas (array of up to 3 short strings), "
            "mejoras (array of up to 4 objects {dijiste (English, what the student said), mejor (English, a better way), por_que (Spanish, <=100 chars)}), "
            "frases_utiles (array of 4 objects {en, es}: ready-to-use English phrases for this situation), siguiente_paso (1 sentence).",
            "\n".join(lines), temperature=0.3)
    except Exception as exc:
        print(f"[SCENARIO FEEDBACK] {exc}")
        return json_error("No se pudo generar tu evaluación.", 500)

    def n100(v):
        try:
            return max(0, min(100, int(float(v))))
        except (TypeError, ValueError):
            return 0
    out = {
        "puntuacion": n100(d.get("puntuacion")), "fluidez": n100(d.get("fluidez")), "gramatica": n100(d.get("gramatica")), "vocabulario": n100(d.get("vocabulario")),
        "objetivo_logrado": bool(d.get("objetivo_logrado")), "resumen": _short(d.get("resumen"), 400),
        "fortalezas": [_short(x, 160) for x in (d.get("fortalezas") or [])[:3]],
        "mejoras": [{"dijiste": _short(m.get("dijiste"), 240), "mejor": _short(m.get("mejor"), 240), "por_que": _short(m.get("por_que"), 160)}
                    for m in (d.get("mejoras") or [])[:4] if isinstance(m, dict)],
        "frases_utiles": [{"en": _short(m.get("en"), 200), "es": _short(m.get("es"), 200)} for m in (d.get("frases_utiles") or [])[:4] if isinstance(m, dict) and m.get("en")],
        "siguiente_paso": _short(d.get("siguiente_paso"), 240),
    }
    xp = 20 if out["puntuacion"] >= 50 else 10
    award_xp(user.id, xp)
    save_history("historial_tutor", user.id, {"mensaje_usuario": f"[Escenario: {sc.get('id')}]", "respuesta_tutor": json.dumps(out, ensure_ascii=False)})
    return jsonify({"ok": True, "xp": xp, **out})


# ---------------------------------------------------------------------------
#  3) CREA TU RUTA: de "vendo quesos y quiero vender en inglés" a un curso a tu medida
# ---------------------------------------------------------------------------
ROUTE_EXAMPLES = [
    "Vendo quesos artesanales y quiero tener una conversación de venta en inglés",
    "Voy a viajar a Canadá y necesito defenderme en el aeropuerto y el hotel",
    "Tengo una entrevista de trabajo en una empresa de tecnología",
    "Soy mesero y quiero atender a turistas en inglés",
    "Quiero platicar con mi pareja que habla inglés",
]


def _route_get(user_id, route_id):
    if not _is_uuid(route_id):
        return None
    client = supabase_admin or supabase
    try:
        rows = (client.table("rutas_personalizadas").select("*").eq("id", route_id).eq("user_id", user_id).limit(1).execute()).data or []
        return rows[0] if rows else None
    except Exception as exc:
        print(f"[ROUTE GET] {exc}")
        return None


def _route_unit(route):
    lessons = route.get("lecciones") or []
    return {"code": "route_" + str(route.get("id"))[:8], "level": route.get("nivel") or "A1", "title": route.get("titulo") or "Mi ruta",
            "icon": route.get("emoji") or "🎯", "lessons": lessons}


def _route_states(route):
    lessons = route.get("lecciones") or []
    prog = route.get("progreso") or {}
    out, prev_ok = [], True
    for i, l in enumerate(lessons):
        row = prog.get(l["id"]) or {}
        done = bool(row.get("passed"))
        out.append({"id": l["id"], "title": l["title"], "n": i + 1, "challenge": False, "state": "done" if done else ("available" if prev_ok else "locked"),
                    "score": row.get("score"), "stars": row.get("stars", 0)})
        prev_ok = prev_ok and done
    row = prog.get("challenge") or {}
    done = bool(row.get("passed"))
    out.append({"id": "challenge", "title": "Reto final", "n": len(lessons) + 1, "challenge": True, "state": "done" if done else ("available" if prev_ok else "locked"),
                "score": row.get("score"), "stars": row.get("stars", 0)})
    return out


def _route_summary(route):
    st = _route_states(route)
    return {"id": route["id"], "titulo": route.get("titulo"), "emoji": route.get("emoji") or "🎯", "nivel": route.get("nivel"),
            "pedido": route.get("pedido"), "resumen": route.get("resumen") or "", "lecciones": len(st), "completadas": sum(1 for s in st if s["state"] == "done"),
            "estrellas": sum(int(s.get("stars") or 0) for s in st), "roleplay": bool((route.get("roleplay") or {}).get("setup")),
            "creada": route.get("created_at")}


def _clean_route(raw, n):
    """Valida lo que devolvió la IA y lo deja en el mismo formato que el currículo normal."""
    if not isinstance(raw, dict):
        return None
    lessons = []
    seen = set()
    for i, l in enumerate((raw.get("lessons") or [])[:n]):
        if not isinstance(l, dict):
            continue
        words, phrases, dialogs = [], [], []
        for w in (l.get("words") or [])[:10]:
            if isinstance(w, dict) and w.get("en") and w.get("es"):
                en = _short(w["en"], 40)
                if en.lower() not in seen:
                    seen.add(en.lower())
                    words.append({"en": en, "es": _short(w["es"], 50), "emoji": _short(w.get("emoji"), 4)})
        for p in (l.get("phrases") or [])[:8]:
            if isinstance(p, dict) and p.get("en") and p.get("es") and len(str(p["en"]).split()) <= 16:
                phrases.append({"en": _short(p["en"], 120), "es": _short(p["es"], 140)})
        for d in (l.get("dialogs") or [])[:5]:
            if isinstance(d, dict) and d.get("q") and d.get("a"):
                wrong = [_short(x, 120) for x in (d.get("wrong") or []) if x and _short(x, 120).lower() != _short(d["a"], 120).lower()][:2]
                if len(wrong) == 2:
                    dialogs.append({"q": _short(d["q"], 140), "a": _short(d["a"], 120), "wrong": wrong})
        if len(words) >= 5 and len(phrases) >= 3 and len(dialogs) >= 1:
            lessons.append({"id": f"l{len(lessons) + 1}", "title": _short(l.get("title"), 40) or f"Lesson {len(lessons) + 1}",
                            "note": _short(l.get("note_es") or l.get("note"), 220), "words": words, "phrases": phrases, "dialogs": dialogs})
    if len(lessons) < 2:
        return None
    lvl = str(raw.get("level") or "A1").upper()
    rp = raw.get("roleplay") if isinstance(raw.get("roleplay"), dict) else {}
    roleplay = {}
    if rp.get("setup") and rp.get("opening"):
        roleplay = {k: _short(rp.get(k), 300) for k in ("setup", "ai_role", "user_role", "goal", "opening")}
    return {"titulo": _short(raw.get("title"), 60) or "Mi ruta", "emoji": _short(raw.get("emoji"), 4) or "🎯",
            "nivel": lvl if lvl in ("A1", "A2", "B1", "B2") else "A2", "resumen": _short(raw.get("summary_es"), 200),
            "lecciones": lessons, "roleplay": roleplay}


@app.get("/api/rutas")
def routes_list():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    plan = _user_plan(user)
    feat = PLAN_FEATURES[plan]
    client = supabase_admin or supabase
    try:
        rows = (client.table("rutas_personalizadas").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(50).execute()).data or []
    except Exception as exc:
        print(f"[ROUTES LIST] {exc}")
        return json_error("Falta crear la tabla de rutas: ejecuta nuevas_funciones.sql en Supabase.", 500)
    return jsonify({"ok": True, "rutas": [_route_summary(r) for r in rows], "maximo": feat["rutas"], "puede_crear": len(rows) < feat["rutas"],
                    "max_lecciones": feat["lecciones_ruta"], "plan": plan, "plan_nombre": PLANS[plan]["nombre"], "ejemplos": ROUTE_EXAMPLES})


@app.post("/api/rutas/crear")
def route_create():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    pedido = _short(body.get("pedido"), 400)
    if len(pedido) < 12:
        return json_error("Cuéntame un poco más: ¿qué quieres lograr en inglés y en qué situación?")
    plan = _user_plan(user)
    feat = PLAN_FEATURES[plan]
    client = supabase_admin or supabase
    try:
        existing = (client.table("rutas_personalizadas").select("id").eq("user_id", user.id).limit(100).execute()).data or []
    except Exception as exc:
        print(f"[ROUTE CREATE CHECK] {exc}")
        return json_error("Falta crear la tabla de rutas: ejecuta nuevas_funciones.sql en Supabase.", 500)
    if len(existing) >= feat["rutas"]:
        return _gate(user, f"Tu plan {PLANS[plan]['nombre']} permite {feat['rutas']} ruta(s) guardada(s). Elimina una o sube de plan para crear más.")
    if not ai_client:
        return json_error("La creación de rutas no está disponible ahora mismo.", 503)
    n = max(2, min(feat["lecciones_ruta"], int(body.get("lecciones") or feat["lecciones_ruta"]) if str(body.get("lecciones") or "").isdigit() else feat["lecciones_ruta"]))
    prof = _profile_for_path(user.id)
    lvl = {"beginner": "A1", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(prof.get("cefr_level"), "")
    asked = body.get("nivel") if body.get("nivel") in ("A1", "A2", "B1", "B2") else ""
    level = asked or lvl or "A2"
    def _route_system(count, first, last, part, parts):
        extra = ""
        if parts > 1:
            extra = (f"This is PART {part} of {parts} of a course with {n} lessons in total. Write ONLY lessons {first} to {last} of the course "
                     "(the course progresses from essential vocabulary to full interactions, so place these lessons accordingly and do not repeat words other parts would use). ")
        meta = ("title (<=40 chars, catchy, Spanish or English), emoji, level ('A1'|'A2'|'B1'|'B2'), summary_es (<=140 chars), " if part == 1 else "")
        rp = (", roleplay: {setup (1-2 sentences, English), ai_role (who the AI plays, e.g. a customer), user_role (who the learner plays), goal (<=160 chars), opening (first line the AI says)}" if part == 1 else "")
        return (
            "You design personalized English micro-courses for a Spanish-speaking adult. Build the course around the learner's REAL situation (their product, job, trip or goal), "
            "using the exact vocabulary and sentences they would actually need. " + _SAFE_SCENE + " If the request is unsafe, build a generic daily-life course instead.\n"
            + extra + f"Create exactly {count} lessons. Target CEFR level: {level} (keep sentences short and useful).\n"
            "Return JSON only: {" + meta +
            "lessons: [{title (English, <=34 chars), note_es (a practical tip in Spanish, <=180 chars), "
            "words: [8 objects {en (1-3 words), es (natural Mexican Spanish), emoji}], phrases: [6 objects {en (<=12 words, something the learner would really say), es}], "
            "dialogs: [3 objects {q (a line the OTHER person says), a (the best natural reply by the learner), wrong: [2 plausible but wrong or unnatural replies]}]}]" + rp + "}.\n"
            "Rules: no duplicate words across lessons; no placeholders; wrong answers must be clearly worse but believable; Spanish translations must be accurate."
        )

    # Se generan en paralelo bloques de hasta 3 lecciones: una sola llamada larga pasaba el límite de tiempo del servidor.
    sizes, left = [], n
    while left > 0:
        k = min(3, left)
        if left - k == 1:
            k = 2 if left > 3 else left
        sizes.append(k)
        left -= k
    plan_parts = []
    start = 1
    for i, k in enumerate(sizes):
        plan_parts.append((k, start, start + k - 1, i + 1, len(sizes)))
        start += k

    def _gen(spec):
        for attempt in range(2):
            try:
                return ai_json(_route_system(*spec), pedido, temperature=0.6)
            except Exception as exc:
                print(f"[ROUTE AI part {spec[3]} try {attempt}] {str(exc)[:160]}")
        return None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(plan_parts)) as ex:
        results = list(ex.map(_gen, plan_parts))
    data = None
    if all(isinstance(r, dict) for r in results):
        merged = dict(results[0])
        merged["lessons"] = [l for r in results for l in (r.get("lessons") or [])]
        data = _clean_route(merged, n)
    if not data:
        return json_error("No pude armar la ruta esta vez. Prueba describiéndola con otras palabras.", 500)
    try:
        res = client.table("rutas_personalizadas").insert({
            "user_id": user.id, "pedido": pedido, "titulo": data["titulo"], "emoji": data["emoji"], "nivel": data["nivel"],
            "resumen": data["resumen"], "lecciones": data["lecciones"], "roleplay": data["roleplay"], "progreso": {},
        }).execute()
        row = (res.data or [None])[0]
    except Exception as exc:
        print(f"[ROUTE SAVE] {exc}")
        return json_error("No se pudo guardar tu ruta. Verifica que exista la tabla (nuevas_funciones.sql).", 500)
    if not row:
        return json_error("No se pudo guardar tu ruta.", 500)
    return jsonify({"ok": True, "ruta": _route_summary(row)})


@app.get("/api/rutas/<route_id>")
def route_detail(route_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    route = _route_get(user.id, route_id)
    if not route:
        return json_error("Ruta no encontrada.", 404)
    return jsonify({"ok": True, "ruta": _route_summary(route), "lecciones": _route_states(route), "roleplay": route.get("roleplay") or {},
                    "palabras": [{"en": w["en"], "es": w["es"]} for l in route["lecciones"] for w in l["words"]][:40]})


@app.get("/api/rutas/<route_id>/leccion/<lesson_id>")
def route_lesson(route_id, lesson_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    route = _route_get(user.id, route_id)
    if not route:
        return json_error("Ruta no encontrada.", 404)
    st = next((s for s in _route_states(route) if s["id"] == lesson_id), None)
    if not st:
        return json_error("Lección no encontrada.", 404)
    if st["state"] == "locked":
        return json_error("Completa la lección anterior primero.", 403)
    unit = _route_unit(route)
    rank = PROFILE_LEVEL_RANK.get(_profile_for_path(user.id).get("cefr_level"), LEVEL_TO_RANK.get(unit["level"], 0))
    data = build_lesson_payload(unit, lesson_id, rank)
    data.update({"unit_code": unit["code"], "unit_title": unit["title"], "icon": unit["icon"], "lesson_id": lesson_id, "mode": "route", "route_id": route_id})
    if not data["exercises"]:
        return json_error("No se pudo preparar la lección.", 500)
    return jsonify({"ok": True, **data})


@app.post("/api/rutas/<route_id>/completar")
def route_complete(route_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    route = _route_get(user.id, route_id)
    if not route:
        return json_error("Ruta no encontrada.", 404)
    body = request.get_json(silent=True) or {}
    lesson_id = _short(body.get("lesson_id"), 20)
    states = _route_states(route)
    st = next((s for s in states if s["id"] == lesson_id), None)
    if not st or st["state"] == "locked":
        return json_error("Lección no válida.", 404)
    try:
        seconds = max(0, min(7200, int(body.get("seconds") or 0)))
        total = max(1, min(40, int(body.get("total") or 1)))
        correct = max(0, min(total, int(body.get("correct") or 0)))
    except (TypeError, ValueError):
        return json_error("Datos de la lección no válidos.")
    mistakes = _clean_mistakes(body.get("mistakes"))
    score = round(100 * correct / total, 1)
    passed = score >= PASS_THRESHOLD
    stars = stars_for(score)
    prog = dict(route.get("progreso") or {})
    prev = prog.get(lesson_id) or {}
    first_time = passed and not prev.get("passed")
    prog[lesson_id] = {"passed": bool(prev.get("passed") or passed), "score": max(score, float(prev.get("score") or 0)),
                       "stars": max(stars, int(prev.get("stars") or 0)), "tries": int(prev.get("tries") or 0) + 1}
    xp = 0
    if seconds >= 15 and passed:
        xp = (15 + 5 * stars) if first_time else 8
    route["progreso"] = prog
    route_done = first_time and all(s["state"] == "done" or s["id"] == lesson_id for s in _route_states(route))
    bonus = 40 if route_done else 0
    try:
        (supabase_admin or supabase).table("rutas_personalizadas").update(
            {"progreso": prog, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", route_id).eq("user_id", user.id).execute()
    except Exception as exc:
        print(f"[ROUTE COMPLETE SAVE] {exc}")
        return json_error("No se pudo guardar tu progreso. Inténtalo de nuevo.", 500)
    if (xp + bonus) and not _xp_allowed(user.id):
        xp = bonus = 0
    if xp + bonus:
        award_xp(user.id, xp + bonus)
    _log_session(user.id, "route", "route:" + str(route_id)[:8], lesson_id, score, stars, xp + bonus, mistakes, seconds)
    _save_mistakes_as_vocab(user.id, mistakes)
    nxt = next((s for s in _route_states(route) if s["state"] == "available" and s["id"] != lesson_id), None)
    return jsonify({"ok": True, "kind": "route", "score": score, "stars": stars, "passed": passed, "first_time": first_time,
                    "xp": xp + bonus, "unit_completed": route_done, "unit_bonus": bonus, "mistakes": len(mistakes), "plan_bonus": 0,
                    "next_route": ({"route_id": route_id, "lesson_id": nxt["id"], "lesson_title": nxt["title"]} if (nxt and passed) else None),
                    "route_done": route_done})


@app.post("/api/rutas/<route_id>/eliminar")
def route_delete(route_id):
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    try:
        (supabase_admin or supabase).table("rutas_personalizadas").delete().eq("id", route_id).eq("user_id", user.id).execute()
    except Exception as exc:
        print(f"[ROUTE DELETE] {exc}")
        return json_error("No se pudo eliminar la ruta.", 500)
    return jsonify({"ok": True})



# ---------------------------------------------------------------------------
#  4) DICCIONARIO · SHADOWING · ANALIZADOR DE VOZ · GRABA UNA REUNIÓN
#     (la voz y el reconocimiento del navegador son gratis; Azure solo se usa al calificar audio)
# ---------------------------------------------------------------------------
_DICT_CACHE = OrderedDict()


@app.post("/api/diccionario")
def dictionary_lookup():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    q = _short((request.get_json(silent=True) or {}).get("q"), 60)
    if len(q) < 2:
        return json_error("Escribe una palabra o frase.")
    key = q.lower()
    if key in _DICT_CACHE:
        _DICT_CACHE.move_to_end(key)
        return jsonify({"ok": True, **_DICT_CACHE[key], "cache": True})
    if not ai_client:
        return json_error("El diccionario no está disponible ahora mismo.", 503)
    try:
        d = ai_json(
            "You are a bilingual English-Spanish learner's dictionary. The query may be English or Spanish (a word, phrase, idiom or phrasal verb). "
            "If it is Spanish, 'word' is the best English equivalent. Return JSON only: {word (English headword/phrase), ipa (IPA without slashes, '' if a phrase longer than 3 words), "
            "level ('A1'..'C1'), meanings: [up to 3 objects {pos (noun, verb, adjective, phrase...), es (clear Spanish meaning, <=80 chars), "
            "examples: [2 objects {en (simple natural sentence using the word), es}]}], synonyms: [up to 5 English], "
            "collocations: [up to 4 objects {en, es}] (common word combinations), note_es (one short tip in Spanish about use, false friends or register, '' if none)}.",
            q, temperature=0.2)
    except Exception as exc:
        print(f"[DICT] {exc}")
        return json_error("No se pudo buscar ahora. Inténtalo de nuevo.", 500)
    meanings = []
    for m in (d.get("meanings") or [])[:3]:
        if isinstance(m, dict) and m.get("es"):
            meanings.append({"pos": _short(m.get("pos"), 24), "es": _short(m.get("es"), 120),
                             "examples": [{"en": _short(e.get("en"), 200), "es": _short(e.get("es"), 200)} for e in (m.get("examples") or [])[:2] if isinstance(e, dict) and e.get("en")]})
    word = _short(d.get("word"), 60)
    if not word or not meanings:
        return json_error("No encontré esa palabra. Revisa cómo está escrita.", 404)
    out = {"word": word, "ipa": _short(d.get("ipa"), 60).strip("/"), "level": _short(d.get("level"), 3), "meanings": meanings,
           "synonyms": [_short(s, 40) for s in (d.get("synonyms") or [])[:5] if s],
           "collocations": [{"en": _short(c.get("en"), 80), "es": _short(c.get("es"), 80)} for c in (d.get("collocations") or [])[:4] if isinstance(c, dict) and c.get("en")],
           "note": _short(d.get("note_es"), 200)}
    _DICT_CACHE[key] = out
    while len(_DICT_CACHE) > 400:
        _DICT_CACHE.popitem(last=False)
    return jsonify({"ok": True, **out})


def _shadow_static(n, rank):
    pool = []
    for u in LEARNING_UNITS:
        if LEVEL_TO_RANK.get(u["level"], 0) > rank + 1:
            continue
        for l in u["lessons"]:
            for p in l["phrases"]:
                if 3 <= len(p["en"].split()) <= 12:
                    pool.append({"en": p["en"], "es": p["es"], "tema": u["title"]})
    random.shuffle(pool)
    return pool[:n]


@app.get("/api/shadowing/frases")
def shadowing_static():
    """Frases del currículo (sin IA, sin créditos). Se califican con el audio rápido de Azure."""
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    rank = PROFILE_LEVEL_RANK.get(_profile_for_path(user.id).get("cefr_level"), 0)
    plan = _user_plan(user)
    return jsonify({"ok": True, "frases": _shadow_static(6, rank), "limite_dia": PLAN_FEATURES[plan]["shadowing_dia"],
                    "tema_ok": PLAN_FEATURES[plan]["shadowing_tema"]})


@app.post("/api/shadowing/tema")
def shadowing_topic():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not PLAN_FEATURES[_user_plan(user)]["shadowing_tema"]:
        return _gate(user, "Shadowing con tus propios temas está disponible desde el plan Básico.")
    tema = _short((request.get_json(silent=True) or {}).get("tema"), 120)
    if len(tema) < 3:
        return json_error("Escribe el tema (por ejemplo: pedir un café, una entrevista).")
    lvl = {"beginner": "A1", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(_profile_for_path(user.id).get("cefr_level"), "A2")
    try:
        d = ai_json("You write short English sentences for shadowing practice (a learner repeats them after hearing native speech). " + _SAFE_SCENE +
                    f" Level {lvl}. Return JSON only: {{frases: [6 objects {{en (natural spoken sentence of 5-12 words with good rhythm), es (Spanish translation)}}]}}.",
                    f"Topic: {tema}", temperature=0.6)
    except Exception as exc:
        print(f"[SHADOW TOPIC] {exc}")
        return json_error("No se pudieron preparar las frases.", 500)
    fr = [{"en": _short(f.get("en"), 140), "es": _short(f.get("es"), 160), "tema": tema} for f in (d.get("frases") or [])[:6] if isinstance(f, dict) and f.get("en") and f.get("es")]
    if len(fr) < 3:
        return json_error("No se pudieron preparar las frases.", 500)
    return jsonify({"ok": True, "frases": fr})


# ---------------------------------------------------------------------------
#  CLIPS CORTOS (mini-escenas con subtítulos, sin videos con licencia) y PRESENTACIONES
# ---------------------------------------------------------------------------
_CLIPS = [
 ("coffee", "Ordering coffee", "☕", 0, [("B", "Hi! What can I get you?", "¡Hola! ¿Qué te sirvo?"), ("A", "A medium latte, please.", "Un latte mediano, por favor."), ("B", "For here or to go?", "¿Para aquí o para llevar?"), ("A", "To go, thanks.", "Para llevar, gracias.")], ("What does the customer want?", ["A tea", "A medium latte", "A sandwich"], 1)),
 ("airport", "At the airport", "✈️", 0, [("B", "Passport, please.", "Pasaporte, por favor."), ("A", "Here you are.", "Aquí tiene."), ("B", "Are you checking any bags?", "¿Va a documentar maletas?"), ("A", "Yes, just one.", "Sí, solo una.")], ("How many bags is the traveler checking?", ["None", "One", "Three"], 1)),
 ("directions", "Asking for directions", "🗺️", 0, [("A", "Excuse me, where is the train station?", "Disculpe, ¿dónde está la estación de tren?"), ("B", "Go straight and turn left at the bank.", "Siga derecho y gire a la izquierda en el banco."), ("A", "Is it far?", "¿Está lejos?"), ("B", "No, it's about five minutes on foot.", "No, son unos cinco minutos a pie.")], ("How far is the station?", ["Five minutes on foot", "One hour", "Next to the bank door"], 0)),
 ("hotel", "Hotel check-in", "🏨", 1, [("B", "Welcome! Do you have a reservation?", "¡Bienvenido! ¿Tiene reservación?"), ("A", "Yes, under the name Lopez.", "Sí, a nombre de López."), ("B", "Great. You're in room 305, and breakfast is until ten.", "Perfecto. Está en la habitación 305 y el desayuno es hasta las diez."), ("A", "Thank you. Is there Wi-Fi?", "Gracias. ¿Hay Wi-Fi?")], ("Until when is breakfast served?", ["Eight", "Ten", "Noon"], 1)),
 ("job", "Job interview", "💼", 1, [("B", "Tell me about yourself.", "Cuéntame sobre ti."), ("A", "I'm a designer with three years of experience.", "Soy diseñador con tres años de experiencia."), ("B", "Why do you want this job?", "¿Por qué quieres este trabajo?"), ("A", "I love solving problems with creative ideas.", "Me encanta resolver problemas con ideas creativas.")], ("What is the candidate's job?", ["Designer", "Teacher", "Driver"], 0)),
 ("doctor", "At the doctor", "🩺", 1, [("B", "What seems to be the problem?", "¿Cuál parece ser el problema?"), ("A", "I've had a headache since yesterday.", "Tengo dolor de cabeza desde ayer."), ("B", "Do you have a fever?", "¿Tiene fiebre?"), ("A", "No, but I feel very tired.", "No, pero me siento muy cansado.")], ("What is the patient's main problem?", ["A broken arm", "A headache", "A cough"], 1)),
 ("shop", "Buying clothes", "👕", 0, [("A", "Do you have this shirt in a larger size?", "¿Tiene esta camisa en una talla más grande?"), ("B", "Let me check. We have a large in blue.", "Déjeme ver. Tenemos una grande en azul."), ("A", "Perfect. How much is it?", "Perfecto. ¿Cuánto cuesta?"), ("B", "It's twenty-five dollars.", "Cuesta veinticinco dólares.")], ("What color is the large shirt?", ["Red", "Blue", "Black"], 1)),
 ("meeting", "Starting a meeting", "📅", 2, [("A", "Thanks for joining, everyone. Let's get started.", "Gracias por unirse. Empecemos."), ("B", "Could you share your screen, please?", "¿Podrías compartir tu pantalla, por favor?"), ("A", "Sure. Can you all see the slides?", "Claro. ¿Todos ven las diapositivas?"), ("B", "Yes, it looks good. Go ahead.", "Sí, se ve bien. Adelante.")], ("What does the speaker share?", ["A video", "The screen with slides", "A document by email"], 1)),
 ("restaurant", "Booking a table", "🍽️", 0, [("A", "I'd like a table for four at eight, please.", "Quisiera una mesa para cuatro a las ocho, por favor."), ("B", "Certainly. Name, please?", "Claro. ¿A nombre de quién?"), ("A", "Garcia.", "García."), ("B", "Perfect, see you tonight.", "Perfecto, nos vemos esta noche.")], ("For how many people is the table?", ["Two", "Four", "Eight"], 1)),
 ("complaint", "A polite complaint", "😕", 2, [("A", "Excuse me, I ordered the chicken, but this is fish.", "Disculpe, pedí pollo, pero esto es pescado."), ("B", "I'm so sorry about that. I'll fix it right away.", "Lo siento mucho. Lo corrijo enseguida."), ("A", "Thank you, I appreciate it.", "Gracias, lo agradezco."), ("B", "It's on the house.", "Va por cuenta de la casa.")], ("What did the customer receive by mistake?", ["Fish", "Pasta", "Salad"], 0)),
 ("weekend", "Weekend plans", "🎉", 1, [("A", "What are you doing this weekend?", "¿Qué vas a hacer este fin de semana?"), ("B", "I'm going hiking with my friends.", "Voy a hacer senderismo con mis amigos."), ("A", "That sounds fun! Where?", "¡Suena divertido! ¿Dónde?"), ("B", "In the mountains near the city.", "En las montañas cerca de la ciudad.")], ("What will the speaker do?", ["Go hiking", "Stay home", "Go shopping"], 0)),
 ("taxi", "Taking a taxi", "🚕", 0, [("A", "To the city center, please.", "Al centro, por favor."), ("B", "Sure. It'll take about twenty minutes.", "Claro. Tardaremos unos veinte minutos."), ("A", "Can I pay by card?", "¿Puedo pagar con tarjeta?"), ("B", "Yes, no problem.", "Sí, sin problema.")], ("How long is the ride?", ["Five minutes", "Twenty minutes", "One hour"], 1)),
]


def _clip_json(c):
    cid, titulo, emoji, nivel, esc_, (q, ops, ok) = c
    return {"id": cid, "titulo": titulo, "emoji": emoji, "nivel": nivel,
            "escena": [{"quien": w, "en": en, "es": es} for w, en, es in esc_], "quiz": {"q": q, "opciones": ops, "correcta": ok}}


@app.get("/api/clips")
def clips_list():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    rank = PROFILE_LEVEL_RANK.get(_profile_for_path(user.id).get("cefr_level"), 0)
    pool = [c for c in _CLIPS if c[3] <= rank + 1]
    random.shuffle(pool)
    f = PLAN_FEATURES[_user_plan(user)]
    return jsonify({"ok": True, "clips": [_clip_json(c) for c in pool[:6]], "limite_dia": f["clips_dia"], "tema_ok": f["clip_tema"]})


@app.post("/api/clips/tema")
def clips_topic():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not PLAN_FEATURES[_user_plan(user)]["clip_tema"]:
        return _gate(user, "Los clips con tu propio tema están disponibles desde el plan Básico.")
    tema = _short((request.get_json(silent=True) or {}).get("tema"), 120)
    if len(tema) < 3:
        return json_error("Escribe el tema (por ejemplo: pedir ayuda en el gimnasio).")
    lvl = {"beginner": "A1", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(_profile_for_path(user.id).get("cefr_level"), "A2")
    try:
        d = ai_json("You write very short realistic two-person English dialogues for a Spanish-speaking learner. " + _SAFE_SCENE +
                    f" Level {lvl}. Return JSON only: {{titulo (3-5 words), emoji, escena: [4 or 5 objects {{quien: 'A' or 'B' alternating, en (6-14 words), es (Spanish)}}], "
                    "quiz: {q (a comprehension question in English), opciones: [3 short strings], correcta: index 0-2}}}.", f"Situation: {tema}", temperature=0.7)
        esc_ = [{"quien": "B" if str(x.get("quien")).upper() == "B" else "A", "en": _short(x.get("en"), 160), "es": _short(x.get("es"), 180)}
                for x in (d.get("escena") or [])[:5] if isinstance(x, dict) and x.get("en") and x.get("es")]
        qz = d.get("quiz") or {}
        ops = [_short(o, 60) for o in (qz.get("opciones") or [])[:3]]
        corr = int(qz.get("correcta")) if str(qz.get("correcta", "")).isdigit() else 0
        if len(esc_) < 3 or len(ops) < 3 or not (0 <= corr < 3):
            raise ValueError("clip incompleto")
    except Exception as exc:
        print(f"[CLIP TEMA] {exc}")
        return json_error("No se pudo preparar el clip. Inténtalo de nuevo.", 500)
    return jsonify({"ok": True, "clip": {"id": "ai-" + _uuid.uuid4().hex[:8], "titulo": _short(d.get("titulo"), 40) or tema, "emoji": _short(d.get("emoji"), 4) or "🎬",
                                          "nivel": 1, "escena": esc_, "quiz": {"q": _short(qz.get("q"), 160), "opciones": ops, "correcta": corr}}})


@app.post("/api/clips/completar")
def clips_done():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    body = request.get_json(silent=True) or {}
    acierto = bool(body.get("acierto"))
    xp = 0
    f = PLAN_FEATURES[_user_plan(user)]
    ok, _w = _rate_hit((user.id, "clips"), f["clips_dia"], 86400) if not is_admin_user(user) else (True, 0)
    if ok and _xp_allowed(user.id):
        xp = 10 if acierto else 5
        award_xp(user.id, xp)
    _log_session(user.id, "clip", "clip:" + _short(body.get("id"), 20), None, 100 if acierto else 50, 0, xp, [], 0)
    return jsonify({"ok": True, "xp": xp, "limite_alcanzado": not ok})


@app.post("/api/presentacion/guion")
def presentation_script():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    plan = _user_plan(user)
    f = PLAN_FEATURES[plan]
    if not f["presentacion"]:
        return _gate(user, "Practicar presentaciones está disponible desde el plan Básico.")
    texto = (request.get_json(silent=True) or {}).get("texto") or ""
    texto = re.sub(r"[ \t]+", " ", str(texto)).strip()[:3500]
    if len(texto) < 20:
        return json_error("Pega el texto de tus diapositivas (al menos una idea por diapositiva).")
    n = f["presentacion_slides"]
    lvl = {"beginner": "A2", "elementary": "A2", "intermediate": "B1", "advanced": "B2"}.get(_profile_for_path(user.id).get("cefr_level"), "B1")
    try:
        d = ai_json("You help a Spanish speaker rehearse a presentation in English. " + _SAFE_SCENE +
                    f" The user pastes the text of their slides (the content may be in Spanish or English). Create at most {n} slides, keeping their order. Level {lvl}. "
                    "Return JSON only: {titulo, slides: [objects {titulo (short English title), guion (what the presenter says aloud: 35-60 words, natural spoken English, first person), "
                    "frases_clave: [3 useful presentation phrases used in the script], es (one-line Spanish summary)}]}.", texto, temperature=0.5)
        sl = []
        for s in (d.get("slides") or [])[:n]:
            if isinstance(s, dict) and s.get("guion"):
                sl.append({"titulo": _short(s.get("titulo"), 60), "guion": _short(s.get("guion"), 520),
                           "frases_clave": [_short(x, 80) for x in (s.get("frases_clave") or [])[:3] if x], "es": _short(s.get("es"), 160)})
        if not sl:
            raise ValueError("sin diapositivas")
    except Exception as exc:
        print(f"[PRESENTACION] {exc}")
        return json_error("No se pudo preparar la presentación. Inténtalo de nuevo.", 500)
    return jsonify({"ok": True, "titulo": _short(d.get("titulo"), 80) or "Mi presentación", "slides": sl, "maximo": n})


def _wav_seconds(path):
    import wave
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate() or 16000)
    except Exception:
        return 0.0


def transcribe_long(wav_path, max_seconds=200):
    """Transcripción continua (la normal, recognize_once, se corta tras la primera pausa)."""
    cfg = speech_config()
    rec = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=speechsdk.audio.AudioConfig(filename=wav_path))
    parts, done = [], threading.Event()
    rec.recognized.connect(lambda e: parts.append(e.result.text) if e.result.reason == speechsdk.ResultReason.RecognizedSpeech and e.result.text else None)
    rec.session_stopped.connect(lambda e: done.set())
    rec.canceled.connect(lambda e: done.set())
    rec.start_continuous_recognition()
    done.wait(timeout=max_seconds + 40)
    try:
        rec.stop_continuous_recognition()
    except Exception:
        pass
    return " ".join(parts).strip()


_FILLERS = ("um", "uh", "er", "like", "you know", "i mean", "actually", "basically", "kind of", "sort of")


@app.post("/api/reunion/analizar")
def meeting_analyze():
    user, error = authenticated_user()
    if error:
        return json_error(error[0], error[1])
    if not PLAN_FEATURES[_user_plan(user)]["reunion"]:
        return _gate(user, "Grabar una reunión y recibir feedback está disponible en el plan Pro.")
    upload = request.files.get("audio")
    if not upload:
        return json_error("No se recibió audio.")
    wav_path = None
    try:
        wav_path = convert_audio_to_wav(upload)
        secs = _wav_seconds(wav_path)
        if secs > 200:
            return json_error("La grabación dura más de 3 minutos. Graba un fragmento más corto.")
        if secs and secs < 8:
            return json_error("La grabación es muy corta. Graba al menos 10 segundos.")
        text = transcribe_long(wav_path)
    except Exception as exc:
        print(f"[MEETING STT] {exc}")
        return json_error("No se pudo transcribir el audio.", 500)
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
    if len(text.split()) < 12:
        return json_error("Casi no se entendió inglés en la grabación. Acércate al micrófono e inténtalo otra vez.")
    low = " " + text.lower() + " "
    fillers = {f: low.count(" " + f + " ") for f in _FILLERS if low.count(" " + f + " ")}
    try:
        d = ai_json(
            "You review a transcript of an English-language meeting for a Spanish-speaking learner. The audio may contain several people and the transcript has no speaker labels: "
            "focus on the learner's likely lines, and if you cannot tell, give feedback on the language use overall. Return JSON only, in Spanish unless a key says English, with keys: "
            "resumen (2-3 sentences of what the meeting was about), puntuacion (0-100 clarity and correctness of the English), "
            "fortalezas (up to 3 short strings), mejoras (up to 5 objects {dijiste (English, as in the transcript), mejor (English), por_que (Spanish <=100 chars)}), "
            "vocabulario (up to 5 objects {en, es}: useful business phrases for this meeting), acciones (up to 4 short strings: action items or decisions mentioned), "
            "consejo (1-2 sentences on what to practice next).", text[:6000], temperature=0.3)
    except Exception as exc:
        print(f"[MEETING AI] {exc}")
        return json_error("No se pudo generar el feedback.", 500)
    try:
        sc = max(0, min(100, int(float(d.get("puntuacion")))))
    except (TypeError, ValueError):
        sc = 0
    out = {"transcript": text, "segundos": int(secs), "palabras": len(text.split()), "muletillas": fillers, "puntuacion": sc,
           "resumen": _short(d.get("resumen"), 500), "fortalezas": [_short(x, 160) for x in (d.get("fortalezas") or [])[:3]],
           "mejoras": [{"dijiste": _short(m.get("dijiste"), 240), "mejor": _short(m.get("mejor"), 240), "por_que": _short(m.get("por_que"), 160)} for m in (d.get("mejoras") or [])[:5] if isinstance(m, dict)],
           "vocabulario": [{"en": _short(m.get("en"), 120), "es": _short(m.get("es"), 140)} for m in (d.get("vocabulario") or [])[:5] if isinstance(m, dict) and m.get("en")],
           "acciones": [_short(x, 160) for x in (d.get("acciones") or [])[:4]], "consejo": _short(d.get("consejo"), 300)}
    award_xp(user.id, 25)
    save_history("historial_tutor", user.id, {"mensaje_usuario": "[Reunión grabada]", "respuesta_tutor": json.dumps({k: v for k, v in out.items() if k != "transcript"}, ensure_ascii=False)})
    return jsonify({"ok": True, "xp": 25, **out})


# ---------------------------------------------------------------------------
#  NOTIFICACIONES PUSH (Web Push / VAPID, gratis). Tabla: push_subscriptions
# ---------------------------------------------------------------------------
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = env("VAPID_SUBJECT", "mailto:a07077189@tec.mx")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")


def _push_ready():
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and supabase_admin)


def _push_parse_sub(b):
    sub = b.get("subscription") if isinstance(b, dict) else None
    if not isinstance(sub, dict):
        return None
    ep = sub.get("endpoint")
    keys = sub.get("keys") or {}
    p256, auth = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(ep, str) and ep.startswith("https://") and len(ep) <= 1000):
        return None
    if not (isinstance(p256, str) and isinstance(auth, str) and 10 <= len(p256) <= 200 and 8 <= len(auth) <= 100):
        return None
    return {"endpoint": ep, "p256dh": p256, "auth": auth}


def _push_user_optional():
    """(user|None, error|None). Sin token => anónimo (permitido solo con correo)."""
    if not get_bearer_token():
        return None, None
    user, error = authenticated_user(require_subscription=False)
    return user, error


@app.get("/api/push/key")
def push_key():
    return jsonify({"ok": True, "ready": _push_ready(), "key": VAPID_PUBLIC_KEY if _push_ready() else ""})


@app.post("/api/push/subscribe")
def push_subscribe():
    """Guarda (o actualiza) la suscripción de este dispositivo. Con sesión la liga al usuario;
    sin sesión (justo al crear la cuenta) la guarda con el correo y se liga al iniciar sesión."""
    if not _push_ready():
        return json_error("Las notificaciones aún no están disponibles.", 503)
    ok, _w = _rate_hit(("push-sub", _client_ip()), 40, 3600)
    if not ok:
        return json_error("Demasiados intentos. Espera un momento.", 429)
    b = request.get_json(silent=True) or {}
    sub = _push_parse_sub(b)
    if not sub:
        return json_error("Suscripción inválida.")
    user, error = _push_user_optional()
    if error:
        return json_error(error[0], error[1])
    row = dict(sub)
    if user:
        row["user_id"] = user.id
        row["email"] = (getattr(user, "email", None) or "")[:254].lower() or None
    else:
        email = _short(b.get("email"), 254).strip().lower()
        if not _EMAIL_RE.match(email):
            return json_error("Correo requerido.")
        row["email"] = email
    hr = _num(b.get("hour"))
    if hr is not None:
        row["hour"] = max(0, min(int(hr), 23))
    if b.get("tz"):
        row["tz"] = _short(b.get("tz"), 64)
    row["lang"] = "en" if b.get("lang") == "en" else "es"
    row["ua"] = _short(request.headers.get("User-Agent"), 200)
    row.update({"enabled": True, "fail_count": 0, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    try:
        supabase_admin.table("push_subscriptions").upsert(row, on_conflict="endpoint").execute()
    except Exception as exc:
        return json_error(_err_log("No se pudo guardar la suscripción", exc), 500)
    return jsonify({"ok": True})


@app.post("/api/push/unsubscribe")
def push_unsubscribe():
    if not supabase_admin:
        return json_error("No disponible.", 503)
    ok, _w = _rate_hit(("push-sub", _client_ip()), 40, 3600)
    if not ok:
        return json_error("Demasiados intentos. Espera un momento.", 429)
    b = request.get_json(silent=True) or {}
    ep = b.get("endpoint")
    if not (isinstance(ep, str) and ep.startswith("https://") and len(ep) <= 1000):
        return json_error("Suscripción inválida.")
    try:
        supabase_admin.table("push_subscriptions").delete().eq("endpoint", ep).execute()
    except Exception as exc:
        return json_error(_err_log("No se pudo desactivar", exc), 500)
    return jsonify({"ok": True})


@app.post("/api/push/prefs")
def push_prefs():
    """Cambia la hora preferida del recordatorio de este dispositivo."""
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    b = request.get_json(silent=True) or {}
    ep = b.get("endpoint")
    hr = _num(b.get("hour"))
    if not (isinstance(ep, str) and ep.startswith("https://")) or hr is None:
        return json_error("Datos inválidos.")
    upd = {"hour": max(0, min(int(hr), 23))}
    if b.get("tz"):
        upd["tz"] = _short(b.get("tz"), 64)
    try:
        supabase_admin.table("push_subscriptions").update(upd).eq("endpoint", ep).eq("user_id", user.id).execute()
    except Exception as exc:
        return json_error(_err_log("No se pudo guardar", exc), 500)
    return jsonify({"ok": True})


def _push_send(row, title, body, url="./", tag="talvo", touch=True, mood="cheer"):
    """Envía una notificación a una suscripción. Devuelve True/False y limpia las caducadas."""
    if not _push_ready():
        return False
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return False
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag, "mood": mood, "lang": row.get("lang") or "es"}, ensure_ascii=False)
    try:
        webpush(subscription_info={"endpoint": row["endpoint"], "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
                data=payload, vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims={"sub": VAPID_SUBJECT}, ttl=86400, timeout=10)
        try:
            upd_ok = {"fail_count": 0}
            if touch:
                upd_ok["last_sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            supabase_admin.table("push_subscriptions").update(upd_ok).eq("endpoint", row["endpoint"]).execute()
        except Exception:
            pass
        return True
    except WebPushException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        try:
            if code in (404, 410):
                supabase_admin.table("push_subscriptions").delete().eq("endpoint", row["endpoint"]).execute()
            else:
                supabase_admin.table("push_subscriptions").update(
                    {"fail_count": int(row.get("fail_count") or 0) + 1}).eq("endpoint", row["endpoint"]).execute()
        except Exception:
            pass
        return False
    except Exception:
        return False


@app.post("/api/push/test")
def push_test():
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    if not _push_ready():
        return json_error("Las notificaciones aún no están disponibles.", 503)
    ok, _w = _rate_hit((user.id, "push-test"), 5, 3600)
    if not ok:
        return json_error("Ya enviaste varias pruebas. Intenta más tarde.", 429)
    try:
        rows = supabase_admin.table("push_subscriptions").select("*").eq("user_id", user.id).eq("enabled", True).execute().data or []
    except Exception as exc:
        return json_error(_err_log("No se pudo enviar la prueba", exc), 500)
    sent = sum(1 for r in rows if _push_send(r, "¡Funciona! 🐔", "Palanqueta te avisará cuando sea hora de practicar.", "./?pq=cheer", "talvo-test", touch=False))
    return jsonify({"ok": True, "enviadas": sent, "dispositivos": len(rows)})



# ---------------------------------------------------------------------------
#  RECORDATORIOS AUTOMÁTICOS (paso 2). Lo llama un cron gratis cada 15 min.
# ---------------------------------------------------------------------------
CRON_SECRET = env("CRON_SECRET", "")
# "1" (por defecto): no avisar a quien ya practicó hoy. Pon "0" en Render para avisar a todos.
PUSH_SKIP_PRACTICED = env("PUSH_SKIP_PRACTICED", "1") != "0"

# (clave, título, cuerpo). {n} = días de racha. Se evita repetir la última que recibió el usuario.
_PUSH_MSGS = {
    "es": {
        "plain": [
            ("p1", "Palanqueta te extraña 🐔", "Solo 5 minutos hoy y tu inglés sigue creciendo."),
            ("p2", "¿Practicamos un poquito? 🎧", "Una lección corta y listo. ¡Tú puedes!"),
            ("p3", "Hora de tu inglés ✨", "Entra, haz una práctica rápida y cierra el día con una victoria."),
            ("p4", "¡Cuack! Es tu hora 🐥", "Palanqueta ya está lista. ¿Y tú?"),
            ("p5", "Un minuto basta 💪", "Repasa unas palabras y mantén el hábito vivo."),
            ("p6", "Tu futuro yo te lo agradece 🚀", "Hoy toca practicar un poco. Abre Talvo."),
        ],
        "streak": [
            ("s1", "¡Tu racha de {n} días está en juego! 🔥", "Practica hoy y no la pierdas."),
            ("s2", "No rompas tu racha de {n} días 🔥", "Con una práctica corta la salvas."),
            ("s3", "{n} días seguidos… ¡vamos por uno más! 🏅", "Palanqueta te espera."),
        ],
    },
    "en": {
        "plain": [
            ("p1", "Palanqueta misses you 🐔", "Just 5 minutes today keeps your English growing."),
            ("p2", "Shall we practice a bit? 🎧", "One short lesson and you're done. You've got this!"),
            ("p3", "Your English time ✨", "Hop in, do a quick practice, and end the day with a win."),
            ("p4", "Cluck! It's your time 🐥", "Palanqueta is ready. Are you?"),
            ("p5", "One minute is enough 💪", "Review a few words and keep the habit alive."),
            ("p6", "Future you says thanks 🚀", "Time for a little practice. Open Talvo."),
        ],
        "streak": [
            ("s1", "Your {n}-day streak is on the line! 🔥", "Practice today and keep it alive."),
            ("s2", "Don't break your {n}-day streak 🔥", "A short practice saves it."),
            ("s3", "{n} days in a row… let's make it one more! 🏅", "Palanqueta is waiting."),
        ],
    },
}


def _push_practiced_today(uid, ln, trust_local):
    """last_activity_date está en UTC: de noche (hora local) puede caer en "mañana". Confirma con la última sesión real."""
    try:
        ev = (supabase_admin.table("learning_sessions").select("created_at,kind").eq("user_id", uid)
              .order("created_at", desc=True).limit(6).execute().data) or []
        for e in ev:
            if e.get("kind") in ("plan_bonus", "level_change"):
                continue
            dt = datetime.fromisoformat(str(e["created_at"]).replace("Z", "+00:00")).astimezone(ln.tzinfo)
            return dt.date() == ln.date()
        return bool(trust_local)
    except Exception:
        return bool(trust_local)


def _push_local_now(tz):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz)) if tz else datetime.now(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _push_pick(lang, streak_at_risk, streak, last_kind):
    pool = _PUSH_MSGS.get(lang) or _PUSH_MSGS["es"]
    items = pool["streak"] if (streak_at_risk and streak >= 2) else pool["plain"]
    options = [m for m in items if m[0] != last_kind] or items
    key, title, body = random.choice(options)
    return key, title.replace("{n}", str(streak)), body.replace("{n}", str(streak))


@app.post("/api/push/cron")
def push_cron():
    """Envía el recordatorio a quien tiene activadas las notificaciones, ya es su hora y no ha practicado hoy."""
    import hmac
    if not CRON_SECRET or not hmac.compare_digest(request.headers.get("X-Cron-Secret", ""), CRON_SECRET):
        return json_error("No autorizado.", 401)
    if not _push_ready():
        return json_error("Las notificaciones aún no están disponibles.", 503)
    try:
        rows = supabase_admin.table("push_subscriptions").select("*").eq("enabled", True).lt("fail_count", 5).execute().data or []
    except Exception as exc:
        return json_error(_err_log("No se pudieron leer las suscripciones", exc), 500)

    now_utc = datetime.now(timezone.utc)
    due = []
    for r in rows:
        ln = _push_local_now(r.get("tz"))
        if ln.hour != int(r.get("hour") if r.get("hour") is not None else 19):
            continue
        ls = r.get("last_sent_at")
        if r.get("last_kind") and ls:
            try:
                if now_utc - datetime.fromisoformat(str(ls).replace("Z", "+00:00")) < timedelta(hours=20):
                    continue  # ya se le avisó hoy
            except Exception:
                pass
        due.append((r, ln))
    if not due:
        return jsonify({"ok": True, "revisadas": len(rows), "enviadas": 0})

    # Perfiles: por user_id, o por correo si la suscripción se guardó antes de iniciar sesión.
    ids = list({r["user_id"] for r, _ in due if r.get("user_id")})
    emails = list({(r.get("email") or "").lower() for r, _ in due if not r.get("user_id") and r.get("email")})
    profs = {}
    try:
        if ids:
            for p in supabase_admin.table("profiles").select("id,email,streak_days,last_activity_date,is_subscribed,trial_ends_at").in_("id", ids).execute().data or []:
                profs[p["id"]] = p
        if emails:
            for p in supabase_admin.table("profiles").select("id,email,streak_days,last_activity_date,is_subscribed,trial_ends_at").in_("email", emails).execute().data or []:
                profs["e:" + (p.get("email") or "").lower()] = p
    except Exception as exc:
        return json_error(_err_log("No se pudieron leer los perfiles", exc), 500)

    jobs = []
    for r, ln in due:
        prof = profs.get(r.get("user_id")) or profs.get("e:" + (r.get("email") or "").lower())
        if not prof:
            continue  # sin cuenta confirmada todavía: no se manda nada
        last = prof.get("last_activity_date")
        today_local = ln.date().isoformat()
        today_utc = now_utc.date().isoformat()
        if PUSH_SKIP_PRACTICED and last in (today_local, today_utc) and _push_practiced_today(prof.get("id"), ln, last == today_local):
            continue  # ya practicó hoy
        if not has_active_access(prof):
            continue  # prueba vencida o sin plan: no insistir
        try:
            idle = (ln.date() - datetime.fromisoformat(str(last)[:10]).date()).days if last else None
        except Exception:
            idle = None
        # No saturar: a quien lleva días sin entrar se le avisa cada vez más espaciado (hasta ~1 mes).
        if idle is None:
            if int(r.get("sent_count") or 0) >= 4:
                continue
        elif idle > 3 and idle not in (5, 7, 10, 14, 21, 30):
            continue
        yesterday = {(ln.date() - timedelta(days=1)).isoformat(), (now_utc.date() - timedelta(days=1)).isoformat()}
        at_risk = last in yesterday
        key, title, body = _push_pick(r.get("lang") or "es", at_risk, int(prof.get("streak_days") or 0), r.get("last_kind"))
        mood = "streak" if key.startswith("s") else ("miss" if (idle or 0) >= 2 else "cheer")
        jobs.append((r, key, title, body, mood))

    def _go(job):
        r, key, title, body, mood = job
        if _push_send(r, title, body, "./?pq=" + mood, "talvo-recordatorio", mood=mood):
            try:
                supabase_admin.table("push_subscriptions").update(
                    {"last_kind": key, "sent_count": int(r.get("sent_count") or 0) + 1}).eq("endpoint", r["endpoint"]).execute()
            except Exception:
                pass
            return True
        return False

    with ThreadPoolExecutor(max_workers=6) as ex:
        sent = sum(1 for ok in ex.map(_go, jobs) if ok)
    return jsonify({"ok": True, "revisadas": len(rows), "a_la_hora": len(due), "enviadas": sent})


# ---------------------------------------------------------------------------
#  CORREOS DE RECORDATORIO (gratis). Render gratis bloquea SMTP, así que se envían por HTTPS:
#   - EMAIL_WEBHOOK_URL + EMAIL_WEBHOOK_SECRET: un Google Apps Script que manda desde tu Gmail (100/día), o
#   - BREVO_API_KEY + EMAIL_FROM: Brevo (300/día) con un remitente verificado.
#  Tablas: email_log, email_optout. Lo dispara el mismo cron de GitHub (cada 15 min; aquí se filtra la hora).
# ---------------------------------------------------------------------------
APP_URL = env("APP_URL", "https://english-academy-cabex1.vercel.app").rstrip("/")
BACKEND_PUBLIC_URL = env("BACKEND_PUBLIC_URL", "https://backend-ingles-e3ms.onrender.com").rstrip("/")
EMAIL_WEBHOOK_URL = env("EMAIL_WEBHOOK_URL", "")
EMAIL_WEBHOOK_SECRET = env("EMAIL_WEBHOOK_SECRET", "")
BREVO_API_KEY = env("BREVO_API_KEY", "")
EMAIL_FROM = env("EMAIL_FROM", "")
EMAIL_MAX_PER_RUN = int(env("EMAIL_MAX_PER_RUN", "40") or 40)
EMAIL_HOURS = (10, 11)  # hora de México en la que se envían (el cron corre cada 15 min)


def _email_ready():
    return bool(EMAIL_WEBHOOK_URL and EMAIL_WEBHOOK_SECRET) or bool(BREVO_API_KEY and EMAIL_FROM)


def _unsub_token(email):
    import hmac, hashlib
    return hmac.new((CRON_SECRET or "x").encode(), (email or "").lower().encode(), hashlib.sha256).hexdigest()[:32]


def _unsub_url(email):
    from urllib.parse import quote
    return f"{BACKEND_PUBLIC_URL}/api/email/unsub?e={quote((email or '').lower())}&t={_unsub_token(email)}"


# kind -> (asunto, titular, cuerpo, pasos, texto del botón, ruta del botón)
_EMAIL_KINDS = {
    "verify": {
        "subject": "✉️ {name}, falta un paso para empezar tu prueba gratis",
        "pre": "Confirma tu correo y entra a practicar inglés con Palanqueta.",
        "title": "¡Casi listo, {name}!",
        "body": "Creaste tu cuenta en <b>Talvo English</b>, pero todavía no confirmas tu correo. Sin ese paso no podemos activar tu <b>prueba gratis de 7 días</b>.",
        "steps": ["Toca el botón de abajo para abrir Talvo.", "Pulsa <b>Reenviar correo</b> (llega en segundos; revisa Spam o Promociones).", "Abre el mensaje, confirma… ¡y listo!"],
        "cta": "Confirmar mi correo", "path": "/?verify={email_q}",
    },
    "start": {
        "subject": "🚀 {name}, tu primera lección te está esperando",
        "pre": "Solo 5 minutos y Palanqueta personaliza tu ruta de inglés.",
        "title": "Empecemos con tu primera lección",
        "body": "Tu cuenta ya está lista, pero aún no practicas. Con solo <b>5 minutos</b> Palanqueta conoce tu nivel y arma una ruta hecha para ti.",
        "steps": ["Haz el examen rápido de nivel.", "Completa tu primera lección y gana tu primera racha 🔥", "Activa los recordatorios para no olvidarlo."],
        "cta": "Empezar ahora", "path": "/",
    },
    "nopush": {
        "subject": "🔔 {name}, activa los recordatorios y no pierdas tu racha",
        "pre": "Un aviso al día, a la hora que tú elijas. Toma 10 segundos.",
        "title": "Que Palanqueta te avise por ti",
        "body": "Practicar un poquito cada día es lo que más funciona, y un recordatorio ayuda mucho. Actívalo y Palanqueta te escribe a la hora que elijas. {streak}",
        "steps": ["Entra a <b>Mi cuenta</b>.", "Activa <b>Recordatorios</b> y acepta el permiso.", "Elige tu hora favorita. ¡Eso es todo!"],
        "cta": "Activar recordatorios", "path": "/?go=cuenta",
    },
    "comeback": {
        "subject": "🥺 {name}, Palanqueta te extraña",
        "pre": "Tu progreso sigue intacto. Vuelve con una lección cortita.",
        "title": "¡Te extrañamos, {name}!",
        "body": "Llevas <b>{idle} días</b> sin practicar. No pasa nada: tu ruta y tu progreso siguen donde los dejaste. Una lección de 5 minutos y recuperas el ritmo.",
        "steps": ["Abre Talvo.", "Retoma tu ruta justo donde la dejaste.", "Activa los recordatorios para que no se te pase."],
        "cta": "Volver a practicar", "path": "/",
    },
}


def _email_render(kind, name, email, idle=0, streak=0):
    """Devuelve (asunto, html, texto)."""
    from html import escape
    from urllib.parse import quote
    k = _EMAIL_KINDS[kind]
    nm = escape((name or "").strip().split(" ")[0].capitalize() or "amigo")
    fmt = {"name": nm, "idle": int(idle or 0), "email_q": quote(email or ""),
           "streak": (f"Llevas <b>{int(streak)} días</b> de racha: ¡cuídala!" if streak and int(streak) >= 2 else "")}
    subject = k["subject"].format(**fmt)
    title = k["title"].format(**fmt)
    body = k["body"].format(**fmt)
    link = APP_URL + k["path"].format(**fmt)
    gif = f"{APP_URL}/email/pq-{kind}.gif"
    steps = "".join(
        f'<tr><td width="34" valign="top" style="padding:7px 0"><div style="width:26px;height:26px;border-radius:13px;background:#3ee8ff;color:#04101a;'
        f'font:700 13px/26px Arial,sans-serif;text-align:center">{i}</div></td>'
        f'<td style="padding:8px 0 8px 8px;font:15px/1.5 Arial,sans-serif;color:#d6e0f5">{s}</td></tr>' for i, s in enumerate(k["steps"], 1))
    unsub = _unsub_url(email)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#04060d">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#04060d">{escape(k['pre'])}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#04060d" style="background:#04060d"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#0a1022;border:1px solid #1e2b4f;border-radius:18px;overflow:hidden">
<tr><td style="padding:0"><img src="{gif}" width="600" alt="Palanqueta" style="display:block;width:100%;max-width:600px;height:auto;border:0"></td></tr>
<tr><td style="padding:26px 30px 8px"><div style="font:700 12px Arial,sans-serif;letter-spacing:.14em;color:#3ee8ff;text-transform:uppercase">Talvo English</div>
<h1 style="margin:8px 0 12px;font:700 26px/1.2 Arial,sans-serif;color:#ffffff">{title}</h1>
<p style="margin:0;font:16px/1.6 Arial,sans-serif;color:#b8c5de">{body}</p></td></tr>
<tr><td style="padding:10px 30px 4px"><table role="presentation" cellpadding="0" cellspacing="0" width="100%">{steps}</table></td></tr>
<tr><td align="center" style="padding:18px 30px 30px"><a href="{link}" style="display:inline-block;background:#3ee8ff;background-image:linear-gradient(90deg,#3ee8ff,#7c78ff);color:#04101a;text-decoration:none;font:700 16px Arial,sans-serif;padding:15px 34px;border-radius:12px">{k['cta']} &rarr;</a>
<div style="margin-top:12px;font:12px Arial,sans-serif;color:#6f7f9c">¿No abre el botón? Copia este enlace: <a href="{link}" style="color:#3ee8ff">{escape(link)}</a></div></td></tr>
<tr><td style="padding:16px 30px 24px;border-top:1px solid #1e2b4f;font:12px/1.6 Arial,sans-serif;color:#6f7f9c">Recibes este correo porque creaste una cuenta en Talvo English. Te escribimos pocas veces y nunca más de uno cada tres días.<br>¿Ya no quieres recordatorios? <a href="{unsub}" style="color:#93a3bd">Darme de baja</a>.</td></tr>
</table></td></tr></table></body></html>"""
    text = f"{title}\n\n{re.sub('<[^>]+>', '', body)}\n\n{k['cta']}: {link}\n\nDarme de baja: {unsub}"
    return subject, html, text


def _send_email(to, subject, html, text=""):
    """Envía un correo por HTTPS. Devuelve (ok, detalle)."""
    try:
        if EMAIL_WEBHOOK_URL and EMAIL_WEBHOOK_SECRET:
            r = requests.post(EMAIL_WEBHOOK_URL, json={"secret": EMAIL_WEBHOOK_SECRET, "to": to, "subject": subject,
                                                       "html": html, "text": text, "name": "Palanqueta · Talvo English"}, timeout=30)
            try:
                d = r.json()
            except Exception:
                return False, f"webhook {r.status_code}"
            return bool(d.get("ok")), str(d.get("error") or d.get("left") or "")
        if BREVO_API_KEY and EMAIL_FROM:
            r = requests.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": BREVO_API_KEY, "accept": "application/json"},
                              json={"sender": {"name": "Palanqueta · Talvo English", "email": EMAIL_FROM}, "to": [{"email": to}],
                                    "subject": subject, "htmlContent": html, "textContent": text}, timeout=30)
            return r.status_code in (200, 201), f"brevo {r.status_code}"
    except Exception as exc:
        return False, type(exc).__name__
    return False, "sin proveedor"


def _email_pick(created, confirmed, prof, has_push, logs, now_mx):
    """Decide qué correo (si alguno) toca. logs = [(kind, datetime)]. Devuelve (kind, idle, streak) o None."""
    if len(logs) >= 6:
        return None
    if logs and (now_mx - max(dt for _k, dt in logs)).total_seconds() < 3 * 86400 - 3600:
        return None  # máximo un correo cada 3 días
    cnt = lambda k: sum(1 for kk, _ in logs if kk == k)
    last_of = lambda k: max([dt for kk, dt in logs if kk == k] or [None]) if cnt(k) else None
    age = (now_mx - created).total_seconds() / 86400
    if not confirmed:
        if cnt("verify") == 0 and age >= 0.8:
            return ("verify", 0, 0)
        if cnt("verify") == 1 and age >= 3:
            return ("verify", 0, 0)
        return None
    if not prof or not has_active_access(prof):
        return None
    last = prof.get("last_activity_date")
    if not last:
        if cnt("start") == 0 and age >= 1:
            return ("start", 0, 0)
        if cnt("start") == 1 and age >= 4:
            return ("start", 0, 0)
        return None
    try:
        idle = (now_mx.date() - datetime.fromisoformat(str(last)[:10]).date()).days
    except Exception:
        return None
    streak = int(prof.get("streak_days") or 0) if idle <= 1 else 0
    if has_push:
        return None  # ya recibe notificaciones: el correo sería de más
    if cnt("nopush") == 0 and idle >= 1:
        return ("nopush", idle, streak)
    if cnt("nopush") == 1 and (now_mx - last_of("nopush")).days >= 10:
        return ("nopush", idle, streak)
    if idle >= 4 and cnt("comeback") < 3 and (cnt("comeback") == 0 or (now_mx - last_of("comeback")).days >= 7):
        return ("comeback", idle, 0)
    return None


@app.post("/api/email/cron")
def email_cron():
    """Correos de recordatorio para quien no confirmó, no ha practicado o no activó notificaciones.
    ?dry=1 solo lista a quién se enviaría; ?force=1 ignora la ventana de horas."""
    import hmac
    from zoneinfo import ZoneInfo
    if not CRON_SECRET or not hmac.compare_digest(request.headers.get("X-Cron-Secret", ""), CRON_SECRET):
        return json_error("No autorizado.", 401)
    dry = request.args.get("dry") == "1"
    force = request.args.get("force") == "1"
    tz = ZoneInfo("America/Mexico_City")
    now_mx = datetime.now(timezone.utc).astimezone(tz)
    if not force and now_mx.hour not in EMAIL_HOURS:
        return jsonify({"ok": True, "enviados": 0, "motivo": "fuera de horario"})
    if not dry and not _email_ready():
        return json_error("Falta configurar el envío de correos (EMAIL_WEBHOOK_URL o BREVO_API_KEY).", 503)
    if not supabase_admin:
        return json_error("Supabase no está configurado.", 500)
    try:
        users = _list_auth_users(supabase_admin)
        profs = {p["id"]: p for p in (supabase_admin.table("profiles").select(
            "id,email,username,streak_days,last_activity_date,is_subscribed,trial_ends_at").limit(5000).execute().data or [])}
        push_users = {r["user_id"] for r in (supabase_admin.table("push_subscriptions").select("user_id").eq("enabled", True).execute().data or []) if r.get("user_id")}
        logs = {}
        for r in (supabase_admin.table("email_log").select("email,kind,sent_at").limit(20000).execute().data or []):
            try:
                dt = datetime.fromisoformat(str(r["sent_at"]).replace("Z", "+00:00")).astimezone(tz)
            except Exception:
                continue
            logs.setdefault((r.get("email") or "").lower(), []).append((r.get("kind"), dt))
        optout = {(r.get("email") or "").lower() for r in (supabase_admin.table("email_optout").select("email").limit(20000).execute().data or [])}
    except Exception as exc:
        return json_error(_err_log("No se pudieron leer los datos", exc), 500)

    plan = []
    for u in users:
        email = (getattr(u, "email", "") or "").lower()
        if not email or email in optout:
            continue
        try:
            ca = getattr(u, "created_at", None)
            created = (ca if isinstance(ca, datetime) else datetime.fromisoformat(str(ca).replace("Z", "+00:00"))).astimezone(tz)
        except Exception:
            continue
        confirmed = bool(getattr(u, "email_confirmed_at", None))
        pick = _email_pick(created, confirmed, profs.get(str(u.id)), str(u.id) in push_users, logs.get(email, []), now_mx)
        if pick:
            prof = profs.get(str(u.id)) or {}
            plan.append({"uid": str(u.id), "email": email, "name": prof.get("username") or email.split("@")[0],
                         "kind": pick[0], "idle": pick[1], "streak": pick[2]})
    plan = plan[:EMAIL_MAX_PER_RUN]
    if dry:
        return jsonify({"ok": True, "dry": True, "usuarios": len(users), "se_enviarian": [{"email": p["email"][:3] + "…", "kind": p["kind"]} for p in plan]})
    sent, failed = 0, 0
    for p in plan:
        subject, html, text = _email_render(p["kind"], p["name"], p["email"], p["idle"], p["streak"])
        ok, detail = _send_email(p["email"], subject, html, text)
        if ok:
            sent += 1
            try:
                supabase_admin.table("email_log").insert({"user_id": p["uid"], "email": p["email"], "kind": p["kind"]}).execute()
            except Exception:
                pass
        else:
            failed += 1
            if detail and ("quota" in detail.lower() or "límite" in detail.lower() or "limit" in detail.lower()):
                break  # cuota diaria agotada: se reintenta mañana
    return jsonify({"ok": True, "usuarios": len(users), "enviados": sent, "fallidos": failed})


@app.post("/api/email/test")
def email_test():
    """Solo admin: te manda a ti mismo un ejemplo de cada correo (?kind=verify|start|nopush|comeback)."""
    user, error = authenticated_user(require_subscription=False)
    if error:
        return json_error(error[0], error[1])
    if not is_admin_user(user):
        return json_error("Solo el administrador.", 403)
    ok, _w = _rate_hit((user.id, "email-test"), 10, 3600)
    if not ok:
        return json_error("Demasiadas pruebas. Espera un momento.", 429)
    kind = (request.get_json(silent=True) or {}).get("kind")
    kinds = [kind] if kind in _EMAIL_KINDS else list(_EMAIL_KINDS)
    if not _email_ready():
        return json_error("Falta configurar el envío de correos (EMAIL_WEBHOOK_URL o BREVO_API_KEY).", 503)
    sent = 0
    for k in kinds:
        subject, html, text = _email_render(k, user.email.split("@")[0], user.email, idle=5, streak=4)
        ok2, _d = _send_email(user.email, "[Prueba] " + subject, html, text)
        sent += 1 if ok2 else 0
    return jsonify({"ok": True, "enviados": sent, "de": len(kinds)})


@app.get("/api/email/unsub")
def email_unsub():
    import hmac
    from html import escape
    e = (request.args.get("e") or "").strip().lower()[:254]
    ok = bool(e) and hmac.compare_digest(request.args.get("t", ""), _unsub_token(e))
    if ok and supabase_admin:
        try:
            supabase_admin.table("email_optout").upsert({"email": e}, on_conflict="email").execute()
        except Exception:
            ok = False
    msg = ("Listo, ya no recibirás recordatorios por correo." if ok else "El enlace no es válido o caducó.")
    page = (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Talvo English</title>'
            f'<body style="margin:0;background:#04060d;color:#f2f6ff;font-family:Arial,sans-serif;display:grid;place-items:center;min-height:100vh;text-align:center;padding:24px">'
            f'<div><img src="{APP_URL}/palanqueta-asoma.webp" width="120" alt=""><h2>{escape(msg)}</h2>'
            f'<p style="color:#93a3bd">Puedes seguir practicando cuando quieras.</p>'
            f'<a href="{APP_URL}" style="display:inline-block;margin-top:10px;background:#3ee8ff;color:#04101a;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700">Ir a Talvo English</a></div>')
    return Response(page, mimetype="text/html")


@app.get("/")
def root():
    return jsonify({"ok": True, "service": "Talvo English API"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
