#!/usr/bin/env python3
"""
Простой скрипт для перезагрузки VirtBot через встроенный /restart endpoint.

Использование:
    python restart_virtbot.py [URL] [SECRET]

Примеры:
    python restart_virtbot.py https://virtbot.replit.dev virtbot-restart-2024-secret-key
    python restart_virtbot.py  # будет запрашивать интерактивно
"""

import sys
import urllib.request
import urllib.error
import json
from urllib.parse import urljoin

DEFAULT_URL = "https://fb218da8-6665-478e-b7f8-ea5765b00c80-00-2e6ufi9c4x0y9.sisko.replit.dev"
DEFAULT_SECRET = "virtbot-restart-2024-secret-key"


def restart_bot(base_url: str, restart_key: str) -> bool:
    """Отправить запрос на перезагрузку бота."""
    restart_url = urljoin(base_url, f"/restart?key={restart_key}")
    
    print(f"📡 Отправляю запрос на {restart_url}...")
    
    try:
        with urllib.request.urlopen(restart_url, timeout=10) as response:
            if response.status == 200:
                result = json.loads(response.read().decode())
                print(f"✅ Успех! Ответ от сервера:")
                print(f"   Status: {result.get('status')}")
                print(f"   Message: {result.get('message')}")
                print(f"   Time: {result.get('timestamp')}")
                print("\n⏳ Бот перезагружается... (ждите 10-20 секунд)")
                return True
            else:
                print(f"❌ Ошибка: сервер вернул статус {response.status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"❌ Ошибка 401: неверный ключ перезагрузки")
        elif e.code == 403:
            print(f"❌ Ошибка 403: перезагрузка отключена (RESTART_SECRET не задан)")
        else:
            print(f"❌ HTTP ошибка {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Ошибка подключения: {e.reason}")
        print(f"   Проверьте:")
        print(f"   1. Правильность URL: {base_url}")
        print(f"   2. Доступность бота в интернете")
        print(f"   3. Что бот запущен и слушает на {base_url}/health")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


def main():
    # Получить параметры из аргументов или использовать значения по умолчанию
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    restart_key = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SECRET
    
    print("=" * 60)
    print("VirtBot Restart Automation")
    print("=" * 60)
    
    # Валидация URL
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    
    base_url = base_url.rstrip("/")
    
    print(f"🔗 URL бота: {base_url}")
    print(f"🔑 Секретный ключ: {restart_key[:10]}...")
    print()
    
    # Сначала проверим health endpoint
    print("🩺 Проверяю доступность бота...")
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
            if response.status == 200:
                health = json.loads(response.read().decode())
                print(f"✅ Бот доступен! Время сервера: {health.get('time')}")
            else:
                print(f"⚠️  Health endpoint вернул {response.status}")
    except Exception as e:
        print(f"⚠️  Бот может быть недоступен: {e}")
        print()
        confirm = input("Продолжить попытку перезагрузки? (да/нет): ").strip().lower()
        if confirm not in ("да", "yes", "y", "д"):
            print("Отмена.")
            return False
    
    print()
    
    # Запросить перезагрузку
    if restart_bot(base_url, restart_key):
        print("\n" + "=" * 60)
        print("🎉 Перезагрузка инициирована успешно!")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("⚠️  Не удалось перезагрузить бота")
        print("=" * 60)
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
