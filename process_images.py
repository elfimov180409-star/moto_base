"""
Унификация фото мотоциклов: удаляет фон, ставит светло-серый,
кропит до 800x600.

Запуск (один раз):
    pip3 install rembg pillow onnxruntime
    python3 process_images.py

Результат — в static/images_clean/. После проверки можно перенести
в static/images/ (см. README.md, раздел "Унификация фото").
"""
import os
import sys
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    print("Нужен Pillow. Установи: pip3 install pillow")
    sys.exit(1)

try:
    from rembg import remove
except ImportError:
    print("Нужен rembg. Установи: pip3 install rembg pillow onnxruntime")
    sys.exit(1)

SRC_DIR = "static/images"
DST_DIR = "static/images_clean"
TARGET_W, TARGET_H = 800, 600
BG_COLOR = (240, 240, 236)  # #f0f0ec — bg3 светлой темы

os.makedirs(DST_DIR, exist_ok=True)


def process(src_path, dst_path):
    """Удалить фон, поставить нейтральный, кропнуть до 800x600."""
    with open(src_path, "rb") as f:
        input_bytes = f.read()
    output_bytes = remove(input_bytes)  # PNG с прозрачностью

    img = Image.open(BytesIO(output_bytes)).convert("RGBA")

    bg = Image.new("RGB", img.size, BG_COLOR)
    bg.paste(img, mask=img.split()[3])  # alpha-канал как маска

    # Cover: подгоняем под 800x600 с сохранением пропорций
    src_ratio = bg.width / bg.height
    dst_ratio = TARGET_W / TARGET_H
    if src_ratio > dst_ratio:
        new_w = int(bg.height * dst_ratio)
        offset = (bg.width - new_w) // 2
        bg = bg.crop((offset, 0, offset + new_w, bg.height))
    else:
        new_h = int(bg.width / dst_ratio)
        offset = (bg.height - new_h) // 2
        bg = bg.crop((0, offset, bg.width, offset + new_h))

    bg = bg.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    bg.save(dst_path, "JPEG", quality=88)


def main():
    if not os.path.isdir(SRC_DIR):
        print(f"Папка {SRC_DIR} не найдена. Сначала запусти download_images.py")
        sys.exit(1)
    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".jpg"))
    if not files:
        print(f"В {SRC_DIR} нет .jpg файлов")
        sys.exit(1)
    print(f"Обрабатываю {len(files)} фото...\n")
    for i, name in enumerate(files, 1):
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(DST_DIR, name)
        if os.path.exists(dst):
            print(f"[{i}/{len(files)}] ✓ Пропуск: {name}")
            continue
        try:
            process(src, dst)
            print(f"[{i}/{len(files)}] ✓ {name}")
        except Exception as e:
            print(f"[{i}/{len(files)}] ✗ {name}: {e}")

    print(f"\nГотово. Результат: {DST_DIR}/")
    print("Чтобы применить — переименуй images_clean в images "
          "(сначала сделай бэкап images!)")


if __name__ == "__main__":
    main()
