# Model setup and public hosting

## Requirements

Use an Ubuntu 24.04 x86-64 server with Python 3.12 and sufficient disk space for the Python environments and separately downloaded model weights. The CPU setup was verified with **2 vCPU / 8 GiB** on an Intel Sapphire Rapids processor, with 40 GB of disk. Model requests can take several seconds, and the first request after startup can take longer.

The pinned upstream CPU implementation normally expands its model weights to FP32. `enable-cpu-bf16.py` adds an opt-in `STRANDS_CPU_BF16=1` switch to retain BF16 weights on this processor. The classification head remains FP32. The observed process RSS was around 4 GiB under the demo workload. Services cap model memory at 7 GiB. Revalidate memory, answers and latency before using another CPU family or upstream revision.

Pinned public sources:

- [Strands Decider](https://github.com/strands-labs/strands-decider), revision `930e6d5de16309be32579f5631a7369a3322140c`.
- [2B checkpoint](https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610), revision `216d1ccb46a9e9b036eb9187b248db98480f77d4`.
- [Qwen base model](https://huggingface.co/Qwen/Qwen3.5-2B-Base), revision `b1485b2fa6dfa1287294f269f5fb618e03d52d7c`.

## Install on your server

Clone this repository into `/opt/unspoken/app`. Review the scripts before running them with administrative privileges; they install services and configure Nginx.

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv python3-pip git nginx certbot curl
sudo mkdir -p /opt/unspoken/app
sudo git clone https://github.com/anne-creator/unspoken.git /opt/unspoken/app
sudo bash /opt/unspoken/app/deploy/install-model.sh
sudo bash /opt/unspoken/app/deploy/install-app.sh demo.example.com
```

Replace `demo.example.com` with a domain you control. Its DNS must point to your server, and ports 80 and 443 must be reachable for the certificate challenge. The application and model bind to loopback; Nginx handles HTTPS. Certificates renew with certbot and a reload hook.

The scripts create a dedicated `unspoken` service user, model/app environments, pinned dependencies, cached model snapshots and systemd services. They do not create cloud instances, networking, account credentials or model subscriptions. For manual local model serving, follow the public Strands Decider instructions and point `--decider-2b-url` at that server.

## Bedrock access

Enable Claude Haiku 4.5 access in your own AWS account. Use a server instance role or another standard credential provider. The application uses the US inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-west-2`.

Grant only `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` for your target inference profile and its routed foundation-model regions. Obtain the correct resource ARNs for your account and chosen inference profile from AWS. Model subscription setup is an account-administrator task; the runtime role does not need permission to subscribe to arbitrary Marketplace products.

## Operations

```bash
systemctl status unspoken-decider unspoken-app nginx
sudo journalctl -u unspoken-app -u unspoken-decider -n 100 --no-pager
curl --fail http://127.0.0.1:8790/healthz
sudo systemctl restart unspoken-app
```

- `/` is the welcome/video page; `/demo?present=1` opens the interactive demo.
- `/healthz` checks local model availability; it does not make a paid Bedrock call.
- `/etc/unspoken.env` controls allowed modes, escalation targets and the deployment notice.
- Every visitor shares one simulated home. A scenario run or reset changes that shared state.
- Public actions can cause paid Haiku calls. The supplied Nginx configuration includes a basic API rate limit.
- Model weights stay cached, and serving uses offline mode. Dependency/model installation needs network access to public package and model sources.
- The browser UI and video are self-hosted; the welcome page does not invoke a model.

The local command `python -m homedemo --mode fake` is useful for development with no cloud services. Never present scripted responses as real model inference.
