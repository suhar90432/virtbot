#!/usr/bin/env python3
"""
Setup script to configure .env from Replit environment or create defaults.
Run this before bot.py to ensure all required variables are set.
"""

import os
import sys
from pathlib import Path

def setup_env():
    """Create .env file with defaults if missing critical vars."""
    env_path = Path(__file__).parent / ".env"
    
    # Check if .env exists and has critical vars
    if env_path.exists():
        with open(env_path) as f:
            content = f.read()
            if "BOT_TOKEN" in content and "WEBAPP_URL" in content:
                print("✅ .env already configured")
                return
    
    # Create minimal .env with defaults
    defaults = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN", "9214718186:AAHCHRHbI6DF1ahlwUswY9cvIBzz0WF1W9c"),
        "BOT_USERNAME": os.getenv("BOT_USERNAME", "BuyVirtssbot"),
        "ADMIN_IDS": os.getenv("ADMIN_IDS", "0"),
        "SHOP_NAME": os.getenv("SHOP_NAME", "Вирты Маджестик"),
        "CURRENCY": os.getenv("CURRENCY", "₽"),
        "MIN_TOPUP": os.getenv("MIN_TOPUP", "100"),
        "MIN_KK": os.getenv("MIN_KK", "1.0"),
        "WEBAPP_HOST": os.getenv("WEBAPP_HOST", "0.0.0.0"),
        "WEBAPP_PORT": os.getenv("WEBAPP_PORT", "8080"),
        # Try to detect Replit dev URL from environment
        "WEBAPP_URL": os.getenv("WEBAPP_URL", _get_replit_dev_url()),
        "RESTART_SECRET": os.getenv("RESTART_SECRET", "virtbot-restart-2024-secret-key"),
        "TELEGRAM_IP": os.getenv("TELEGRAM_IP", ""),
        "PROXY_URL": os.getenv("PROXY_URL", ""),
        "PROXY_FILE": os.getenv("PROXY_FILE", ""),
        "NET_RETRIES": os.getenv("NET_RETRIES", "4"),
        "NET_TIMEOUT": os.getenv("NET_TIMEOUT", "30"),
    }
    
    # Write .env
    with open(env_path, "w") as f:
        for key, value in defaults.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Created .env at {env_path}")
    print(f"   WEBAPP_URL: {defaults['WEBAPP_URL']}")


def _get_replit_dev_url() -> str:
    """Try to detect Replit dev URL from environment."""
    # Check if running on Replit
    if "REPLIT_HOME" in os.environ or "REPLIT_DB_URL" in os.environ:
        # Try to get from REPLIT_DEV_DOMAIN if available
        if "REPLIT_DEV_DOMAIN" in os.environ:
            return f"https://{os.environ['REPLIT_DEV_DOMAIN']}"
        # Fallback to generic Replit detection
        return "https://replit.dev"  # Will be replaced at runtime
    
    # Default fallback
    return "https://fb218da8-6665-478e-b7f8-ea5765b00c80-00-2e6ufi9c4x0y9.sisko.replit.dev"


if __name__ == "__main__":
    setup_env()
    sys.exit(0)
