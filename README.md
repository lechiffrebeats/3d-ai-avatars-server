# **DoYouTrustMe – 3D AI Avatar Chatbot (Server)**  
Python backend for the *DoYouTrustMe – 3D AI Avatar Chatbot* research project.

Provides:
- **LLM access** (GWDG RAG Container or local Llama 3.1)
- **STT** (Whisper)
- **TTS** (Piper)
- **Viseme/phoneme extraction** for 3D lip-sync
- Lightweight REST API used by the SvelteKit frontend

> ⚠️ Research prototype – not intended for production.

---

## 🧩 Architecture (Short)

```

SvelteKit Client → SvelteKit Proxy → THIS_SERVER → LLM / STT / TTS

````

Backend stack:
- Flask (API)
- Piper TTS
- Whisper (CPU/GPU)
- Phoneme → Viseme (BFA + phonemizer)
- Optional: Gunicorn + Nginx on Linux

---

## 🔧 Required Environment Variables

Create a `.env` file:

```bash
PIPER_VOICE_DIR=./voices
SERVER_API_KEY=
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=meta-llama-3.1-8b-rag
LLM_RAG_ID=
````

Optional:

```bash
WHISPER_MODEL=base
PIPER_MODEL=de_DE-amy-medium
```

---

## 🧪 Local Setup

### ▶️ Windows 11

```powershell
# Create venv (Python 3.10 required)
py -3.10 -m venv .venv
.venv\Scripts\activate

# Update pip
python -m pip install --upgrade pip

# Install backend dependencies
pip install -r requirements.txt

# Install PyTorch (choose one):
pip install torch==2.1.0+cpu --index-url https://download.pytorch.org/whl/cpu
# or GPU:
pip install torch==2.1.0+cu121 --index-url https://download.pytorch.org/whl/cu121

# Start server
python PythonServer/api/server.py
```

### ▶️ Linux (Ubuntu)

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv ffmpeg

python3.10 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install torch==2.1.0+cpu --index-url https://download.pytorch.org/whl/cpu

python PythonServer/api/server.py
```

---

## 📁 Project Structure

```
📦PythonServer
 ┗ 📂api
    ┣ server.py        # Main entry
    ┣ gwdg_api.py
    ┣ stt_api.py
    ┣ tts_api.py
    ┗ __init__.py
```

---

## 🔒 Security

* Auth via `Authorization: Bearer <SERVER_API_KEY>`
* Basic input sanitization
* Recommended: Nginx reverse proxy + HTTPS + rate limit
* Do not expose to the public internet without protection

---

## 📜 License Notes

Generate dependency licenses:

```bash
pip-licenses --format=json --with-urls --with-license-file \
  --with-system --output-file licenses/pip-licenses.json
```

Whisper, Piper, and LLM models may have **additional licenses**.
Ensure compliance before deployment.

---

## 📧 Contact

If you need help running the backend or integrating it with the SvelteKit client, feel free to reach out.

```

---