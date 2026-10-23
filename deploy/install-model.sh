#!/bin/bash
set -euo pipefail
cloud-init status --wait
id unspoken >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/unspoken --shell /usr/sbin/nologin unspoken
install -d -o unspoken -g unspoken /opt/unspoken
cd /opt/unspoken
sudo -u unspoken python3 -m venv /opt/unspoken/model-venv
sudo -u unspoken /opt/unspoken/model-venv/bin/pip install uv==0.13.5
sudo -u unspoken /opt/unspoken/model-venv/bin/uv pip install --python /opt/unspoken/model-venv/bin/python --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu
if [ ! -d /opt/unspoken/strands-decider ]; then
  sudo -u unspoken git clone https://github.com/strands-labs/strands-decider.git /opt/unspoken/strands-decider
fi
sudo -u unspoken git -C /opt/unspoken/strands-decider checkout 930e6d5de16309be32579f5631a7369a3322140c
sudo -u unspoken /opt/unspoken/model-venv/bin/uv pip sync --python /opt/unspoken/model-venv/bin/python --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match /opt/unspoken/app/deploy/model-requirements.lock.txt
python3 /opt/unspoken/app/deploy/enable-cpu-bf16.py /opt/unspoken/model-venv/lib/python3.12/site-packages/strands_decider
sudo -u unspoken env HF_HOME=/opt/unspoken/hf-home HF_HUB_DISABLE_TELEMETRY=1 /opt/unspoken/model-venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path
model=snapshot_download('StrandsAgents/strands-decider-2B-qwen3.5-v1-2610',revision='216d1ccb46a9e9b036eb9187b248db98480f77d4')
snapshot_download('Qwen/Qwen3.5-2B-Base',revision='b1485b2fa6dfa1287294f269f5fb618e03d52d7c')
Path('/opt/unspoken/model-path').write_text(model)
PY
cat >/etc/systemd/system/unspoken-decider.service <<'UNIT'
[Unit]
Description=Unspoken real Strands Decider 2B
After=network-online.target
Wants=network-online.target
[Service]
User=unspoken
Group=unspoken
WorkingDirectory=/opt/unspoken
Environment=HF_HOME=/opt/unspoken/hf-home
Environment=HF_HUB_DISABLE_TELEMETRY=1
Environment=HF_HUB_OFFLINE=1
Environment=TOKENIZERS_PARALLELISM=false
Environment=OMP_NUM_THREADS=2
Environment=MKL_NUM_THREADS=2
Environment=STRANDS_CPU_BF16=1
MemoryMax=7G
ExecStart=/bin/bash -c 'exec /opt/unspoken/model-venv/bin/strands-decider serve "$(cat /opt/unspoken/model-path)" --host 127.0.0.1 --port 8765 --device cpu --model-name decider-2b'
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/unspoken
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now unspoken-decider
/opt/unspoken/model-venv/bin/pip freeze > /opt/unspoken/model-requirements.lock.txt
echo MODEL_INSTALL_COMPLETE
