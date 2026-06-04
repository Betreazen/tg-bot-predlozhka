#!/bin/bash
# ============================================================
# Deployment script for tg-bot-prelozhka
# Ensures all files are present and services are running
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  tg-bot-prelozhka Deployment Script"
echo "============================================"

# --- Check required files ---
echo -e "\n${YELLOW}[1/5] Checking required files...${NC}"

REQUIRED_FILES=(
    "docker-compose.yml"
    "Dockerfile"
    "requirements.txt"
    ".env"
    "config/config.json"
    "config/messages.json"
    "migrations/init.sql"
    "bot/main.py"
    "bot/utils/config.py"
    "bot/utils/database.py"
)

MISSING=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "  ${RED}✗ Missing: $file${NC}"
        MISSING=$((MISSING + 1))
    else
        echo -e "  ${GREEN}✓ $file${NC}"
    fi
done

if [ $MISSING -gt 0 ]; then
    echo -e "\n${RED}ERROR: $MISSING required file(s) missing!${NC}"
    echo "If you deployed from git, try: git checkout -- ."
    echo "Or re-clone: git clone <repo-url> ."
    exit 1
fi

# --- Check .env configuration ---
echo -e "\n${YELLOW}[2/5] Validating .env configuration...${NC}"

REQUIRED_VARS=("BOT_TOKEN" "CHANNEL_ID" "ADMIN_CHAT_ID" "ERROR_CHAT_ID" "DB_NAME" "DB_USER" "DB_PASSWORD" "REDIS_PASSWORD")
ENV_OK=true

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env 2>/dev/null; then
        echo -e "  ${RED}✗ Missing variable: $var${NC}"
        ENV_OK=false
    fi
done

if [ "$ENV_OK" = false ]; then
    echo -e "\n${RED}ERROR: .env is incomplete. Copy from .env.example and fill in values.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ All required variables present${NC}"

# --- Build and start ---
echo -e "\n${YELLOW}[3/5] Building Docker image...${NC}"
docker compose build --no-cache bot

echo -e "\n${YELLOW}[4/5] Starting all services...${NC}"
docker compose up -d

# --- Health check ---
echo -e "\n${YELLOW}[5/5] Waiting for services to become healthy...${NC}"
sleep 5

MAX_WAIT=60
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    PG_STATUS=$(docker inspect --format='{{.State.Health.Status}}' tg-bot-postgres 2>/dev/null || echo "not found")
    REDIS_STATUS=$(docker inspect --format='{{.State.Health.Status}}' tg-bot-redis 2>/dev/null || echo "not found")
    BOT_STATUS=$(docker inspect --format='{{.State.Status}}' tg-bot-app 2>/dev/null || echo "not found")

    echo "  PostgreSQL: $PG_STATUS | Redis: $REDIS_STATUS | Bot: $BOT_STATUS"

    if [ "$PG_STATUS" = "healthy" ] && [ "$REDIS_STATUS" = "healthy" ] && [ "$BOT_STATUS" = "running" ]; then
        echo -e "\n${GREEN}============================================${NC}"
        echo -e "${GREEN}  ✓ All services are running!${NC}"
        echo -e "${GREEN}============================================${NC}"
        echo ""
        echo "Useful commands:"
        echo "  docker compose logs -f bot     # Watch bot logs"
        echo "  docker compose ps              # Check service status"
        echo "  docker compose restart bot     # Restart bot only"
        exit 0
    fi

    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

echo -e "\n${RED}WARNING: Services did not become healthy within ${MAX_WAIT}s${NC}"
echo "Check logs with: docker compose logs"
exit 1
