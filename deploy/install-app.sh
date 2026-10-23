#!/bin/bash
set -euo pipefail
DOMAIN=${1:?domain required}
cd /opt/unspoken
chown -R unspoken:unspoken /opt/unspoken/app
sudo -u unspoken python3 -m venv /opt/unspoken/demo-venv
sudo -u unspoken /opt/unspoken/model-venv/bin/uv pip sync --python /opt/unspoken/demo-venv/bin/python /opt/unspoken/app/requirements.lock.txt
cat >/etc/unspoken.env <<'ENV'
HOMEDEMO_MODE=cascade
HOMEDEMO_ALLOWED_MODES=2b,cascade
HOMEDEMO_ALLOWED_ESCALATIONS=bedrock
HOMEDEMO_DEPLOYMENT_NOTICE="AWS-hosted demo · Sensors, speech and devices are simulated. Real Decider 2B runs on this server. Uncertain decisions go to Claude Haiku on Amazon Bedrock. All visitors share one simulated home."
AWS_DEFAULT_REGION=us-west-2
ENV
cat >/etc/systemd/system/unspoken-app.service <<'UNIT'
[Unit]
Description=Unspoken smart-home demo
After=network-online.target unspoken-decider.service
Wants=network-online.target unspoken-decider.service
[Service]
User=unspoken
Group=unspoken
WorkingDirectory=/opt/unspoken/app
EnvironmentFile=/etc/unspoken.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStartPre=/bin/bash -c 'for i in {1..90}; do curl --fail --silent http://127.0.0.1:8765/health >/dev/null && exit 0; sleep 2; done; exit 1'
ExecStart=/opt/unspoken/demo-venv/bin/python -m homedemo --host 127.0.0.1 --port 8790 --mode ${HOMEDEMO_MODE} --bedrock-profile "" --bedrock-region us-west-2
TimeoutStartSec=200
TimeoutStopSec=15
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
[Install]
WantedBy=multi-user.target
UNIT
install -d /var/www/acme
cat >/etc/nginx/sites-available/unspoken <<NGINX
server {
 listen 80;
 server_name $DOMAIN;
 location /.well-known/acme-challenge/ { root /var/www/acme; }
 location / { return 503; }
}
NGINX
ln -sf /etc/nginx/sites-available/unspoken /etc/nginx/sites-enabled/unspoken
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx
certbot certonly --webroot -w /var/www/acme --non-interactive --agree-tos --register-unsafely-without-email -d "$DOMAIN"
cat >/etc/nginx/sites-available/unspoken <<'NGINX'
limit_req_zone $binary_remote_addr zone=unspoken_api:10m rate=2r/s;
server {
 listen 80;
 server_name __DOMAIN__;
 location /.well-known/acme-challenge/ { root /var/www/acme; }
 location / { return 301 https://$host$request_uri; }
}
server {
 listen 443 ssl;
 server_name __DOMAIN__;
 ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
 ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
 ssl_protocols TLSv1.2 TLSv1.3;
 server_tokens off;
 client_max_body_size 16k;
 add_header X-Content-Type-Options nosniff always;
 add_header Referrer-Policy same-origin always;
 add_header X-Frame-Options DENY always;
 add_header Strict-Transport-Security "max-age=31536000" always;
 location = /healthz {
  proxy_pass http://127.0.0.1:8790;
 }
 location = /api/stream {
  proxy_pass http://127.0.0.1:8790;
  proxy_http_version 1.1;
  proxy_set_header Connection "";
  proxy_buffering off;
  proxy_read_timeout 3600s;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
 }
 location /api/ {
  limit_req zone=unspoken_api burst=10 nodelay;
  proxy_pass http://127.0.0.1:8790;
  proxy_read_timeout 120s;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
 }
 location / {
  proxy_pass http://127.0.0.1:8790;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
 }
}
NGINX
sed -i "s/__DOMAIN__/$DOMAIN/g" /etc/nginx/sites-available/unspoken
nginx -t
systemctl reload nginx
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' >/etc/letsencrypt/renewal-hooks/deploy/unspoken-nginx
chmod +x /etc/letsencrypt/renewal-hooks/deploy/unspoken-nginx
systemctl daemon-reload
systemctl enable unspoken-app
systemctl restart --no-block unspoken-app
echo APP_INSTALL_COMPLETE
