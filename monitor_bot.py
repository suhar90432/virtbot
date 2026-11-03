#!/usr/bin/env python3
"""VirtBot Monitoring & Auto-Restart Service

Полностью автоматический мониторинг без ручного вмешательства.
Проверяет статус бота каждые 2 минуты и перезагружает при падении.
"""
import subprocess
import time
import sys
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
    """Check if bot is responding."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", str(TIMEOUT), HEALTH_ENDPOINT],
            capture_output=True,
            timeout=TIMEOUT + 5,
            text=True
        )
        # Bot is up if we get any response (not a Replit error page)
        is_up = result.returncode == 0 and len(result.stdout) > 0
        if is_up:
            log("✅ Bot health check passed", "DEBUG")
        else:
            log(f"❌ Bot health check failed (curl exit: {result.returncode})", "WARNING")
        return is_up
    except subprocess.TimeoutExpired:
        log("⏱️ Health check timeout", "WARNING")
        return False
    except Exception as e:
        log(f"🔴 Health check error: {e}", "ERROR")
        return False


def restart_bot() -> bool:
    """Trigger bot restart via /restart endpoint."""
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X", "POST",
                "-H", f"X-Restart-Secret: {RESTART_SECRET}",
                "-m", str(TIMEOUT),
                RESTART_ENDPOINT
            ],
            capture_output=True,
            timeout=TIMEOUT + 5,
            text=True
        )
        if result.returncode == 0:
            log("✅ Restart signal sent successfully", "INFO")
            return True
        else:
            log(f"❌ Restart failed (curl exit: {result.returncode})", "ERROR")
            return False
    except subprocess.TimeoutExpired:
        log("⏱️ Restart timeout", "WARNING")
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
                log(f"✅ Bot is healthy (check #{consecutive_failures + 1})", "DEBUG")
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
