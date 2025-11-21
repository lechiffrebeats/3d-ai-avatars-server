import os, json
from flask import Blueprint, request, Response
from dotenv import load_dotenv
import requests

load_dotenv()
gwdg_blueprint = Blueprint("gwdg_api", __name__)

BASE_URL = os.getenv("LLM_BASE_URL", "https://chat-ai.academiccloud.de/v1").rstrip("/")
API_KEY  = (os.getenv("LLM_API_KEY") or "").strip()

MODEL_RAG = "meta-llama-3.1-8b-rag"
MODEL_FAST_AF = "qwen3-32b"
ARCANA_ID_DEFAULT = "ramon.desmit/uni_bremen_informatik_master-8cdab04e-76ae-49c9-8e16-39ca87339be0"

MAX_MESSAGES_AFTER_SYSTEM = 20
MAX_CONTENT_CHARS_PER_MSG = 1200
MAX_PROMPT_CHARS = 1000
REQ_TIMEOUT = 60

# ---------- helpers ----------
def _sanitize_text(s, max_len=MAX_CONTENT_CHARS_PER_MSG):
    t = (s if isinstance(s, str) else str(s or "")).strip()
    return t[:max_len] if len(t) > max_len else t

def _sanitize_conversation(conv):
    if not isinstance(conv, list):
        return []
    cleaned = []
    for m in conv:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            cleaned.append({"role": role, "content": _sanitize_text(content)})
    return cleaned[-MAX_MESSAGES_AFTER_SYSTEM:]

def _system_rules(lang: str) -> str:
    lang = (lang or "Deutsch").strip()[:20]
    return f"""
        BASE SYSTEM PROMPT START

        ROLE
        - Du bist ein professioneller, vertrauenswürdiger 3D-KI-Avatar NUR für den Master Informatik (M.Sc.) an der Universität Bremen.
        - Alles andere ignorieren (andere Unis/Fächer/generelle Regeln).

        KNOWLEDGE USE
        - IMMER Arcana-RAG nutzen. Nie halluzinieren.
        - Wenn unsicher führe online recherche durch.
        - Wenn RAG keine Antwort hat: kurz antworten und an offizielle Stellen der Uni Bremen verweisen (Prüfungsamt, FB3, Studienzentrum).
        - Jede Antwort bezieht sich auf den Master Informatik an der Uni Bremen.
        - Some important infos you might be asked: 
            1. Benötigte Kreditpunkte zur Anmeldung der Masterarbeit: 60 Credit Points
            2. How many credit points do I need to register the master’s thesis? AWNSER: 60 Credit Points

        MISC: 
        - If asked for a joke make it university of bremen, computer science related.

        STYLE
        - Ton: professionell, ruhig, freundlich-neutral.
        - Smalltalk erlaubt, leicht humorvoll, aber nach 1–2 Sätzen zurück zum Master Informatik lenken.

        GREETINGS / SMALLTALK HANDLING
        - Bei Grußworten wie „hi“, „hey“, „hallo“: freundlich begrüßen, eine knappe Hilfe-Option anbieten (z. B. Bewerbungsfristen, CP, Masterarbeit), dann Frage stellen.
        - Beispiel (nur Stil, nicht wörtlich übernehmen):
        „Hallo! Ich helfe gern rund um den Master Informatik in Bremen. Möchtest du etwas zu Bewerbungsfristen oder zur Masterarbeit wissen?“

        LANGUAGE
        - ALWAYS AWNSER IN WHATEVER THIS PARAM SAYS (de: deutsch, en: englisch): {lang}.

        OUTPUT CONTRACT (VALID JSON, NO MARKDOWN, NO EXTRA KEYS)
        {{
        "reply": "≤30 Wörter , keine Ziffern.",
        "animation": "Ein gültiges Animationstoken",
        "expression": "Ein gültiges Expressionstoken"
        }}

        STRICT RULES (HARD)
        - Immer gültiges JSON zurückgeben.
        - „reply“ ≤ 30 Wörter, ohne Ziffern (Zahlen ausschreiben).
        - Bei Unsicherheit: gültiges JSON und kurzer Verweis auf zuständige Stelle der Uni Bremen.
        - Keine Aussagen zu anderen Studiengängen/Unis.

        BASE SYSTEM PROMPT END
        """.strip()


def _sys_message(lang: str):
    return {"role": "system", "content": _system_rules(lang)}

# ---------- route ----------
@gwdg_blueprint.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return Response('{"error":"LLM_API_KEY missing"}', status=500, mimetype="application/json")
    if not request.is_json:
        return Response('{"error":"content-type must be application/json"}', status=415, mimetype="application/json")

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return Response('{"error":"bad json"}', status=400, mimetype="application/json")

    conversation = _sanitize_conversation(data.get("conversation"))
    prompt = _sanitize_text(data.get("prompt", ""), MAX_PROMPT_CHARS)
    lang = _sanitize_text(data.get("lang", "Deutsch"), 20)
    use_full = bool(data.get("use_full", False))

    messages = [_sys_message(lang)] + conversation
    if prompt:
        messages.append({"role": "user", "content": prompt})
    model_current = MODEL_RAG if use_full else MODEL_FAST_AF

    payloadBase = {
        "model": model_current,
        "messages": messages,
        "temperature": 0.0,
        "top_p": 0.05,
        "max_tokens": 300,
        "max_completion_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    if use_full:
        payloadBase["arcana"] = {
            "id": ARCANA_ID_DEFAULT
        }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        upstream = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payloadBase,
            timeout=REQ_TIMEOUT
        )
    except requests.RequestException as e:
        body = json.dumps({"error": "upstream network error", "detail": str(e)[:200]})
        return Response(body, status=502, mimetype="application/json")

    content_type = upstream.headers.get("content-type", "application/json")
    return Response(upstream.text, status=upstream.status_code, mimetype=content_type)
