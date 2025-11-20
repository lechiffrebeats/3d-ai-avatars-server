from flask import Blueprint, request, jsonify, abort
import os, io, wave, re, tempfile, base64, logging, traceback, threading
from functools import lru_cache
from werkzeug.exceptions import HTTPException
import torch, torch.jit as _jit
from piper.voice import PiperVoice

TORCH_NUM_THREADS = int(os.getenv("TORCH_NUM_THREADS", "1"))
BFA_GROUPS = bool(int(os.getenv("BFA_GROUPS", "0")))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("TORCHAUDIO_USE_FFMPEG", "0")
os.environ.setdefault("TORCHAUDIO_USE_SOUNDFILE", "1")

torch.set_num_threads(TORCH_NUM_THREADS)
try: torch.set_num_interop_threads(1)
except Exception: pass

_real_torch_load = torch.load
def _torch_load_cpu(*a, **k):
    k.setdefault("map_location", torch.device("cpu"))
    return _real_torch_load(*a, **k)
torch.load = _torch_load_cpu

_orig_jit_load = _jit.load
def _jit_load_cpu(*a, **k):
    k.setdefault("map_location", torch.device("cpu"))
    return _orig_jit_load(*a, **k)
_jit.load = _jit_load_cpu

tts_blueprint = Blueprint("tts_api", __name__)
log = logging.getLogger("tts")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

try:
    from german_transliterate.core import GermanTransliterate
    _GT = GermanTransliterate()
except Exception:
    _GT = None

_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_ROOT = os.environ.get("HISTAR_MODEL_DIR", os.path.join(_BASE, "models"))
VOICE_DIR = os.environ.get("PIPER_VOICE_DIR", os.path.join(MODEL_ROOT, "piper_voices"))
BFA_DIR = os.environ.get("BFA_DIR", os.path.join(MODEL_ROOT, "bfa"))

# https://huggingface.co/rhasspy/piper-voices/tree/main/de/de_DE/kerstin/low
# "de_DE-eva_k-x_low.onnx"
PIPER_MODELS = {
    "de": {"male": "de_DE-thorsten-high.onnx", "female": "de_DE-kerstin-low.onnx"},
    "en": {"male": "en_US-ryan-high.onnx", "female": "en_US-amy-medium.onnx"},
}
BFA_BY_LANG = {
    "en": os.getenv("BFA_EN", "en_libri1000_uj01d_e199_val_GER=0.2307.ckpt"),
    "de": os.getenv("BFA_DE", "multi_MLS8_uh02_e36_val_GER=0.2334.ckpt"),
}
BFA_FALLBACK = os.getenv("BFA_FALLBACK", "multi_mswc38_ug20_e59_val_GER=0.5611.ckpt")

MAX_TEXT_CHARS = 4000
MAX_AUDIO_BYTES = 5_000_000
DEFAULT_LANG = "de"
DEFAULT_GENDER = "male"

_VOICE_LOCKS = {}
_VOICE_LOCKS_GUARD = threading.Lock()
def _voice_lock_for(path: str) -> threading.Lock:
    with _VOICE_LOCKS_GUARD:
        lock = _VOICE_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _VOICE_LOCKS[path] = lock
        return lock

def _ensure_espeak_env():
    if not os.environ.get("PHONEMIZER_ESPEAK_PATH"):
        if os.path.exists("/usr/bin/espeak-ng"):
            os.environ["PHONEMIZER_ESPEAK_PATH"] = "/usr/bin/espeak-ng"
    if not os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
        cand = "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"
        if os.path.exists(cand):
            os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = cand
    if not os.environ.get("PHONEMIZER_ESPEAK_DATA_PATH"):
        cand = "/usr/lib/x86_64-linux-gnu/espeak-ng-data"
        if os.path.isdir(cand):
            os.environ["PHONEMIZER_ESPEAK_DATA_PATH"] = cand

@lru_cache(maxsize=1024)
def _normalize_text(text, lang):
    s = (text or "").strip()
    if _GT and str(lang).lower().startswith("de"):
        try: s = _GT.transliterate(s)
        except Exception: pass
    return re.sub(r"[ \t]+", " ", s)

def _resolve_path(base_dir, name_or_path):
    return name_or_path if os.path.isabs(name_or_path) else os.path.join(base_dir, name_or_path)

def _select_voice(lang, gender):
    l = "en" if str(lang).lower().startswith("en") else "de"
    g = "female" if str(gender).lower().startswith("f") else "male"
    onnx = _resolve_path(VOICE_DIR, PIPER_MODELS[l][g])
    if not os.path.exists(onnx): raise FileNotFoundError(onnx)
    cfg = onnx + ".json"
    alt = os.path.splitext(onnx)[0] + ".json"
    if not os.path.exists(cfg) and os.path.exists(alt): cfg = alt
    if not os.path.exists(cfg): cfg = None
    return onnx, cfg

@lru_cache(maxsize=8)
def _piper(onnx_path, cfg_path):
    if cfg_path: return PiperVoice.load(onnx_path, config_path=cfg_path)
    return PiperVoice.load(onnx_path)

def _synthesize_wav(text, onnx_path, cfg_path):
    v = _piper(onnx_path, cfg_path)
    lock = _voice_lock_for(onnx_path)
    bio = io.BytesIO()
    with lock:
        if hasattr(v, "synthesize_wav"):
            with wave.open(bio, "wb") as wf:
                try: v.synthesize_wav(text, wf, syn_config=None, set_wav_format=True)
                except TypeError: v.synthesize_wav(text, wf)
        elif hasattr(v, "synthesize"):
            with wave.open(bio, "wb") as wf:
                v.synthesize(text, wf)
        else:
            raise AttributeError("PiperVoice unsupported")
    wav = bio.getvalue()
    with wave.open(io.BytesIO(wav), "rb") as wf2:
        sr = wf2.getframerate(); frames = wf2.getnframes()
    return wav, int(sr or 22050), frames / float(sr or 22050)

def _lang_code(lang):
    l = str(lang).lower()
    return "en-us" if l.startswith("en") else ("de" if l.startswith("de") else "en-us")

def _resolve_bfa_model(name):
    p = _resolve_path(BFA_DIR, name)
    return p if os.path.exists(p) else name

@lru_cache(maxsize=4)
def _aligner(model_name, lang_code):
    _ensure_espeak_env()
    from bournemouth_aligner import PhonemeTimestampAligner
    m = _resolve_bfa_model(model_name)
    return PhonemeTimestampAligner(model_name=m, lang=lang_code, duration_max=10, device="cpu")

def _bootstrap():
    try:
        onnx,cfg = _select_voice("de","male"); _synthesize_wav("Hallo.", onnx, cfg)
    except Exception as e: log.warning("warmup de: %s", e)
    try:
        onnx,cfg = _select_voice("en","male"); _synthesize_wav("Hello.", onnx, cfg)
    except Exception as e: log.warning("warmup en: %s", e)
    try:
        _ = _aligner(BFA_BY_LANG["de"], "de"); _ = _aligner(BFA_BY_LANG["en"], "en-us")
    except Exception as e: log.warning("aligner warmup: %s", e)

_bootstrap()

@tts_blueprint.errorhandler(HTTPException)
def _http_error(e):
    return jsonify({"ok": False, "error": e.name, "status": e.code, "description": e.description}), e.code

@tts_blueprint.errorhandler(Exception)
def _unhandled_error(e):
    log.error("Unhandled exception", exc_info=e)
    return jsonify({"ok": False, "error_type": type(e).__name__, "error_message": str(e), "traceback": traceback.format_exc()}), 500

@tts_blueprint.route("/healthz", methods=["GET"])
def healthz():
    checks = {}
    ok = True
    for l in ("de","en"):
        for g in ("male","female"):
            k = f"piper_{l}_{g}"
            try:
                onnx,cfg = _select_voice(l,g); _ = _piper(onnx,cfg); checks[k]=True
            except Exception as e:
                checks[k]=str(e); ok=False
    try:
        _ = _aligner(BFA_BY_LANG["de"], "de"); checks["aligner_de"]=True
    except Exception as e:
        checks["aligner_de"]=str(e); ok=False
    try:
        _ = _aligner(BFA_BY_LANG["en"], "en-us"); checks["aligner_en"]=True
    except Exception as e:
        checks["aligner_en"]=str(e); ok=False
    return jsonify(ok=ok, checks=checks)

@tts_blueprint.route("/tts_align", methods=["POST"])
def tts_align():
    if not request.is_json: abort(400, description="Content-Type must be application/json")

    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()
    lang = (d.get("lang") or DEFAULT_LANG).lower()
    gender = (d.get("gender") or DEFAULT_GENDER).lower()
    bfa_override = (d.get("bfa_model") or "").strip()

    if not text: abort(400, description="No text provided")
    if len(text) > MAX_TEXT_CHARS: abort(413, description="text too long")
    if lang[:2] not in ("de","en"): abort(400, description="Unsupported lang")
    if gender not in ("male","female"): abort(400, description="Unsupported gender")

    tnorm = _normalize_text(text, lang)
    onnx,cfg = _select_voice(lang, gender)
    wav, sr, dur = _synthesize_wav(tnorm, onnx, cfg)

    if len(wav) > MAX_AUDIO_BYTES: abort(413, description="audio too large")

    lang_code = _lang_code(lang)
    model_name = bfa_override or BFA_BY_LANG.get(lang[:2], BFA_FALLBACK)
    align = _aligner(model_name, lang_code)
    tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=tmp_dir) as tmp:
        tmp.write(wav); wav_path = tmp.name
    try:
        audio_wav = align.load_audio(wav_path, backend="soundfile")
        with torch.inference_mode():
            ts = align.process_sentence(
                tnorm, audio_wav,
                ts_out_path=None,
                extract_embeddings=False,
                vspt_path=None,
                do_groups=BFA_GROUPS,
                debug=False
            )
        segs = []
        seg0 = ((ts or {}).get("segments") or [None])[0]
        if seg0:
            for p in seg0.get("phoneme_ts") or []:
                segs.append({
                    "phoneme": p.get("phoneme_label"),
                    "start": float(p.get("start_ms", 0.0))/1000.0,
                    "end": float(p.get("end_ms", 0.0))/1000.0,
                    "confidence": float(p.get("confidence", 0.0)),
                })
        return jsonify(
            ok=True,
            language=("en" if lang.startswith("en") else "de"),
            gender=gender,
            audio_mime="audio/wav",
            sample_rate=sr,
            phonemes=segs,
            timing_meta={
                "source":"bfa",
                "model":_resolve_bfa_model(model_name),
                "lang_code":lang_code,
                "audio_seconds":dur,
                "phoneme_count":len(segs),
                "do_groups":BFA_GROUPS,
                "torch_threads": TORCH_NUM_THREADS
            },
            audio_base64=base64.b64encode(wav).decode("ascii"),
            normalized_text=tnorm,
            raw=ts
        )
    finally:
        try: os.unlink(wav_path)
        except Exception: pass
