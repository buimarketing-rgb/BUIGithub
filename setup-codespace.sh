#!/usr/bin/env bash
# BUI one-step setup for GitHub Codespaces.
# Usage (in the Codespace terminal, from the repository folder):  bash setup-codespace.sh
# Optional: GROQ_API_KEY=gsk_... bash setup-codespace.sh   (free AI answers via Groq)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f docker-compose.yml ]; then
  echo "ERROR: run this from the BUI repository folder (the one containing docker-compose.yml)."; exit 1
fi

echo "==> 1/5 Creating any missing configuration files"
mkdir -p docker/nginx docker/searxng
if [ ! -f docker/nginx/nginx.conf ]; then
cat > docker/nginx/nginx.conf <<'EOF'
upstream bui_backend  { server backend:8000; }
upstream bui_frontend { server frontend:3000; }
limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;
server {
    listen 80;
    server_name _;
    client_max_body_size 30m;
    add_header X-Content-Type-Options nosniff always;
    location /api/chat/stream {
        proxy_pass http://bui_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
    location /api/ {
        limit_req zone=api burst=40 nodelay;
        proxy_pass http://bui_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
    location / {
        proxy_pass http://bui_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
fi
if [ ! -f docker/searxng/settings.yml ]; then
cat > docker/searxng/settings.yml <<'EOF'
use_default_settings: true
server:
  secret_key: "overridden-by-env"
  limiter: false
  image_proxy: false
search:
  safe_search: 1
  formats: [html, json]
EOF
fi
# Never commit secrets from the Codespace
touch .gitignore
for p in .env bui-login.txt; do grep -qxF "$p" .gitignore || echo "$p" >> .gitignore; done

echo "==> 2/5 Writing settings (.env)"
if [ -n "${CODESPACE_NAME:-}" ]; then
  PUBLIC_URL="https://${CODESPACE_NAME}-80.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
else
  PUBLIC_URL="http://localhost"
fi
if [ -f .env ] && grep -q '^INITIAL_ADMIN_PASSWORD=' .env; then
  ADMIN_PW=$(grep '^INITIAL_ADMIN_PASSWORD=' .env | cut -d= -f2-)
  echo "    .env already exists - keeping it"
else
  ADMIN_PW="Bui$(openssl rand -hex 5)Ax9"
  if [ -n "${GROQ_API_KEY:-}" ]; then
    LLM="LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=${GROQ_API_KEY}
OPENAI_MODEL=llama-3.3-70b-versatile"
  else
    LLM="LLM_PROVIDER=extractive"
  fi
  cat > .env <<EOF
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SEARXNG_SECRET=$(openssl rand -hex 16)
PUBLIC_URL=${PUBLIC_URL}
COOKIE_SECURE=true
HTTP_PORT=80
INITIAL_ADMIN_EMAIL=admin@bui.local
INITIAL_ADMIN_NAME=BUI Super Admin
INITIAL_ADMIN_PASSWORD=${ADMIN_PW}
${LLM}
EMBEDDING_PROVIDER=auto
INSTALL_ML=false
SEARCH_PROVIDER=searxng
MAX_UPLOAD_MB=25
API_WORKERS=1
EOF
fi

echo "==> 3/5 Building and starting BUI (first time: 5-10 minutes)"
docker compose up -d --build db redis searxng backend frontend nginx

echo "==> 4/5 Waiting for BUI to be ready"
for i in $(seq 1 90); do
  if curl -fs http://localhost/api/health >/dev/null 2>&1; then break; fi
  sleep 5
  if [ "$i" = 90 ]; then echo "BUI did not start. Show logs with: docker compose logs backend --tail 50"; exit 1; fi
done

echo "==> 5/5 Loading demo data"
docker compose exec -T backend python -m app.seeds.demo --users || echo "(demo data step failed - BUI still works)"

cat > bui-login.txt <<EOF
BUI address : ${PUBLIC_URL}
Super Admin : admin@bui.local  /  ${ADMIN_PW}
Demo Admin  : admin@demo.bui   /  DemoAdmin2026!
Demo Member : member@demo.bui  /  DemoMember2026!
EOF
echo
echo "================ BUI IS RUNNING ================"
cat bui-login.txt
echo "================================================"
echo "Open the address above (or: Ports tab -> port 80 -> globe icon)."
echo "These details are saved in bui-login.txt"
