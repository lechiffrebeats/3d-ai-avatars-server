# **DoYouTrustMe – 3D AI Avatar Chatbot (Server) – Python Backend for 3D AI Avatar Chatbot**

This repository contains the **Python backend** used in the *DoYouTrustMe – 3D AI Avatar Chatbot* research project.
It provides endpoints for:

* **LLM access** (GWDG RAG Container)
* **STT** (Whisper or cloud alternative)
* **TTS** (Piper or cloud alternative)
* **Viseme extraction** for lip-sync
* **Utility APIs** for evaluation & debugging

The server can run on **Linux (Ubuntu)** or **Windows**.

> ⚠️ Research prototype – not optimized for production use.

---

# 🏗 **Architecture Overview**

The Python server exposes a small REST API and acts as the central processing unit:

```
SvelteKit Client  →  SvelteKit Proxy  →  HISTAR_SERVER  →  GWDG LLM / STT / TTS
```

Technologies:

* **Flask** (REST API)
* **Whisper (CPU)** – STT
* **Piper TTS** – speech synthesis
* **Phoneme → Viseme mapping** for avatar lip-sync
* **Gunicorn + Nginx** (recommended on Linux)
* **Python 3.10**

---

# ⚙️ **Required Environment Variables**

Create a `.env` file or set environment variables manually:

```bash
VM_API_KEY=your_api_key_here
GWDG_API_KEY=
GWDG_BASE_URL=
GWDG_MODEL=meta-llama-3.1-8b-rag
GWDG_ARCANA_ID=
```

Optional:

```bash
WHISPER_MODEL=base
PIPER_MODEL=de_DE-amy-medium
```

---

# 🧪 **Local Development Setup**

## 🔵 **Windows Setup**

```powershell
# Remove old venv if needed
rm -r .venv

# Create venv with Python 3.10
python3.10 -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Start server:

```powershell
python PythonServer\api\server.py
```

---

## 🟢 **Linux (Ubuntu 22.04+) Setup**

### **1️⃣ Install Python 3.10**

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3.10-distutils python3.10-dev
```

Check:

```bash
python3.10 --version
```

(Optional) make Python 3.10 default:

```bash
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2
sudo update-alternatives --config python3
```

### **2️⃣ CPU PyTorch (optional)**

```bash
pip install torch==2.1.0+cpu torchvision --index-url https://download.pytorch.org/whl/cpu
```

### **3️⃣ Create virtual environment**

```bash
rm -r .venv
python3.10 -m venv .venv
source .venv/bin/activate
```

### **4️⃣ Install dependencies**

```bash
pip install -r requirements.txt
```

---

# 🚀 **Running the Server**

Inside the venv:

```bash
python PythonServer/api/server.py
```

Health check:

```bash
curl -s http://127.0.0.1:5000/health
# → "ok"
```

---

# 🔑 **Generate API Keys**

```bash
openssl rand -hex 32
```

Add to `.env`:

```bash
VM_API_KEY=your_hex_key
```

---

# 🧪 **Testing the GWDG LLM Endpoint**

```bash
curl -X POST http://127.0.0.1:5000/gwdg/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $VM_API_KEY" \
  -d '{
    "prompt": "Wann beginnt das Wintersemester im Master Informatik an der Universität Bremen?",
    "animations": ["Idle", "Happy Idle", "Nodd", "Breathing"],
    "expressions": ["Smile", "Neutral", "Surprised", "Confused"],
    "userLanguage": "Deutsch",
    "conversation": [],
    "arcanaId": "ramon.desmit/Universität Bremen"
  }'
```

---

# 📁 **Project Structure (Short)**

```
📦PythonServer
 ┗ 📂api
 ┃ ┣ 📜gwdg_api.py
 ┃ ┣ 📜server.py
 ┃ ┣ 📜stt_api.py
 ┃ ┣ 📜tts_api.py
 ┃ ┗ 📜__init__.py
```

---

# 🔒 **Security Notes**

* Authentication via `Authorization: Bearer <VM_API_KEY>`
* Basic request sanitization (`_sanitize`)
* Rate-limiting recommended via Nginx (example configs in thesis)
* Do **not** expose without HTTPS

---

# 📜 **Licensing**

Generate dependency licenses:

```bash
pip-licenses --format=json --with-urls --with-license-file --with-system \
  --output-file licenses/pip-licenses.json
```

This backend is provided **for academic research only**.
Models for Whisper/Piper may carry their own licenses—verify before deployment.

---

# 📧 **Contact**

If you need help running the backend, connecting the SvelteKit client, or replacing TTS/STT/LLM providers, feel free to reach out.

---
