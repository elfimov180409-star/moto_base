"""
Скрипт скачивания фото мотоциклов через DuckDuckGo Images.
Запуск: python3 download_images.py
"""
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request

from app import MOTORCYCLES

IMG_DIR = "static/images"
os.makedirs(IMG_DIR, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

# SSL: пытаемся использовать certifi, иначе fallback на unverified
# (на macOS с Python.org нет встроенных корневых сертификатов).
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl._create_unverified_context()


def get_ddg_token(query):
    url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&iax=images&ia=images"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
        html = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'vqd="([\d-]+)"', html) or re.search(r"vqd=([\d-]+)&", html)
    return m.group(1) if m else None


def find_image_url(query):
    token = get_ddg_token(query)
    if not token:
        return None
    # Фильтры DDG: type:photo (студийные приоритет), size:Large
    api = (f"https://duckduckgo.com/i.js?l=us-en&o=json"
           f"&q={urllib.parse.quote(query)}&vqd={token}"
           f"&f=,,,type:photo,size:Large&p=1")
    req = urllib.request.Request(api, headers={
        "User-Agent": UA,
        "Referer": "https://duckduckgo.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
            data = json.loads(r.read())
        for item in data.get("results", []):
            u = item.get("image", "")
            if u and any(u.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                return u
    except Exception:
        pass
    return None


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
        data = r.read()
    if len(data) < 5000:
        raise ValueError("Файл слишком маленький")
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def main():
    total = len(MOTORCYCLES)
    skipped = downloaded = failed = 0
    print(f"Загружаю фото для {total} мотоциклов...\n")
    for i, m in enumerate(MOTORCYCLES, 1):
        dest = f"{IMG_DIR}/{m['id']}.jpg"
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            print(f"[{i}/{total}] ✓ Уже есть: {m['brand']} {m['name']}")
            skipped += 1
            continue
        trim = f" {m['trim']}" if m["trim"] else ""
        query = f"{m['brand']} {m['name']}{trim} {m['year']} press photo studio side view"
        print(f"[{i}/{total}] {query}...", end=" ", flush=True)
        try:
            url = find_image_url(query)
            if not url:
                fallback = f"{m['brand']} {m['name']} motorcycle side"
                print(f"\n  fallback: {fallback}", end=" ", flush=True)
                url = find_image_url(fallback)
            if not url:
                print("✗ не найдено")
                failed += 1
                continue
            size = download(url, dest)
            print(f"✓ {size // 1024}KB")
            downloaded += 1
        except Exception as e:
            print(f"✗ {e}")
            failed += 1
        time.sleep(1.2)
    print(f"\nГотово! Скачано: {downloaded}, пропущено: {skipped}, ошибок: {failed}")


if __name__ == "__main__":
    main()
