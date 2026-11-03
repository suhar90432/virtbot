#!/usr/bin/env python3
"""VirtBot Monitoring & Auto-Restart Service

Полностью автоматический мониторинг без ручного вмешательства.
Проверяет статус бота каждые 2 минуты и перезагружает при падении.
Использует только встроенные модули Python (urllib, без curl).
"""
import subprocess
import time
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Configuration
REPLIT_URL = "https://fb218da8-6665-478e-b7f8-ea5765b00c80-00-2e6ufi9c4x0y9.sisko.replit.dev"
HEALTH_ENDPOINT = f"{REPLIT_URL}/app"
RESTART_ENDPOINT = f"{REPLIT_URL}/restart"
RESTART_SECRET = "virtbot-restart-2024-secret-key"
CHECK_INTERVAL = 120  # 2 minutes
MAX_RETRIES = 3
TIMEOUT = 10  # seconds

LOG_FILE = Path(__file__).parent / "bot_monitor.log"


def log(message: str, level: str = "INFO") -> None:
    """Write log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {level}: {message}"
    print(log_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_message + "\n")


def check_bot_health() -> bool:
    """Check if bot is responding using urllib (no curl dependency)."""
    import urllib.request
    import urllib.error
    
    try:
        with urllib.request.urlopen(HEALTH_ENDPOINT, timeout=TIMEOUT) as response:
            # Bot is up if we get HTTP 200 and some content
            is_up = response.status == 200 and len(response.read()) > 0
            if is_up:
                log("✅ Bot health check passed", "DEBUG")
            else:
                log(f"❌ Bot health check failed (HTTP {response.status})", "WARNING")
            return is_up
    except urllib.error.HTTPError as e:
        log(f"❌ Bot health check failed (HTTP {e.code})", "WARNING")
        return False
    except urllib.error.URLError as e:
        log(f"⚠️ Connection error during health check: {e.reason}", "WARNING")
        return False
    except Exception as e:
        log(f"🔴 Health check error: {e}", "ERROR")
        return False


def restart_bot() -> bool:
    """Trigger bot restart via /restart endpoint using urllib (no curl dependency)."""
    import urllib.request
    import urllib.error
    
    restart_url_with_key = f"{RESTART_ENDPOINT}?key={RESTART_SECRET}"
    
    try:
        log(f"Sending restart request to {restart_url_with_key[:50]}...", "DEBUG")
        with urllib.request.urlopen(restart_url_with_key, timeout=TIMEOUT) as response:
            if response.status == 200:
                log("✅ Restart signal sent successfully", "INFO")
                return True
            else:
                log(f"❌ Restart failed (HTTP {response.status})", "ERROR")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            log(f"❌ Invalid restart key (401)", "ERROR")
        elif e.code == 403:
            log(f"❌ Restart disabled - RESTART_SECRET not configured (403)", "ERROR")
        else:
            log(f"❌ HTTP error {e.code}: {e.reason}", "ERROR")
        return False
    except urllib.error.URLError as e:
        log(f"❌ Connection error: {e.reason}", "ERROR")
        return False
    except Exception as e:
        log(f"🔴 Restart error: {e}", "ERROR")
        return False


def monitor_loop() -> None:
    """Main monitoring loop."""
    log("🚀 VirtBot Monitor started", "INFO")
    log(f"Checking every {CHECK_INTERVAL} seconds", "INFO")
    
    consecutive_failures = 0
    
    while True:
        try:
            if check_bot_health():
                consecutive_failures = 0
                log(f"✅ Bot is healthy", "DEBUG")
            else:
                consecutive_failures += 1
                log(f"⚠️ Health check #{consecutive_failures} failed", "WARNING")
                
                if consecutive_failures >= MAX_RETRIES:
                    log(f"🔴 Bot down {consecutive_failures} times, initiating restart", "ERROR")
                    if restart_bot():
                        log("⏳ Waiting 30 seconds for restart...", "INFO")
                        time.sleep(30)
                        consecutive_failures = 0
                    else:
                        log("❌ Restart failed, will retry in next cycle", "ERROR")
            
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log("🛑 Monitor stopped by user", "INFO")
            sys.exit(0)
        except Exception as e:
            log(f"🔴 Unexpected error in monitor loop: {e}", "ERROR")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    log("=" * 60, "INFO")
    log("VirtBot 24/7 Monitoring Service", "INFO")
    log(f"Replit Project: {REPLIT_URL}", "INFO")
    log("=" * 60, "INFO")
    
    monitor_loop()
