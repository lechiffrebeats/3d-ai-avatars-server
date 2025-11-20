# PythonServer/stt_api.py
import os, time, tempfile
from flask import Blueprint, request, jsonify, abort
from faster_whisper import WhisperModel

stt_blueprint = Blueprint("stt_api", __name__)

CPU_THREADS = int(os.getenv("STT_CPU_THREADS", "4"))

# model config from env (keine client inputs hier!!)
STT_MODEL = os.getenv("STT_MODEL", "base")  
STT_DEVICE = os.getenv("STT_DEVICE", "cpu")         
STT_COMPUTE = os.getenv("STT_COMPUTE_TYPE", "int8") 
STT_BEAM = int(os.getenv("STT_BEAM_SIZE", "5"))
STT_DOWNLOAD = os.getenv("STT_DOWNLOAD_DIR", "/opt/histar/models/whisper")

# only common browser encodings erlaubt (kein exot)
# OWASP file upload rulez: allowlist only https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
ALLOWED_MIME = {
       "audio/webm", "audio/webm;codecs=opus",
       "audio/wav",
}

_model = None
def get_model():
    global _model
    if _model is None:
        os.makedirs(STT_DOWNLOAD, exist_ok=True)  # sicherstellen ordner exisitiert
        _model = WhisperModel(
            STT_MODEL,
            device=STT_DEVICE,
            compute_type=STT_COMPUTE,
            download_root=STT_DOWNLOAD,
            cpu_threads=CPU_THREADS
        )
    return _model

@stt_blueprint.get("/")
def info():
    # simple info endpoint (kein secret hier zeigen!!!)
    return jsonify(ok=True, model=STT_MODEL, device=STT_DEVICE, compute_type=STT_COMPUTE)

@stt_blueprint.post("/transcribe")
def transcribe():
    # AUTH wird global im server.py gemacht (before_request), also hier schon enforced
    if "audio" not in request.files:
        abort(400, description="Missing file field 'audio' (multipart/form-data).")

    f = request.files["audio"]

    # MIME TYPE allowlist check (NICHT auf filename vertrauen!!)
    # source: flask docs upload, mdn mimetype https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types
    content_type = (f.mimetype or "").lower()
    if content_type not in ALLOWED_MIME:
        abort(415, description=f"Unsupported media type: {content_type}")

    # optional sprache, nur kurzstring
    lang = (request.form.get("language") or "").strip() or None
    if lang and len(lang) > 5:  # cap length, dont trust input
        lang = lang[:5]

    # Save to temp file (not in /tmp without cleanup!!) 
    # OWASP: save outside webroot, random name, delete after use
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        # limit size check nochmal (nginx + flask global already do but defense-in-depth)
        f.seek(0, 2); size = f.tell(); f.seek(0)
        if size > 10 * 1024 * 1024:  # 10mb max
            abort(413, description="File too large")

        f.save(tmp.name)
        tmp.flush()

        t0 = time.time()
        segments, info = get_model().transcribe(
            tmp.name,
            language=lang,
            task="transcribe",
            beam_size=STT_BEAM,
            vad_filter=True,
            word_timestamps=False,
            # num_workers=int(os.getenv("STT_NUM_WORKERS", "1")),
        )
        # glue all seg texts
        text = "".join(seg.text for seg in segments).strip()

        return jsonify(ok=True, text=text, language=info.language, time_ms=int((time.time()-t0)*1000))
    finally:
        try:
            tmp.close()
        except Exception:
            pass
        try:
            os.unlink(tmp.name)  # cleanup file, kein leak
        except Exception:
            pass
