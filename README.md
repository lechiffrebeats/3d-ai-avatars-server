# HISTAR_SERVER
Server Only

# python
Python310

# Update package list
sudo apt update

# Install dependencies for adding new repos
sudo apt install -y software-properties-common

# Add the deadsnakes PPA (contains newer Python versions)
sudo add-apt-repository ppa:deadsnakes/ppa

# Update again after adding PPA
sudo apt update

# Install Python 3.10
sudo apt install -y python3.10 python3.10-venv python3.10-distutils python3.10-dev

# Check version
python3.10 --version

# make it defautl
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2
sudo update-alternatives --config python3

pip install torch==2.1.0+cpu torchvision --index-url https://download.pytorch.org/whl/cpu

pip-licenses --format=json --with-urls --with-license-file --with-system | Out-File -Encoding utf8 licenses/pip-licenses.json

rm -r .venv
python3.10 -m venv .venv <!-- oder wo auch immer python310 ist -->
source .venv\Scripts\activate

# install 
cd .venv\Scripts\
pip install -r requirements.txt

# misc
api key openssl rand -hex 32
Test: curl -s http://127.0.0.1:5000/health -> ok

# testing
THE LLM API
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


