#!/bin/bash
# ============================================================
#  tg-bot-predlozhka deployment script
#  Builds and starts the whole stack from a single .env file.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  tg-bot-predlozhka deployment"
echo "============================================"

# --- Pick the docker compose command ---
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo -e "${RED}ERROR: docker compose is not installed.${NC}"
    exit 1
fi

# --- Ensure .env exists ---
echo -e "\n${YELLOW}[1/3] Checking .env...${NC}"
if [ ! -f .env ]; then
    echo -e "${RED}ERROR: .env not found.${NC}"
    echo "Create it from the template:  cp .env.example .env  (then fill in the values)"
    exit 1
fi

# Validate required variables are present and non-empty.
REQUIRED_VARS=(COMPOSE_PROJECT_NAME BOT_TOKEN CHANNEL_ID ADMIN_CHAT_ID ERROR_CHAT_ID ADMIN_IDS DB_NAME DB_USER DB_PASSWORD REDIS_PASSWORD)
MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
    value=$(grep -E "^${var}=" .env | head -n1 | cut -d= -f2-)
    if [ -z "$value" ]; then
        echo -e "  ${RED}✗ ${var} is missing or empty${NC}"
        MISSING=$((MISSING + 1))
    fi
done
if [ "$MISSING" -gt 0 ]; then
    echo -e "\n${RED}Fill in the missing variables in .env and re-run.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ .env looks complete${NC}"

# --- Build and start (waits until services are healthy) ---
echo -e "\n${YELLOW}[2/3] Building and starting services...${NC}"
$DC up -d --build --wait

echo -e "\n${YELLOW}[3/3] Status:${NC}"
$DC ps

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}  ✓ Deployment complete${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Useful commands:"
echo "  $DC logs -f bot      # watch bot logs"
echo "  $DC ps               # service status"
echo "  $DC restart bot      # restart the bot only"
echo "  $DC down             # stop the stack"
