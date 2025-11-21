from dotenv import load_dotenv
load_dotenv()

import logging, sys
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

import os, hmac, time
from collections import deque, defaultdict
from flask import Flask, request, abort, jsonify, g
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

# load key from .env, if missing => stop (no key = no api)
SERVER_API_KEY = (os.getenv("SERVER_API_KEY") or "").strip()
if not SERVER_API_KEY:
    # owasp: dont run w/o auth secrets (REST Sec) https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html  :contentReference[oaicite:0]{index=0}
    raise RuntimeError("SERVER_API_KEY missing")  

app = Flask(__name__)

# trust proxy headers from nginx only, set counts so not spoofable
# docs: werkzeug ProxyFix https://werkzeug.palletsprojects.com/en/stable/middleware/proxy_fix/  
# # and guidance https://werkzeug.palletsprojects.com/en/stable/deployment/proxy_fix/
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)  # behind 1 proxy  :contentReference[oaicite:1]{index=1}

# dont allow big bodies (bombs). keep same as nginx
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20mb

# only allow cors from my allowed frontends (not *), strict origins
ALLOWED_ORIGINS = [
    "https://www.traustdumir.de/",    
    "http://localhost:5173",
]

# owasp: limit origins, https only https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html  :contentReference[oaicite:2]{index=2}
CORS(app, resources={r"/*": {
    "origins": ALLOWED_ORIGINS,
    "methods": ["GET","POST","OPTIONS"],
    "allow_headers": ["Authorization","Content-Type"],
    "max_age": 86400
}}, supports_credentials=False)  

# constant-time compare = no timing leak on tokens
# docs: hmac.compare_digest https://docs.python.org/3/library/hmac.html#hmac.compare_digest 
# # (also explainer) https://sqreen.github.io/DevelopersSecurityBestPractices/timing-attack/python
def _eq(a, b): return hmac.compare_digest(a.encode(), b.encode())  # use this not ==  :contentReference[oaicite:3]{index=3}

# tiny in-mem rate limit (per token+ip). not perfect but cheap
# owasp/api rate limit baseline idea https://cheatsheetseries.owasp.org/  
# # and api top10 https://apisecurity.io/encyclopedia/content/owasp/owasp-api-security-top-10-cheat-sheet.htm
_rl = defaultdict(deque)
def ratelimit(key: str, limit:int=5, per_seconds:int=1):
    now = time.time()
    dq = _rl[key]
    while dq and dq[0] <= now - per_seconds: dq.popleft()
    if len(dq) >= limit: abort(429)
    dq.append(now)

@app.before_request
def gate():
    # skip auth for health/root + preflight (cors)
    if request.method == "OPTIONS" or request.path in ("/", "/health"):
        return

    # must be https at proxy, else reject (mixed proto bad)
    # why: trust https only (HSTS etc) mdn https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security
    #https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-Proto
    if request.headers.get("X-Forwarded-Proto") not in (None, "", "https"):
        abort(400) 

    # bearer token check
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        abort(401)
    token = auth[7:].strip()
    if not _eq(token, SERVER_API_KEY):
        abort(401)

    # rate limit per token + client ip (from proxy)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    g.client_id = token
    ratelimit(f"{g.client_id}:{ip}", limit=5, per_seconds=1)

    # only accept json or multipart for write-ish methods
    # owasp: content-type strict, avoid unexpected parsing
    if request.method in ("POST","PUT","PATCH"):
        ct = (request.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ct not in ("application/json","multipart/form-data"):
            abort(415)

@app.after_request
def sec_headers(r):
    # basic sec hdrs for apis. mdn ref list: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers
    r.headers["X-Content-Type-Options"] = "nosniff"      
    r.headers["X-Frame-Options"] = "DENY"                
    r.headers["Referrer-Policy"] = "no-referrer"         
    r.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"  
    r.headers["Content-Security-Policy"] = "default-src 'none'"  # api no content
    r.headers["Server"] = "api"  # hide stack
    return r  #  :contentReference[oaicite:5]{index=5}

@app.errorhandler(HTTPException)
def json_http(e):
    # always json err, no html stack traces
    return jsonify(ok=False, error={"code": e.code, "name": e.name, "message": e.description}), e.code

@app.errorhandler(Exception)
def json_500(e):
    app.logger.exception("Unhandled exception", exc_info=e) 
    return jsonify(ok=False, error={"code": 500, "name": "Internal Server Error"}), 500

@app.get("/")
def index():
    return "SERVER LÄUFT..."

@app.get("/health")
def health():
    return jsonify(ok=True)

# quick helper for json input check (keys present + size)
# owasp rest: validate input, schema if possible https://opencre.org/node/standard/OWASP%20Cheat%20Sheets/section/REST%20Security%20Cheat%20Sheet
def require_json(keys: list[str], max_bytes: int = 256_000):
    if request.content_length and request.content_length > max_bytes:
        abort(413)
    data = request.get_json(silent=True) # DOC: Silence mimetype and parsing errors, and return None instead.
    if not isinstance(data, dict): #muss dict sein 
        abort(400)
    for k in keys:
        if k not in data:#muss dict sein rec
            abort(400)
    return data  

#import blueprints (keep modular) -> endpoitins
from tts_api import tts_blueprint
from gwdg_api import gwdg_blueprint
from stt_api import stt_blueprint

# IMMER VOR PUSH DIE PUNKTE REIN SONST BREAKT ALLES YALLAH GIB
# IMMER VOR PUSH DIE PUNKTE REIN SONST BREAKT ALLES YALLAH GIB
# IMMER VOR PUSH DIE PUNKTE REIN SONST BREAKT ALLES YALLAH GIB
""" 
from .tts_api import tts_blueprint
from .gwdg_api import gwdg_blueprint
from .stt_api import stt_blueprint 
"""

app.register_blueprint(tts_blueprint, url_prefix="/tts")
app.register_blueprint(gwdg_blueprint, url_prefix="/gwdg")
app.register_blueprint(stt_blueprint, url_prefix="/stt")

if __name__ == "__main__":
    # local only, prod goes via nginx+gunicorn (see proxyfix)
    app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=True)
