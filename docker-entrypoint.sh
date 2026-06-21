#!/bin/sh
# Container entrypoint: apply database migrations, then start the bot.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Starting bot..."
exec python -m bot.main
