# Quick Start Guide / Руководство по быстрому запуску

This guide provides complete installation instructions from scratch for Windows and Linux Ubuntu 24.04 LTS.

Это руководство содержит полную инструкцию по установке с нуля для Windows и Linux Ubuntu 24.04 LTS.

---

## 📋 Table of Contents / Содержание

- [Windows Installation](#windows-installation)
- [Linux Ubuntu 24.04 Installation](#linux-ubuntu-2404-installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Bot Management](#bot-management)
- [Troubleshooting](#troubleshooting)

---

## 🪟 Windows Installation

### Step 1: Install Python 3.11+

1. **Download Python:**
   - Go to [python.org/downloads](https://www.python.org/downloads/)
   - Download Python 3.11 or newer (recommended: Python 3.11.x)

2. **Install Python:**
   - Run the installer
   - ✅ **IMPORTANT:** Check "Add Python to PATH"
   - Click "Install Now"

3. **Verify installation:**
   ```powershell
   python --version
   # Should show: Python 3.11.x or higher
   
   pip --version
   # Should show pip version
   ```

### Step 2: Install Git (Optional, for cloning)

1. **Download Git:**
   - Go to [git-scm.com/download/win](https://git-scm.com/download/win)
   - Download and run the installer

2. **Install with default settings**

3. **Verify:**
   ```powershell
   git --version
   ```

### Step 3: Install Docker Desktop

1. **Download Docker Desktop:**
   - Go to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
   - Download "Docker Desktop for Windows"

2. **Install Docker Desktop:**
   - Run the installer
   - Follow the installation wizard
   - Restart your computer if prompted

3. **Start Docker Desktop:**
   - Launch Docker Desktop from Start menu
   - Wait for Docker Engine to start (icon in system tray turns green)

4. **Verify installation:**
   ```powershell
   docker --version
   # Should show: Docker version 24.x.x or higher
   
   docker-compose --version
   # Should show: Docker Compose version 2.x.x or higher
   ```

### Step 4: Get the Project

**Option A: Clone with Git**
```powershell
cd "D:\Program Projects\TG"
git clone <your-repository-url>
cd tg-bot-prelozhka
```

**Option B: Download ZIP**
- Download project as ZIP
- Extract to desired location
- Open PowerShell in project directory

### Continue to [Configuration](#configuration) section

---

## 🐧 Linux Ubuntu 24.04 Installation

### Step 1: Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Python 3.11+

Ubuntu 24.04 comes with Python 3.12 by default, but let's verify:

```bash
# Check Python version
python3 --version

# If Python is not installed or version < 3.11:
sudo apt install -y python3 python3-pip python3-venv

# Verify installation
python3 --version  # Should be 3.11 or higher
pip3 --version
```

### Step 3: Install Git

```bash
sudo apt install -y git

# Verify installation
git --version
```

### Step 4: Install Docker

```bash
# Remove old Docker versions (if any)
sudo apt remove -y docker docker-engine docker.io containerd runc

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Log out and log back in for group changes to take effect
# Or run: newgrp docker

# Verify installation
docker --version
docker compose version
```

### Step 5: Get the Project

```bash
# Clone repository
cd ~
git clone <your-repository-url>
cd tg-bot-prelozhka

# Or download and extract ZIP
# wget <download-url> -O bot.zip
# unzip bot.zip
# cd tg-bot-prelozhka
```

---

## ⚙️ Configuration

### Step 1: Create Telegram Bot

1. **Open Telegram and find @BotFather**
2. **Send:** `/newbot`
3. **Follow instructions:**
   - Enter bot name (e.g., "My UGC Bot")
   - Enter bot username (must end with 'bot', e.g., "my_ugc_content_bot")
4. **Copy the bot token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Create Channel and Admin Chat

1. **Create a Telegram Channel:**
   - Open Telegram → New Channel
   - Name it (e.g., "My UGC Channel")
   - Set as Public or Private
   - Add your bot as administrator with "Post messages" permission

2. **Create Admin Chat:**
   - Create a new group in Telegram
   - Add your bot as administrator
   - This chat will receive moderation requests

3. **Get Chat/Channel IDs:**
   - Add [@userinfobot](https://t.me/userinfobot) to your channel and admin chat
   - The bot will show the chat ID
   - **Note:** Channel and group IDs start with `-100` (e.g., `-1001234567890`)
   - Save these IDs for configuration

4. **Get Your User ID:**
   - Send `/start` to [@userinfobot](https://t.me/userinfobot)
   - Copy your user ID (e.g., `123456789`)

### Step 3: Configure Environment Variables

1. **Copy environment template:**

   **Windows PowerShell:**
   ```powershell
   copy .env.example .env
   ```

   **Linux:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file:**

   **Windows:** Use Notepad, VS Code, or any text editor
   **Linux:** Use nano, vim, or any text editor

   ```bash
   # Linux example:
   nano .env
   ```

3. **Fill in the values** (this is the ONLY file you need to edit to deploy):

   ```env
   # Docker isolation — unique name per bot on the host
   COMPOSE_PROJECT_NAME=predlozhka

   # Telegram Bot Configuration
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # Your bot token from BotFather
   CHANNEL_ID=-1001234567890                         # Your channel ID (with minus!)
   ADMIN_CHAT_ID=-1009876543210                      # Your admin chat ID
   ERROR_CHAT_ID=-1009876543210                      # Chat for error notifications (can be same as admin)

   # Administrators — comma-separated Telegram user IDs (from @userinfobot)
   ADMIN_IDS=123456789,987654321

   # Database Configuration
   DB_HOST=postgres              # Leave as is for Docker
   DB_NAME=telegram_bot
   DB_USER=botuser
   DB_PASSWORD=MySecurePass123!  # CHANGE THIS to a strong password!

   # Redis Configuration
   REDIS_HOST=redis              # Leave as is for Docker
   REDIS_PASSWORD=RedisPass456!  # CHANGE THIS to a strong password!
   ```

   **Save and exit** (in nano: Ctrl+X, then Y, then Enter)

   > **Administrators are configured entirely via `ADMIN_IDS` in `.env`.** You do
   > **not** need to edit `config/config.json` to add moderators anymore.

### Step 4: (Optional) Tune bot behavior

Defaults work out of the box. If you want to change limits or publication
behavior, edit `config/config.json`:

   ```json
   {
     "rate_limits": {
       "submissions_per_day": 2,        // Max submissions per user per day
       "timezone": "Europe/Moscow",     // Your timezone
       "reset_time": "00:00"            // Daily reset time
     },
     "publication": {
       "delay_minutes": 2,              // Delay before publishing (allows cancellation)
       "include_footer": false,         // Add footer to posts
       "footer_text": "",               // Footer text if enabled
       "include_hashtags": false,       // Add hashtags to posts
       "hashtags": [],                  // List of hashtags if enabled
       "max_file_size_mb": 200          // Maximum file size
     }
   }
   ```

### Step 5: Verify Configuration

**Windows PowerShell:**
```powershell
python verify_deployment.py
```

**Linux:**
```bash
python3 verify_deployment.py
```

This will check your configuration files for common issues.

---

## 🚀 Running the Bot

Database migrations are applied **automatically** every time the bot container
starts (via the entrypoint), so there is no separate migration step.

### Start the Bot

**Recommended — one command (Linux/macOS/Git Bash):**
```bash
bash deploy.sh
```
It validates `.env`, builds the images, and waits until all services are healthy.

**Manual alternative (any platform):**
```bash
# Build and start all services (bot, PostgreSQL, Redis), wait until healthy
docker compose up -d --build --wait

# View logs to ensure bot started successfully
docker compose logs -f bot
```

**You should see:**
```
Bot started and polling...
🤖 Bot started successfully
```

**To stop following logs:** Press `Ctrl+C`

### Verify Everything is Running

```bash
# Check container status
docker compose ps

# All containers should show "Up" or "Up (healthy)".
# Names are prefixed with COMPOSE_PROJECT_NAME, e.g. for predlozhka:
# NAME                    STATUS
# predlozhka-bot-1        Up (healthy)
# predlozhka-postgres-1   Up (healthy)
# predlozhka-redis-1      Up (healthy)
```

### Test the Bot

1. **Find your bot in Telegram** (search by username)
2. **Send `/start`** to the bot
3. **Click "📤 Submit Content"**
4. **Send some content** (text, photo, or video)
5. **Check your admin chat** - moderation message should appear
6. **Click moderation buttons** to test approval/rejection
7. **Check your channel** - approved content should publish after 2 minutes

---

## 🛠️ Bot Management

### View Logs

```bash
# View all logs
docker compose logs bot

# View last 50 lines
docker compose logs --tail=50 bot

# Follow logs in real-time
docker compose logs -f bot

# View logs from all services
docker compose logs
```

### Stop the Bot

```bash
# Stop all services
docker compose stop

# Stop only the bot (keep database running)
docker compose stop bot
```

### Restart the Bot

```bash
# Restart all services
docker compose restart

# Restart only the bot
docker compose restart bot
```

### Stop and Remove Everything

```bash
# Stop and remove containers (keeps database data)
docker compose down

# Stop, remove containers AND delete all data
docker compose down -v
```

### Update Configuration

1. **Edit configuration files:**
   - `.env` for environment variables
   - `config/config.json` for bot settings
   - `config/messages.json` for bot messages

2. **Restart the bot:**
   ```bash
   docker compose restart bot
   ```

### View Database

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U botuser -d telegram_bot

# Example queries:
\dt                                    # List all tables
SELECT * FROM users;                   # View all users
SELECT * FROM submissions;             # View all submissions
SELECT * FROM submissions WHERE status = 'pending';  # Pending submissions
\q                                     # Exit
```

### Backup Database

**Windows PowerShell:**
```powershell
# Create backup
docker compose exec postgres pg_dump -U botuser telegram_bot > backup_$(Get-Date -Format 'yyyyMMdd').sql

# Restore backup
Get-Content backup_20251219.sql | docker compose exec -T postgres psql -U botuser telegram_bot
```

**Linux:**
```bash
# Create backup
docker compose exec postgres pg_dump -U botuser telegram_bot > backup_$(date +%Y%m%d).sql

# Restore backup
docker compose exec -T postgres psql -U botuser telegram_bot < backup_20251219.sql
```

### View Statistics

Send `/stats` command in the admin chat to view bot statistics:
- Total submissions
- Approved/rejected counts
- Active users
- Daily/weekly/monthly stats

---

## 🐛 Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
docker compose logs bot
```

**Common issues:**
- ❌ Invalid bot token → Check `BOT_TOKEN` in `.env`
- ❌ Database connection failed → Check if PostgreSQL is running: `docker compose ps postgres`
- ❌ Redis connection failed → Check if Redis is running: `docker compose ps redis`

**Solution:**
```bash
# Stop everything
docker compose down

# Start again
docker compose up -d

# Check logs
docker compose logs -f
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Restart PostgreSQL
docker compose restart postgres

# Test connection
docker compose exec postgres pg_isready -U botuser
```

### Redis Connection Issues

```bash
# Check Redis status
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping
# Should return: PONG

# Test with password
docker compose exec redis redis-cli -a YourRedisPassword ping
```

### Bot Not Receiving Messages

**Checklist:**
1. ✅ You sent `/start` to the bot
2. ✅ Bot is added to admin chat as administrator
3. ✅ Bot is added to channel as administrator with "Post messages" permission
4. ✅ Channel ID in `.env` starts with `-100`
5. ✅ Admin chat ID in `.env` starts with `-100`

**Check bot permissions:**
- Open channel settings → Administrators
- Ensure bot has "Post messages" permission
- Open admin chat → Manage chat → Administrators
- Ensure bot is administrator

### Publications Not Working

**Checklist:**
1. ✅ Bot is administrator in the channel
2. ✅ Bot has "Post messages" permission in channel
3. ✅ `CHANNEL_ID` in `.env` is correct (starts with `-100`)
4. ✅ Check logs for errors: `docker compose logs bot | grep -i error`

**Test manually:**
- Send content to bot
- Check admin chat for moderation message
- Click "✅ Approve and Publish"
- Wait 2 minutes (publication delay)
- Check channel for published content
- Check logs: `docker compose logs -f bot`

### Running Several Bots on One Server

This stack is designed to coexist with other bots on the same Docker host:

- **No host ports are published.** PostgreSQL and Redis are only reachable on the
  project's internal network, and the bot uses long-polling (no inbound port).
  So you will **not** hit "port already allocated" errors.
- **All resources are namespaced** by `COMPOSE_PROJECT_NAME`. Give each bot a
  unique value (e.g. `predlozhka`, `mybot2`) in its own `.env`, and its
  containers, network and volumes won't collide with other stacks.

To run a second instance, copy the project to another folder, set a different
`COMPOSE_PROJECT_NAME` (and a different `BOT_TOKEN`) in its `.env`, and run
`bash deploy.sh` there.

### Docker Daemon Not Running

**Windows:**
- Open Docker Desktop
- Wait for it to start
- Try command again

**Linux:**
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Permission Denied (Linux)

**Error:** `permission denied while trying to connect to Docker daemon`

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in, or:
newgrp docker

# Try command again
docker compose ps
```

---

## 📊 Monitoring

### Check Container Health

```bash
# Container status
docker compose ps

# Resource usage
docker stats tg-bot-prelozhka-bot tg-bot-prelozhka-postgres tg-bot-prelozhka-redis

# Logs from all services
docker compose logs --tail=100
```

### Check Disk Space

**Windows PowerShell:**
```powershell
docker system df
```

**Linux:**
```bash
docker system df

# Clean up unused data
docker system prune
```

---

## 🔄 Updating the Bot

### Update Bot Code

```bash
# Stop the bot
docker compose down

# Update code (if using git)
git pull

# Rebuild and start
docker compose up -d --build

# Check logs
docker compose logs -f bot
```

### Update Dependencies

```bash
# Rebuild with latest dependencies
docker compose build --no-cache bot
docker compose up -d

# Check for errors
docker compose logs bot
```

### Database Migration

Migrations run **automatically** on container start. To apply them manually
(e.g. without restarting), run:

```bash
docker compose exec bot alembic upgrade head
```

---

## ✅ Pre-Launch Checklist

Before running in production, ensure:

- [ ] ✅ Python 3.11+ installed
- [ ] ✅ Docker and Docker Compose installed
- [ ] ✅ `.env` file created with all required values
- [ ] ✅ Unique `COMPOSE_PROJECT_NAME` set (if sharing the host with other bots)
- [ ] ✅ Strong passwords set for `DB_PASSWORD` and `REDIS_PASSWORD`
- [ ] ✅ `ADMIN_IDS` in `.env` contains your admin user ID(s)
- [ ] ✅ Bot created via @BotFather
- [ ] ✅ Bot added to admin chat as administrator
- [ ] ✅ Bot added to channel as administrator with "Post messages" permission
- [ ] ✅ All IDs (channel, chat, user) are correct
- [ ] ✅ Configuration verified: `python verify_deployment.py`
- [ ] ✅ Bot tested: send `/start`, submit content, moderate in admin chat
- [ ] ✅ Publication tested: approve content, wait 2 minutes, check channel

---

## 📞 Support

If you encounter issues:

1. **Check logs:** `docker compose logs bot`
2. **Verify configuration:** `python verify_deployment.py` (or `python3 verify_deployment.py` on Linux)
3. **Review this guide** for missed steps
4. **Check all IDs** (channel, chat, user) are correct
5. **Verify bot permissions** in channel and admin chat

---

**Good luck with your UGC bot! 🚀**

**Удачи с вашим UGC ботом! 🚀**
