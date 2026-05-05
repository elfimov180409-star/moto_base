# 🏍️ MotoBase

Веб-сайт для сравнения мотоциклов: каталог 130+ моделей, фильтры по правам/категориям/объёму, сортировка, графики цен по годам, AI-советник (Claude), 3 языка (RU/EN/PL).

## Локальный запуск

```
pip3 install -r requirements.txt
python3 download_images.py    # один раз — скачает фото
python3 process_images.py     # опц. — унификация фона (rembg)
python3 app.py                # запуск
```

Сайт: http://127.0.0.1:5001

## Переменные окружения

Скопируй `.env.example` в `.env` и заполни:

- `ANTHROPIC_API_KEY` — для AI-советника
- `GA_MEASUREMENT_ID` — для Google Analytics
- `ADSENSE_CLIENT`, `SHOW_ADS=true` — для рекламы (когда наберётся трафик)
- `AFFILIATE_ENABLED=true` — для партнёрских ссылок (Revzilla)
- `SECRET_KEY` — длинная случайная строка

Flask читает их через `from config import Config` (см. `config.py`).

## Деплой на Render.com (бесплатно)

1. github.com → новый репозиторий → залей через GitHub Desktop или CLI
2. render.com → New Web Service → подключи репо
3. Render автоматически прочитает `render.yaml`
4. Environment Variables → добавь `ANTHROPIC_API_KEY=sk-ant-...`
5. Через 3 минуты сайт доступен по `https://motobase-XXXX.onrender.com`

## Свой домен

1. Купи на porkbun.com или namecheap.com (~$10/год)
2. Render → Settings → Custom Domains → Add
3. В DNS регистратора добавь CNAME-запись, которую покажет Render
4. Через 30 минут работает на твоём домене

## Монетизация

Три потока (все опциональны, включаются переменными окружения):

1. **Партнёрские ссылки** (`AFFILIATE_ENABLED=true`) — на странице сравнения появляется блок «Готов к покупке?» с реферальными ссылками на Revzilla.
2. **AdSense** (`SHOW_ADS=true` + `ADSENSE_CLIENT=ca-pub-...`) — рекламный слот после сравнения.
3. **Premium $4/мес** — каркас в `/pricing`, нужна интеграция Stripe.

## Добавить мотоцикл

В `app.py` в списке `MOTORCYCLES` добавь запись через хелпер `m()` со всеми полями. Категория прав вычислится автоматически. Затем:

```
python3 download_images.py    # скачает только новые фото
python3 process_images.py     # выровняет фон
```

## Структура

```
app.py                  # Flask, MOTORCYCLES, роуты, AI-прокси, license_category
config.py               # настройки через env vars
download_images.py      # DDG поиск фото
process_images.py       # rembg → серый фон 800x600
render.yaml             # деплой на Render одной кнопкой
templates/
  index.html            # каталог
  compare.html          # сравнение 2-4 моделей
  pricing.html          # тарифы Free/Premium
  error.html            # 404/429/500
static/
  css/                  # светлая+тёмная темы
  js/catalog.js         # фильтры, сортировка, поиск, variant picker
  js/compare.js         # графики, AI анализ
  images/               # фото
```

## Лицензия

Личный пет-проект. Используй как хочешь.
