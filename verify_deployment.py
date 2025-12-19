#!/usr/bin/env python3
"""Deployment verification script for the Telegram UGC Bot.

This script verifies that all components are properly configured
and ready for deployment.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    exists = os.path.isfile(filepath)
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    print(f"{status} {description}: {filepath}")
    return exists


def check_dir_exists(dirpath: str, description: str) -> bool:
    """Check if a directory exists."""
    exists = os.path.isdir(dirpath)
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    print(f"{status} {description}: {dirpath}")
    return exists


def check_env_file() -> Tuple[bool, List[str]]:
    """Check if .env file exists and has required variables."""
    env_file = '.env'
    
    if not os.path.isfile(env_file):
        print(f"{YELLOW}⚠{RESET} .env file not found (copy .env.example and configure)")
        return False, []
    
    required_vars = [
        'BOT_TOKEN',
        'CHANNEL_ID',
        'ADMIN_CHAT_ID',
        'ERROR_CHAT_ID',
        'DB_HOST',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
        'REDIS_HOST',
        'REDIS_PASSWORD'
    ]
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    missing = []
    for var in required_vars:
        if var not in content or f"{var}=" not in content:
            missing.append(var)
    
    if missing:
        print(f"{YELLOW}⚠{RESET} Missing environment variables: {', '.join(missing)}")
        return False, missing
    else:
        print(f"{GREEN}✓{RESET} All required environment variables present in .env")
        return True, []


def verify_project_structure() -> Dict[str, bool]:
    """Verify the complete project structure."""
    
    print("\n" + "=" * 60)
    print("TELEGRAM UGC BOT - DEPLOYMENT VERIFICATION")
    print("=" * 60)
    
    results = {}
    
    # Core application files
    print("\n📦 Core Application Files:")
    results['main'] = check_file_exists('bot/main.py', 'Main entry point')
    results['models'] = check_file_exists('bot/models/database.py', 'Database models')
    
    # Handlers
    print("\n🎮 Handler Files:")
    results['user_handlers'] = check_file_exists('bot/handlers/user_handlers.py', 'User handlers')
    results['admin_handlers'] = check_file_exists('bot/handlers/admin_handlers.py', 'Admin handlers')
    results['stats_handlers'] = check_file_exists('bot/handlers/statistics_handlers.py', 'Statistics handlers')
    
    # Services
    print("\n⚙️  Service Files:")
    services = [
        ('bot/services/rate_limit.py', 'Rate limiting'),
        ('bot/services/user_service.py', 'User service'),
        ('bot/services/submission_service.py', 'Submission service'),
        ('bot/services/decision_manager.py', 'Decision manager'),
        ('bot/services/publication_service.py', 'Publication service'),
        ('bot/services/notification_service.py', 'Notification service'),
        ('bot/services/statistics_service.py', 'Statistics service'),
        ('bot/services/error_handler.py', 'Error handler'),
        ('bot/services/recovery_service.py', 'Recovery service'),
    ]
    for filepath, desc in services:
        check_file_exists(filepath, desc)
    
    # Utilities
    print("\n🔧 Utility Files:")
    utilities = [
        ('bot/utils/config.py', 'Configuration loader'),
        ('bot/utils/database.py', 'Database manager'),
        ('bot/utils/redis_manager.py', 'Redis manager'),
        ('bot/utils/logging.py', 'Logging setup'),
        ('bot/utils/health.py', 'Health checks'),
        ('bot/utils/states.py', 'FSM states'),
    ]
    for filepath, desc in utilities:
        check_file_exists(filepath, desc)
    
    # Configuration
    print("\n⚙️  Configuration Files:")
    results['config_json'] = check_file_exists('config/config.json', 'Bot configuration')
    results['messages_json'] = check_file_exists('config/messages.json', 'Messages configuration')
    
    # Infrastructure
    print("\n🐳 Infrastructure Files:")
    results['dockerfile'] = check_file_exists('Dockerfile', 'Dockerfile')
    results['docker_compose'] = check_file_exists('docker-compose.yml', 'Docker Compose')
    results['requirements'] = check_file_exists('requirements.txt', 'Python requirements')
    
    # Database migrations
    print("\n🗄️  Database Migration Files:")
    results['alembic_ini'] = check_file_exists('alembic.ini', 'Alembic config')
    results['migration_env'] = check_file_exists('migrations/env.py', 'Migration environment')
    results['migration_init'] = check_file_exists('migrations/versions/001_initial_schema.py', 'Initial migration')
    
    # Environment
    print("\n🔐 Environment Configuration:")
    results['env_example'] = check_file_exists('.env.example', 'Environment example')
    env_ok, missing_vars = check_env_file()
    results['env'] = env_ok
    
    # Documentation
    print("\n📚 Documentation Files:")
    results['readme'] = check_file_exists('README.md', 'README')
    results['impl_guide'] = check_file_exists('IMPLEMENTATION_GUIDE.md', 'Implementation guide')
    
    return results


def print_summary(results: Dict[str, bool]) -> None:
    """Print verification summary."""
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"\nTotal checks: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    
    if failed > 0:
        print(f"{RED}Failed: {failed}{RESET}")
        print(f"\n{YELLOW}⚠ Some checks failed. Please review the output above.{RESET}")
        return False
    else:
        print(f"{GREEN}✓ All checks passed!{RESET}")
        print(f"\n{GREEN}🎉 Bot is ready for deployment!{RESET}")
        return True


def print_next_steps() -> None:
    """Print next steps for deployment."""
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    
    print("""
1. Configure environment variables:
   cp .env.example .env
   # Edit .env with your actual values

2. Update admin configuration:
   # Edit config/config.json
   # Add your admin user IDs to the "administrators" array

3. Start the bot:
   docker-compose up -d --build

4. Check logs:
   docker-compose logs -f bot

5. Verify database migrations:
   docker-compose exec bot alembic current
   
6. Test the bot:
   - Send /start to your bot in Telegram
   - Try submitting content
   - Check admin chat for moderation

7. Monitor health:
   docker-compose ps
   docker-compose logs --tail=100 bot
""")


def main() -> int:
    """Main verification function."""
    
    # Change to project root directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run verification
    results = verify_project_structure()
    
    # Print summary
    all_passed = print_summary(results)
    
    # Print next steps
    if all_passed:
        print_next_steps()
        return 0
    else:
        print(f"\n{RED}Deployment verification failed. Please fix the issues above.{RESET}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
