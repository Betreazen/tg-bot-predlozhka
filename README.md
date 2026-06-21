# Telegram Bot for UGC Collection and Moderation

[![tests](https://github.com/Betreazen/tg-bot-predlozhka/actions/workflows/tests.yml/badge.svg)](https://github.com/Betreazen/tg-bot-predlozhka/actions/workflows/tests.yml)

A comprehensive Telegram bot system for collecting user-generated content with mandatory moderation, automated publishing, and statistics tracking.

## 📋 Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Running the Bot](#running-the-bot)
- [Deployment](#deployment)
- [Development](#development)
- [Implementation Status](#implementation-status)

## ✨ Features

### User Features
- Submit content (text, photos, videos, documents, audio)
- Optional authorship attribution
- Rate limiting (2 submissions per day)
- Status notifications

### Admin Features
- Unified moderation chat
- Approve/reject submissions
- Schedule publications with delay
- Block/unblock users
- Add notes to users
- View detailed statistics
- Publication error handling with retry

### System Features
- Asynchronous architecture
- PostgreSQL database with SQLAlchemy ORM
- Redis for caching and rate limiting
- Docker containerization
- Comprehensive logging
- Health checks
- Error recovery

## 🛠 Technology Stack

- **Language:** Python 3.11+
- **Bot Framework:** aiogram 3.x
- **Database:** PostgreSQL 15+ with asyncpg
- **ORM:** SQLAlchemy 2.0 (async)
- **Cache:** Redis 7+
- **Containerization:** Docker & docker-compose
- **Migrations:** Alembic

## 📁 Project Structure

```
tg-bot-prelozhka/
├── bot/
│   ├── handlers/          # Bot message and callback handlers
│   ├── services/          # Business logic services
│   ├── models/            # Database models
│   ├── utils/             # Utilities (config, database, redis, logging)
│   └── main.py            # Bot entry point
├── config/
│   ├── config.json        # Main configuration
│   └── messages.json      # All bot messages in Russian
├── migrations/            # Alembic database migrations
├── logs/                  # Application logs
├── docker-compose.yml     # Docker services configuration
├── Dockerfile             # Bot application container
├── requirements.txt       # Python dependencies
├── alembic.ini            # Alembic configuration
└── .env.example           # Environment variables template
```

## 🚀 Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Git

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tg-bot-prelozhka
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` with your actual values — **this single file is all you need**:

```env
# Docker isolation (unique per bot on a shared host)
COMPOSE_PROJECT_NAME=predlozhka

# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_from_botfather

# Channel and Chat IDs
CHANNEL_ID=-1001234567890           # Your channel ID
ADMIN_CHAT_ID=-1009876543210        # Admin chat ID
ERROR_CHAT_ID=-1001111111111        # Error notifications chat ID

# Administrators — comma-separated Telegram user IDs
ADMIN_IDS=123456789,987654321

# Database Configuration
DB_HOST=postgres
DB_NAME=tg_bot
DB_USER=bot_user
DB_PASSWORD=your_secure_password

# Redis Configuration
REDIS_HOST=redis
REDIS_PASSWORD=your_redis_password
```

### 3. Configure Administrators

Administrators are set via the `ADMIN_IDS` environment variable in `.env`
(comma-separated Telegram user IDs). No edits to `config/config.json` are
required. Get your user ID from [@userinfobot](https://t.me/userinfobot).

## ⚙️ Configuration

### Main Configuration (`config/config.json`)

- **Rate Limits:** Submissions per day, timezone
- **Publication:** Delay, footer, hashtags
- **Features:** Enable/disable bot features
- **Error Handling:** Retry attempts and delays

### Messages (`config/messages.json`)

All bot messages are in Russian and fully customizable:
- User messages and prompts
- Admin notifications
- Statistics templates
- Error messages

## 🗄️ Database Setup

The database is automatically initialized when Docker containers start. For manual setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head
```

### Database Schema

**Users Table:**
- user_id, username, first_name, last_name
- is_blocked, admin_note
- total_submissions_count
- registration_timestamp, last_interaction_timestamp

**Submissions Table:**
- submission_id (UUID), user_id
- status, moderator_id, decision_timestamp
- show_authorship
- message_id_in_admin_chat, message_id_in_channel
- media information, text_content
- publication scheduling fields

**Admin Action Logs Table:**
- log_id, action_type, admin_user_id
- target_user_id, submission_id
- action_timestamp, additional_context

## 🏃 Running the Bot

### Using Docker (Recommended)

Database migrations run automatically when the bot container starts.

```bash
# One-command deploy: validates .env, builds, waits until healthy
bash deploy.sh

# ...or manually:
docker compose up -d --build --wait

# View logs
docker compose logs -f bot

# Stop services
docker compose down

# Rebuild after code changes
docker compose up -d --build
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export $(cat .env | xargs)

# Run migrations
alembic upgrade head

# Start bot
python -m bot.main
```

## 🚢 Deployment

### VPS Deployment with systemd

1. **Copy files to server:**

```bash
scp -r tg-bot-prelozhka/ user@your-server:/opt/
```

2. **Create systemd service:**

Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram UGC Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/tg-bot-prelozhka
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

3. **Enable and start service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

### Token Rotation

To rotate the bot token without code changes:

1. Get new token from [@BotFather](https://t.me/botfather)
2. Update `.env` file: `BOT_TOKEN=new_token`
3. Restart service: `docker-compose restart bot`

Total time: < 1 minute

## 💻 Development

### Code Style

The project uses:
- Black for code formatting (line length: 100)
- Type hints throughout
- Async/await for all I/O operations

### Adding New Features

1. **Database Changes:** Create Alembic migration
2. **Configuration:** Add to `config.json` or `messages.json`
3. **Handlers:** Add to `bot/handlers/`
4. **Services:** Add business logic to `bot/services/`
5. **Register:** Update `bot/main.py` to register new handlers

### Testing

```bash
# Run tests (when implemented)
pytest

# Type checking
mypy bot/

# Code formatting
black bot/
```

## 📊 Implementation Status

### ✅ Completed Components

- [x] Project structure and configuration
- [x] Database models (User, Submission, AdminActionLog)
- [x] Configuration loader with environment variables
- [x] Database connection manager
- [x] Redis connection manager
- [x] Logging system with structured output
- [x] Health check utilities
- [x] Docker containerization
- [x] Alembic migrations setup

### 🚧 Remaining Implementation

The following components need to be implemented:

#### Services (`bot/services/`)

1. **rate_limit.py** - Rate limiting with Redis
   - Daily submission counter per user
   - Timezone-aware reset logic
   - Atomic increment operations

2. **user_service.py** - User management
   - Create/update user records
   - Block/unblock operations
   - Note management

3. **submission_service.py** - Submission handling
   - Create submissions
   - Update status
   - Query operations

4. **publication_service.py** - Publication scheduling
   - 2-minute delayed publication
   - Cancellation support
   - Format message with authorship/footer

5. **statistics_service.py** - Statistics aggregation
   - Monthly/yearly metrics
   - Per-admin performance
   - Rate calculations

6. **notification_service.py** - User notifications
   - Status change notifications
   - Template formatting

#### Handlers (`bot/handlers/`)

1. **user_handlers.py** - User flow
   - /start command
   - Content submission FSM
   - Authorship selection

2. **admin_handlers.py** - Admin moderation
   - Submission presentation
   - Decision callbacks
   - Block/note management

3. **statistics_handlers.py** - Statistics display
   - Period selection
   - Report formatting

#### Main Application

**bot/main.py** - Bot entry point
   - Initialize all managers
   - Register handlers
   - Setup FSM storage
   - Error handling
   - Graceful shutdown

### Implementation Guide

Each service and handler should:
1. Use the configuration from `config_loader`
2. Access database via `db_manager.session()`
3. Access Redis via `redis_manager.get_client()`
4. Use structured logging
5. Handle errors appropriately
6. Follow async patterns

### Example Service Structure

```python
# bot/services/example_service.py
import logging
from bot.utils.database import get_db_manager
from bot.utils.redis_manager import get_redis_manager
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)

class ExampleService:
    def __init__(self):
        self.config = config_loader.load_config()
        self.db = get_db_manager()
        self.redis = get_redis_manager()
    
    async def do_something(self) -> None:
        async with self.db.session() as session:
            # Database operations
            pass
```

### Example Handler Structure

```python
# bot/handlers/example_handlers.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Hello!")
```

## 📝 Important Notes

1. **Security:**
   - Never commit `.env` file
   - Keep bot token secure
   - Use strong database passwords

2. **Rate Limiting:**
   - Default: 2 submissions per day (Europe/Moscow timezone)
   - Configurable in `config.json`

3. **File Size:**
   - Maximum file size: 200 MB (Telegram limit)
   - Files larger than 200 MB are rejected

4. **Statistics Retention:**
   - Default: 2 years of historical data
   - Automatic cleanup of older data

5. **Publication Delay:**
   - Default: 2 minutes
   - Allows admin to cancel before publishing
   - Configurable in `config.json`

## 🐛 Troubleshooting

### Bot not starting

Check logs:
```bash
docker-compose logs bot
```

Common issues:
- Invalid bot token
- Database connection failed
- Redis connection failed
- Missing environment variables

### Database issues

```bash
# Check database logs
docker-compose logs postgres

# Connect to database
docker exec -it tg-bot-postgres psql -U bot_user -d tg_bot

# Run migrations manually
docker exec -it tg-bot-app alembic upgrade head
```

### Redis issues

```bash
# Check Redis logs
docker-compose logs redis

# Test Redis connection
docker exec -it tg-bot-redis redis-cli ping
```

## 📄 License

[Specify your license here]

## 👥 Contributing

Contributions are welcome! Please follow the code style and include tests for new features.

## 📞 Support

For issues and questions, please open an issue on GitHub or contact the maintainers.

---

**Note:** This bot is designed for moderate-scale usage (up to 5,000 users). For larger deployments, consider horizontal scaling with multiple bot instances and shared Redis/PostgreSQL.
