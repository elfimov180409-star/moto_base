"""MotoBase — Flask backend: data, routes, AI proxy."""
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify, abort, g, Response

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Rate limiting (опционально — если flask-limiter установлен)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
    )
except ImportError:
    limiter = None


# Партнёрские ссылки и монетизация
AFFILIATE_LINKS = {
    "buy":       "https://www.revzilla.com/search?q={brand}+{name}&ref=motobase",
    "insurance": "https://compare.com/motorcycle-insurance?ref=motobase",
    "gear":      "https://www.revzilla.com/motorcycle-gear?ref=motobase",
}


def affiliate_url(kind, moto=None):
    if not app.config.get("AFFILIATE_ENABLED"):
        return None
    template = AFFILIATE_LINKS.get(kind, "#")
    if moto:
        return template.format(
            brand=moto.get("brand", "").replace(" ", "+"),
            name=moto.get("name", "").replace(" ", "+"),
        )
    return template


def is_premium_user(req):
    """Заглушка под premium. В будущем — JWT/cookie/БД."""
    return False

# ===== i18n =====
LANGS = ("ru", "en", "pl")
DEFAULT_LANG = "ru"

TYPE_NAMES = {
    "sport":       {"ru": "Спорт",          "en": "Sport",          "pl": "Sport"},
    "naked":       {"ru": "Naked",          "en": "Naked",          "pl": "Naked"},
    "sport-tour":  {"ru": "Спорт-туринг",   "en": "Sport-touring",  "pl": "Sport-turystyk"},
    "tour":        {"ru": "Туризм",         "en": "Tourer",         "pl": "Turystyk"},
    "tour-enduro": {"ru": "Тур-эндуро",     "en": "Adventure",      "pl": "Adventure"},
    "enduro":      {"ru": "Эндуро",         "en": "Enduro",         "pl": "Enduro"},
    "cruiser":     {"ru": "Круизер",        "en": "Cruiser",        "pl": "Cruiser"},
    "classic":     {"ru": "Классик",        "en": "Classic",        "pl": "Klasyk"},
    "supermoto":   {"ru": "Мотард",         "en": "Supermoto",      "pl": "Supermoto"},
    "motocross":   {"ru": "Кросс",          "en": "Motocross",      "pl": "Motocross"},
}

COUNTRY_TR = {
    "Япония":         {"en": "Japan",         "pl": "Japonia"},
    "Германия":       {"en": "Germany",       "pl": "Niemcy"},
    "Италия":         {"en": "Italy",         "pl": "Włochy"},
    "Великобритания": {"en": "UK",            "pl": "Wielka Brytania"},
    "Австрия":        {"en": "Austria",       "pl": "Austria"},
    "США":            {"en": "USA",           "pl": "USA"},
    "Индия":          {"en": "India",         "pl": "Indie"},
    "Испания":        {"en": "Spain",         "pl": "Hiszpania"},
}

COOLING_TR = {
    "жидкостное":         {"en": "liquid",      "pl": "płynne"},
    "воздушное":          {"en": "air",         "pl": "powietrzne"},
    "воздушно-масляное":  {"en": "air/oil",     "pl": "powietrzno-olejowe"},
}

TRANS_TR = {
    "механика": {"en": "manual",     "pl": "manualna"},
    "автомат":  {"en": "automatic",  "pl": "automatyczna"},
}

# Все строки UI. Ключи произвольные (en-snake-case), значения — переводы.
T = {
    # Header
    "ai_advisor":          {"ru": "AI советник",       "en": "AI advisor",         "pl": "Doradca AI"},
    "back_to_catalog":     {"ru": "← К каталогу",       "en": "← To catalog",        "pl": "← Do katalogu"},
    "site_subtitle_cmp":   {"ru": "Сравнение",         "en": "Compare",            "pl": "Porównanie"},
    "theme_toggle":        {"ru": "Переключить тему", "en": "Toggle theme",       "pl": "Przełącz motyw"},
    # Filters
    "filter_all":          {"ru": "Все",              "en": "All",                "pl": "Wszystkie"},
    "filter_license":      {"ru": "Права",            "en": "License",            "pl": "Prawo jazdy"},
    "filter_license_any":  {"ru": "Любые",            "en": "Any",                "pl": "Dowolne"},
    "filter_cc":           {"ru": "Объём",            "en": "Engine size",        "pl": "Pojemność"},
    "cc_to_125":           {"ru": "до 125",           "en": "up to 125",          "pl": "do 125"},
    "cc_126_500":          {"ru": "126–500",          "en": "126–500",            "pl": "126–500"},
    "cc_501_1000":         {"ru": "501–1000",         "en": "501–1000",           "pl": "501–1000"},
    "cc_1000_plus":        {"ru": "1000+",            "en": "1000+",              "pl": "1000+"},
    "sort_label":          {"ru": "Сортировка",       "en": "Sort by",            "pl": "Sortuj"},
    "sort_default":        {"ru": "Рекомендуемые",    "en": "Recommended",        "pl": "Polecane"},
    "sort_price_asc":      {"ru": "Цена: от низкой",  "en": "Price: low to high", "pl": "Cena: rosnąco"},
    "sort_price_desc":     {"ru": "Цена: от высокой", "en": "Price: high to low", "pl": "Cena: malejąco"},
    "sort_hp_asc":         {"ru": "Мощность: от низкой",  "en": "Power: low to high",   "pl": "Moc: rosnąco"},
    "sort_hp_desc":        {"ru": "Мощность: от высокой", "en": "Power: high to low",   "pl": "Moc: malejąco"},
    "sort_weight_asc":     {"ru": "Вес: от низкого",      "en": "Weight: low to high",  "pl": "Waga: rosnąco"},
    "sort_weight_desc":    {"ru": "Вес: от высокого",     "en": "Weight: high to low",  "pl": "Waga: malejąco"},
    "sort_year_desc":      {"ru": "Самые новые",          "en": "Newest first",         "pl": "Najnowsze"},
    "err_404":             {"ru": "Страница не найдена",
                            "en": "Page not found",
                            "pl": "Strona nie znaleziona"},
    "err_429":             {"ru": "Слишком много запросов. Попробуй через минуту.",
                            "en": "Too many requests. Try again in a minute.",
                            "pl": "Za dużo zapytań. Spróbuj za minutę."},
    "err_500":             {"ru": "Что-то пошло не так. Уже чиним.",
                            "en": "Something went wrong. We're on it.",
                            "pl": "Coś poszło nie tak. Naprawiamy."},
    "err_home":            {"ru": "На главную", "en": "Home", "pl": "Strona główna"},
    "page_pricing":        {"ru": "Тарифы",     "en": "Pricing", "pl": "Cennik"},
    "free_plan":           {"ru": "Бесплатно",  "en": "Free",    "pl": "Darmowy"},
    "premium_plan":        {"ru": "Premium",    "en": "Premium", "pl": "Premium"},
    "coming_soon":         {"ru": "Скоро доступно",
                            "en": "Coming soon",
                            "pl": "Wkrótce dostępne"},
    "search_placeholder":  {"ru": "Поиск: марка, модель, комплектация…",
                            "en": "Search: brand, model, trim…",
                            "pl": "Szukaj: marka, model, wersja…"},
    "filter_brand":        {"ru": "Марка",            "en": "Brand",              "pl": "Marka"},
    "filter_country":      {"ru": "Страна",           "en": "Country",            "pl": "Kraj"},
    "filter_year":         {"ru": "Год",              "en": "Year",               "pl": "Rok"},
    "filter_trans":        {"ru": "КПП",              "en": "Gearbox",            "pl": "Skrzynia"},
    "filter_hp_from":      {"ru": "л.с. от",          "en": "HP from",            "pl": "KM od"},
    "filter_price_to":     {"ru": "до $",             "en": "up to $",            "pl": "do $"},
    # Compare bar
    "selected_label":      {"ru": "Выбрано",          "en": "Selected",           "pl": "Wybrano"},
    "compare_hint":        {"ru": "выбери от 2 до 4 для сравнения",
                            "en": "pick 2 to 4 to compare",
                            "pl": "wybierz od 2 do 4 do porównania"},
    "compare_btn":         {"ru": "Сравнить →",       "en": "Compare →",          "pl": "Porównaj →"},
    "reset":               {"ru": "Сбросить",         "en": "Clear",              "pl": "Wyczyść"},
    # Cards
    "add_to_compare":      {"ru": "+ Добавить к сравнению",
                            "en": "+ Add to compare",
                            "pl": "+ Dodaj do porównania"},
    "in_compare":          {"ru": "✓ В сравнении",    "en": "✓ In compare",       "pl": "✓ W porównaniu"},
    "in_compare_n":        {"ru": "✓ {n} в сравнении",
                            "en": "✓ {n} in compare",
                            "pl": "✓ {n} w porównaniu"},
    "n_variants":          {"ru": "{n} вариантов",    "en": "{n} variants",       "pl": "{n} wersji"},
    "empty_results":       {"ru": "По заданным фильтрам мотоциклов не найдено.",
                            "en": "No motorcycles match the selected filters.",
                            "pl": "Brak motocykli pasujących do wybranych filtrów."},
    "models_label":        {"ru": "моделей",          "en": "models",             "pl": "modeli"},
    "variants_label":      {"ru": "вариантов",        "en": "variants",           "pl": "wersji"},
    # Variant picker
    "vm_pick":             {"ru": "Выбери год и комплектацию:",
                            "en": "Pick year and trim:",
                            "pl": "Wybierz rok i wersję:"},
    "vm_full":             {"ru": "Слот сравнения заполнен ({n}). Сначала сбрось выбор, чтобы добавить.",
                            "en": "Compare slot is full ({n}). Clear selection first.",
                            "pl": "Porównanie zapełnione ({n}). Najpierw wyczyść wybór."},
    "vm_confirm":          {"ru": "Добавить к сравнению",
                            "en": "Add to compare",
                            "pl": "Dodaj do porównania"},
    "vm_done":             {"ru": "Готово",          "en": "Done",               "pl": "Gotowe"},
    "vm_pick_multi":       {"ru": "Выбери варианты для сравнения. Клик переключает.",
                            "en": "Pick variants for comparison. Click to toggle.",
                            "pl": "Wybierz wersje do porównania. Kliknij, by przełączyć."},
    "vm_remove":           {"ru": "Убрать",          "en": "Remove",             "pl": "Usuń"},
    "vm_add":              {"ru": "Добавить",        "en": "Add",                "pl": "Dodaj"},
    "vm_in_compare":       {"ru": "в сравнении",      "en": "in compare",         "pl": "w porównaniu"},
    "close":               {"ru": "Закрыть",          "en": "Close",              "pl": "Zamknij"},
    # AI panel
    "ai_greeting":         {"ru": "Привет! Я помогу выбрать мотоцикл, сравнить модели или объяснить характеристики. Задавай вопросы.",
                            "en": "Hi! I'll help you pick a motorcycle, compare models, or explain specs. Ask anything.",
                            "pl": "Cześć! Pomogę wybrać motocykl, porównać modele lub wyjaśnić specyfikacje. Pytaj śmiało."},
    "ai_placeholder":      {"ru": "Задай вопрос…",    "en": "Ask a question…",    "pl": "Zadaj pytanie…"},
    "ai_thinking":         {"ru": "Думаю…",           "en": "Thinking…",          "pl": "Myślę…"},
    "ai_key_hint":         {"ru": "Ключ хранится только в браузере. Получить:",
                            "en": "Key is stored only in your browser. Get one at:",
                            "pl": "Klucz jest przechowywany tylko w przeglądarce. Pobierz na:"},
    "ai_save":             {"ru": "Сохранить",        "en": "Save",               "pl": "Zapisz"},
    "ai_no_key":           {"ru": "Сначала введи API ключ",
                            "en": "Enter API key first",
                            "pl": "Najpierw wprowadź klucz API"},
    "ai_key_short":        {"ru": "Ключ должен начинаться с sk-ant-",
                            "en": "Key must start with sk-ant-",
                            "pl": "Klucz musi zaczynać się od sk-ant-"},
    "ai_key_saved":        {"ru": "Ключ сохранён",    "en": "Key saved",          "pl": "Klucz zapisany"},
    "ai_key_cleared":      {"ru": "Ключ удалён",      "en": "Key removed",        "pl": "Klucz usunięty"},
    "ai_error":            {"ru": "Ошибка:",          "en": "Error:",             "pl": "Błąd:"},
    "ai_net_error":        {"ru": "Сетевая ошибка:",  "en": "Network error:",     "pl": "Błąd sieci:"},
    "ai_empty_reply":      {"ru": "(пустой ответ)",   "en": "(empty reply)",      "pl": "(pusta odpowiedź)"},
    # Compare page
    "cmp_prices":          {"ru": "Цены по годам",    "en": "Prices by year",     "pl": "Ceny według lat"},
    "available_since":     {"ru": "Доступен с {y} года",
                            "en": "Available since {y}",
                            "pl": "Dostępny od {y}"},
    "no_price_history":    {"ru": "Модель только вышла — истории цен пока нет",
                            "en": "New release — no price history yet",
                            "pl": "Nowy model — brak historii cen"},
    "cmp_specs":           {"ru": "Характеристики",   "en": "Specifications",     "pl": "Specyfikacje"},
    "cmp_filter_all":      {"ru": "Все",              "en": "All",                "pl": "Wszystkie"},
    "cmp_filter_same":     {"ru": "Одинаковые",       "en": "Same",               "pl": "Takie same"},
    "cmp_filter_diff":     {"ru": "Различия",         "en": "Different",          "pl": "Różne"},
    "cmp_ratings":         {"ru": "Рейтинги",         "en": "Ratings",            "pl": "Oceny"},
    "rating_power":        {"ru": "Мощь",             "en": "Power",              "pl": "Moc"},
    "rating_comfort":      {"ru": "Комфорт",          "en": "Comfort",            "pl": "Komfort"},
    "rating_handling":     {"ru": "Управляемость",    "en": "Handling",           "pl": "Prowadzenie"},
    "rating_value":        {"ru": "Цена/качество",    "en": "Value",              "pl": "Stosunek ceny do jakości"},
    "cmp_ai":              {"ru": "AI анализ",        "en": "AI analysis",        "pl": "Analiza AI"},
    "cmp_ai_cta":          {"ru": "Получи развёрнутое мнение мотожурналиста о сравнении.",
                            "en": "Get a detailed motorcycle journalist's take on the comparison.",
                            "pl": "Otrzymaj szczegółową opinię dziennikarza motocyklowego o porównaniu."},
    "cmp_ai_btn":          {"ru": "Получить AI анализ",
                            "en": "Get AI analysis",
                            "pl": "Uzyskaj analizę AI"},
    "cmp_ai_intro":        {"ru": "Введи API ключ Anthropic для AI анализа",
                            "en": "Enter Anthropic API key for AI analysis",
                            "pl": "Wprowadź klucz API Anthropic dla analizy AI"},
    "cmp_alts":            {"ru": "Другие сравнения", "en": "Other comparisons",  "pl": "Inne porównania"},
    "manufacturer_link":   {"ru": "Сайт производителя →",
                            "en": "Manufacturer's site →",
                            "pl": "Strona producenta →"},
    "cmp_analyzing":       {"ru": "Анализирую…",      "en": "Analyzing…",         "pl": "Analizuję…"},
    # Spec labels
    "spec_engine":         {"ru": "Двигатель",        "en": "Engine",             "pl": "Silnik"},
    "spec_displacement":   {"ru": "Объём",            "en": "Displacement",       "pl": "Pojemność"},
    "spec_power":          {"ru": "Мощность",         "en": "Power",              "pl": "Moc"},
    "spec_torque":         {"ru": "Крутящий момент",  "en": "Torque",             "pl": "Moment"},
    "spec_cylinders":      {"ru": "Цилиндров",        "en": "Cylinders",          "pl": "Cylindry"},
    "spec_cooling":        {"ru": "Охлаждение",       "en": "Cooling",            "pl": "Chłodzenie"},
    "spec_chassis":        {"ru": "Ходовая часть",    "en": "Chassis",            "pl": "Podwozie"},
    "spec_weight":         {"ru": "Снаряжённый вес",  "en": "Curb weight",        "pl": "Masa wł."},
    "spec_seat_height":    {"ru": "Высота сиденья",   "en": "Seat height",        "pl": "Wys. siodła"},
    "spec_consume":        {"ru": "Расход топлива",   "en": "Fuel cons.",         "pl": "Spalanie"},
    "spec_general":        {"ru": "Общее",            "en": "General",            "pl": "Ogólne"},
    "spec_transmission":   {"ru": "КПП",              "en": "Gearbox",            "pl": "Skrzynia"},
    "spec_country":        {"ru": "Страна",           "en": "Country",            "pl": "Kraj"},
    "spec_year":           {"ru": "Год",              "en": "Year",               "pl": "Rok"},
    "spec_price":          {"ru": "Цена",             "en": "Price",              "pl": "Cena"},
    # Units
    "u_cc":                {"ru": "куб.см",           "en": "cc",                 "pl": "cm³"},
    "u_hp":                {"ru": "л.с.",             "en": "HP",                 "pl": "KM"},
    "u_nm":                {"ru": "Нм",               "en": "Nm",                 "pl": "Nm"},
    "u_kg":                {"ru": "кг",               "en": "kg",                 "pl": "kg"},
    "u_mm":                {"ru": "мм",               "en": "mm",                 "pl": "mm"},
    "u_l_per_100":         {"ru": "л/100км",          "en": "L/100km",            "pl": "l/100km"},
    "u_year_short":        {"ru": "год",              "en": "yr",                 "pl": "rok"},
    # Plurals (3 forms separated by |)
    "p_year":              {"ru": "год|года|лет",
                            "en": "year|years|years",
                            "pl": "rok|lata|lat"},
    "p_trim":              {"ru": "комплектация|комплектации|комплектаций",
                            "en": "trim|trims|trims",
                            "pl": "wersja|wersje|wersji"},
    "p_variants":          {"ru": "вариант|варианта|вариантов",
                            "en": "variant|variants|variants",
                            "pl": "wersja|wersje|wersji"},
    "price_from":          {"ru": "от $",
                            "en": "from $",
                            "pl": "od $"},
    # AI prompts (keys)
    "ai_system_catalog":   {"ru": "Ты эксперт-консультант по мотоциклам на сайте MotoBase. Отвечай по-русски, конкретно и полезно.",
                            "en": "You are an expert motorcycle consultant on MotoBase. Reply in English, concretely and helpfully.",
                            "pl": "Jesteś ekspertem motocyklowym na MotoBase. Odpowiadaj po polsku, konkretnie i pomocnie."},
    "ai_system_compare":   {"ru": "Ты опытный мотожурналист. Пиши по-русски, живо и конкретно.",
                            "en": "You are an experienced motorcycle journalist. Write in English, vivid and concrete.",
                            "pl": "Jesteś doświadczonym dziennikarzem motocyklowym. Pisz po polsku, żywo i konkretnie."},
    "ai_compare_prompt":   {"ru": "Сравни {n} мотоцикла, дай развёрнутый аналитический обзор по-русски",
                            "en": "Compare {n} motorcycles, give a detailed analytical review in English",
                            "pl": "Porównaj {n} motocykli, dostarcz szczegółową analizę po polsku"},
    "ai_compare_steps":    {"ru": "4-6 абзацев без заголовков:\n1. Общее впечатление о каждом\n2. Сравнение характеристик\n3. Для кого идеален каждый\n4. Итоговый вывод",
                            "en": "4-6 paragraphs, no headings:\n1. Overall impression of each\n2. Spec comparison\n3. Ideal rider for each\n4. Final verdict",
                            "pl": "4-6 akapitów bez nagłówków:\n1. Ogólne wrażenie o każdym\n2. Porównanie specyfikacji\n3. Idealny kierowca dla każdego\n4. Końcowy werdykt"},
}


def get_lang():
    """Получить язык из ?lang=, иначе DEFAULT_LANG."""
    lang = request.args.get("lang", "").lower()
    if lang in LANGS:
        return lang
    return DEFAULT_LANG


def make_strings(lang):
    """Плоский словарь строк для текущего языка."""
    return {key: vals.get(lang, vals.get(DEFAULT_LANG, key)) for key, vals in T.items()}


def tr_country(c, lang):
    if lang == "ru":
        return c
    return COUNTRY_TR.get(c, {}).get(lang, c)


def tr_cooling(v, lang):
    if lang == "ru":
        return v
    return COOLING_TR.get(v, {}).get(lang, v)


def tr_trans(v, lang):
    if lang == "ru":
        return v
    return TRANS_TR.get(v, {}).get(lang, v)


def type_name(t, lang):
    return TYPE_NAMES.get(t, {}).get(lang, TYPE_NAMES.get(t, {}).get(DEFAULT_LANG, t))


def type_names_for(lang):
    """{type_key: localized_name} для текущего языка."""
    return {k: v.get(lang, v.get(DEFAULT_LANG, k)) for k, v in TYPE_NAMES.items()}


def localize_moto(moto, lang):
    """Возвращает копию записи с переведёнными country/cooling/transmission."""
    if lang == "ru":
        return moto
    out = dict(moto)
    out["country"] = tr_country(moto["country"], lang)
    out["cooling"] = tr_cooling(moto["cooling"], lang)
    out["transmission"] = tr_trans(moto["transmission"], lang)
    return out


@app.before_request
def detect_lang():
    g.lang = get_lang()


@app.context_processor
def inject_lang():
    return {
        "lang": g.lang,
        "t": make_strings(g.lang),
        "langs": LANGS,
        "config": app.config,
        "affiliate_url": affiliate_url,
    }


@app.template_filter("plural_t")
def plural_t_filter(n, forms_str):
    """Plural по правилам текущего языка (g.lang)."""
    forms = forms_str.split("|")
    n = abs(int(n))
    lang = getattr(g, "lang", DEFAULT_LANG)
    if lang == "en":
        return forms[0] if n == 1 else forms[1]
    last_two = n % 100
    if 11 <= last_two <= 14:
        return forms[2]
    last = n % 10
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def m(id, name, trim, brand, type_, year, cc, hp, torque, weight, price,
      consume, seat_height, cylinders, cooling, transmission, country, url, rating):
    return {
        "id": id, "name": name, "trim": trim, "brand": brand, "type": type_,
        "year": year, "cc": cc, "hp": hp, "torque": torque, "weight": weight,
        "price": price, "consume": consume, "seat_height": seat_height,
        "cylinders": cylinders, "cooling": cooling, "transmission": transmission,
        "country": country, "url": url, "image": "", "rating": rating,
    }


MOTORCYCLES = [
    # ===== Спорт =====
    m(1, "CBR600RR", "", "Honda", "sport", 2024, 599, 121, 65, 194, 11999, 6.0, 820, 4,
      "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CBR600RR/",
      {"power": 8, "comfort": 5, "handling": 9, "value": 7}),
    m(2, "CBR1000RR-R Fireblade", "", "Honda", "sport", 2024, 999, 215, 113, 201, 28999, 6.8, 830, 4,
      "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CBR1000RR-R/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 6}),
    m(3, "CBR1000RR-R Fireblade", "SP", "Honda", "sport", 2024, 999, 215, 113, 201, 34999, 6.8, 830, 4,
      "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CBR1000RR-R/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 5}),
    m(4, "YZF-R1", "", "Yamaha", "sport", 2024, 998, 200, 113, 201, 18399, 6.7, 855, 4,
      "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/yzf-r1/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 7}),
    m(5, "YZF-R1", "M", "Yamaha", "sport", 2024, 998, 200, 113, 202, 27199, 6.7, 855, 4,
      "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/yzf-r1m/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 6}),
    m(6, "Panigale V2", "", "Ducati", "sport", 2024, 955, 155, 104, 200, 17995, 6.5, 840, 2,
      "жидкостное", "механика", "Италия", "https://www.ducati.com/panigale-v2/",
      {"power": 9, "comfort": 5, "handling": 9, "value": 7}),
    m(7, "Panigale V4", "", "Ducati", "sport", 2024, 1103, 215, 124, 198, 24995, 7.0, 850, 4,
      "жидкостное", "механика", "Италия", "https://www.ducati.com/panigale-v4/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 7}),
    m(8, "Panigale V4", "S", "Ducati", "sport", 2024, 1103, 215, 124, 195, 30495, 7.0, 850, 4,
      "жидкостное", "механика", "Италия", "https://www.ducati.com/panigale-v4s/",
      {"power": 10, "comfort": 5, "handling": 10, "value": 6}),
    m(9, "Ninja ZX-10R", "", "Kawasaki", "sport", 2024, 998, 200, 114, 207, 17699, 6.9, 835, 4,
      "жидкостное", "механика", "Япония", "https://www.kawasaki.com/zx-10r/",
      {"power": 10, "comfort": 5, "handling": 9, "value": 8}),
    m(10, "GSX-R1000R", "", "Suzuki", "sport", 2024, 999, 199, 117, 203, 19099, 6.8, 825, 4,
       "жидкостное", "механика", "Япония", "https://www.suzukicycles.com/gsx-r1000r/",
       {"power": 10, "comfort": 5, "handling": 9, "value": 8}),
    m(11, "S1000RR", "", "BMW", "sport", 2024, 999, 210, 113, 197, 17895, 6.4, 824, 4,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/s1000rr/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 8}),
    m(12, "S1000RR", "M", "BMW", "sport", 2024, 999, 210, 113, 192, 24895, 6.4, 832, 4,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/m1000rr/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),

    # ===== Naked =====
    m(13, "MT-09", "", "Yamaha", "naked", 2021, 889, 119, 93, 189, 9999, 5.0, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-09/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 9}),
    m(14, "MT-09", "", "Yamaha", "naked", 2022, 889, 119, 93, 189, 10299, 5.0, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-09/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 9}),
    m(15, "MT-09", "", "Yamaha", "naked", 2023, 889, 119, 93, 193, 10499, 5.0, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-09/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 9}),
    m(16, "MT-09", "", "Yamaha", "naked", 2024, 889, 119, 93, 193, 10999, 5.0, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-09/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 9}),
    m(17, "MT-09", "SP", "Yamaha", "naked", 2024, 889, 119, 93, 193, 12299, 5.0, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-09sp/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 8}),
    m(18, "MT-07", "", "Yamaha", "naked", 2024, 689, 73, 67, 184, 8199, 4.3, 805, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-07/",
       {"power": 6, "comfort": 7, "handling": 9, "value": 10}),
    m(19, "Z900", "", "Kawasaki", "naked", 2024, 948, 125, 98, 212, 9499, 5.4, 820, 4,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z900/",
       {"power": 8, "comfort": 7, "handling": 8, "value": 9}),
    m(20, "Z650", "", "Kawasaki", "naked", 2024, 649, 67, 65, 187, 7849, 4.3, 790, 2,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z650/",
       {"power": 6, "comfort": 7, "handling": 8, "value": 9}),
    m(21, "F900R", "", "BMW", "naked", 2024, 895, 105, 92, 211, 9295, 5.0, 815, 2,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/f900r/",
       {"power": 7, "comfort": 7, "handling": 8, "value": 8}),
    m(22, "Street Triple RS", "", "Triumph", "naked", 2024, 765, 128, 80, 188, 13195, 5.0, 826, 3,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/street-triple-rs/",
       {"power": 9, "comfort": 7, "handling": 10, "value": 8}),
    m(23, "Speed Triple 1200 RS", "", "Triumph", "naked", 2024, 1160, 180, 125, 199, 19595, 6.5, 830, 3,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/speed-triple-1200-rs/",
       {"power": 10, "comfort": 7, "handling": 10, "value": 7}),
    m(24, "Monster 937", "", "Ducati", "naked", 2024, 937, 111, 93, 188, 13095, 5.5, 820, 2,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/monster/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 7}),
    m(25, "Streetfighter V4", "", "Ducati", "naked", 2024, 1103, 208, 123, 199, 21995, 7.0, 845, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/streetfighter-v4/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),
    m(26, "CB1000R", "", "Honda", "naked", 2024, 998, 145, 104, 213, 13099, 5.7, 830, 4,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CB1000R/",
       {"power": 8, "comfort": 7, "handling": 8, "value": 8}),
    m(27, "Duke 690", "", "KTM", "naked", 2024, 693, 75, 74, 149, 9499, 4.1, 835, 1,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/duke-690/",
       {"power": 7, "comfort": 6, "handling": 10, "value": 9}),

    # ===== Спорт-туринг =====
    m(29, "Ninja 1000SX", "", "Kawasaki", "sport-tour", 2024, 1043, 142, 111, 235, 13399, 6.0, 835, 4,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/ninja-1000sx/",
       {"power": 9, "comfort": 8, "handling": 8, "value": 9}),
    m(30, "FJR1300", "", "Yamaha", "sport-tour", 2024, 1298, 144, 138, 296, 17999, 7.2, 805, 4,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/fjr1300/",
       {"power": 9, "comfort": 9, "handling": 7, "value": 7}),
    m(31, "S1000XR", "", "BMW", "sport-tour", 2024, 999, 165, 114, 226, 18495, 6.0, 840, 4,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/s1000xr/",
       {"power": 10, "comfort": 9, "handling": 9, "value": 7}),

    # ===== Туризм =====
    m(32, "K1600GT", "", "BMW", "tour", 2024, 1649, 160, 180, 339, 26395, 6.7, 750, 6,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/k1600gt/",
       {"power": 10, "comfort": 10, "handling": 7, "value": 7}),
    m(33, "Gold Wing", "", "Honda", "tour", 2024, 1833, 124, 170, 363, 25500, 5.5, 745, 6,
       "жидкостное", "автомат", "Япония", "https://www.honda.co.jp/GoldWing/",
       {"power": 9, "comfort": 10, "handling": 7, "value": 8}),

    # ===== Тур-эндуро =====
    m(34, "R1300GS", "", "BMW", "tour-enduro", 2024, 1300, 145, 149, 237, 18895, 5.6, 850, 2,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/r1300gs/",
       {"power": 9, "comfort": 9, "handling": 9, "value": 8}),
    m(35, "R1300GS", "Adventure", "BMW", "tour-enduro", 2024, 1300, 145, 149, 269, 20895, 5.8, 870, 2,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/r1300gs-adventure/",
       {"power": 9, "comfort": 10, "handling": 8, "value": 8}),
    m(36, "Africa Twin 1100", "", "Honda", "tour-enduro", 2024, 1084, 102, 105, 226, 14999, 5.0, 850, 2,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/AfricaTwin/",
       {"power": 8, "comfort": 9, "handling": 9, "value": 9}),
    m(37, "Tracer 9 GT", "", "Yamaha", "sport-tour", 2024, 889, 119, 93, 220, 14999, 5.4, 825, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/tracer-9-gt/",
       {"power": 8, "comfort": 9, "handling": 9, "value": 9}),
    m(38, "Tracer 7", "", "Yamaha", "sport-tour", 2024, 689, 73, 67, 196, 9899, 4.3, 835, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/tracer-7/",
       {"power": 6, "comfort": 8, "handling": 8, "value": 10}),
    m(39, "Tiger 900", "Rally Pro", "Triumph", "tour-enduro", 2024, 888, 108, 87, 219, 16895, 5.2, 850, 3,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/tiger-900/",
       {"power": 8, "comfort": 9, "handling": 9, "value": 8}),
    m(40, "Multistrada V4", "", "Ducati", "sport-tour", 2024, 1158, 170, 125, 215, 21695, 6.0, 840, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/multistrada-v4/",
       {"power": 10, "comfort": 9, "handling": 9, "value": 7}),
    m(41, "1290 Super Adventure", "", "KTM", "tour-enduro", 2024, 1301, 160, 138, 240, 19999, 5.9, 849, 2,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/1290-super-adventure/",
       {"power": 10, "comfort": 9, "handling": 9, "value": 8}),
    m(42, "Pan America 1250", "", "Harley-Davidson", "tour-enduro", 2024, 1252, 150, 128, 245, 17499, 5.8, 855, 2,
       "жидкостное", "механика", "США", "https://www.harley-davidson.com/pan-america/",
       {"power": 9, "comfort": 9, "handling": 8, "value": 8}),

    # ===== Эндуро =====
    m(43, "790 Adventure", "", "KTM", "enduro", 2024, 799, 95, 88, 189, 13499, 4.5, 830, 2,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/790-adventure/",
       {"power": 7, "comfort": 7, "handling": 10, "value": 8}),

    # ===== Круизер =====
    m(44, "Fat Boy", "114", "Harley-Davidson", "cruiser", 2024, 1868, 93, 155, 317, 22099, 5.4, 675, 2,
       "воздушно-масляное", "механика", "США", "https://www.harley-davidson.com/fat-boy/",
       {"power": 7, "comfort": 8, "handling": 5, "value": 7}),
    m(45, "Scout", "", "Indian", "cruiser", 2024, 1133, 100, 97, 246, 13499, 5.0, 643, 2,
       "жидкостное", "механика", "США", "https://www.indianmotorcycle.com/scout/",
       {"power": 7, "comfort": 8, "handling": 7, "value": 8}),
    m(46, "Vulcan S", "", "Kawasaki", "cruiser", 2024, 649, 61, 63, 235, 7599, 4.4, 705, 2,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/vulcan-s/",
       {"power": 5, "comfort": 8, "handling": 6, "value": 9}),
    m(47, "Rocket 3 R", "", "Triumph", "cruiser", 2024, 2458, 165, 221, 291, 24295, 6.8, 773, 3,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/rocket-3-r/",
       {"power": 10, "comfort": 8, "handling": 7, "value": 7}),

    # ===== Классик =====
    m(48, "Bonneville T120", "", "Triumph", "classic", 2024, 1200, 80, 105, 236, 12595, 4.4, 790, 2,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/bonneville-t120/",
       {"power": 6, "comfort": 8, "handling": 7, "value": 7}),
    m(49, "R nineT", "", "BMW", "classic", 2024, 1170, 109, 116, 222, 15995, 5.3, 805, 2,
       "воздушно-масляное", "механика", "Германия", "https://www.bmw-motorrad.com/r-ninet/",
       {"power": 8, "comfort": 7, "handling": 8, "value": 7}),
    m(50, "Z900RS", "", "Kawasaki", "classic", 2024, 948, 110, 98, 215, 11999, 5.2, 820, 4,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z900rs/",
       {"power": 8, "comfort": 8, "handling": 8, "value": 9}),

    # ===== Мотард =====
    m(51, "701 Supermoto", "", "Husqvarna", "supermoto", 2024, 693, 74, 71, 149, 11999, 4.3, 890, 1,
       "жидкостное", "механика", "Австрия", "https://www.husqvarna-motorcycles.com/701-supermoto/",
       {"power": 7, "comfort": 5, "handling": 10, "value": 7}),

    # ===== Кросс =====
    m(52, "KX450", "", "Kawasaki", "motocross", 2024, 449, 55, 50, 110, 10299, 6.5, 960, 1,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/kx450/",
       {"power": 8, "comfort": 3, "handling": 10, "value": 8}),
    m(53, "CRF450R", "", "Honda", "motocross", 2024, 449, 55, 49, 110, 9799, 6.5, 965, 1,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CRF450R/",
       {"power": 8, "comfort": 3, "handling": 10, "value": 9}),
    m(54, "YZ450F", "", "Yamaha", "motocross", 2024, 450, 56, 51, 111, 9999, 6.5, 965, 1,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/yz450f/",
       {"power": 8, "comfort": 3, "handling": 10, "value": 9}),
    m(55, "450 SX-F", "", "KTM", "motocross", 2024, 450, 60, 52, 105, 11199, 6.5, 960, 1,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/450-sx-f/",
       {"power": 9, "comfort": 3, "handling": 10, "value": 8}),

    # ===== Дополнительные модели =====
    # Спорт
    m(56, "RSV4", "", "Aprilia", "sport", 2024, 1099, 217, 125, 202, 19999, 7.0, 845, 4,
       "жидкостное", "механика", "Италия", "https://www.aprilia.com/rsv4/",
       {"power": 10, "comfort": 5, "handling": 10, "value": 7}),
    m(57, "YZF-R6", "", "Yamaha", "sport", 2020, 599, 117, 61, 190, 12299, 6.5, 850, 4,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/yzf-r6/",
       {"power": 8, "comfort": 4, "handling": 10, "value": 7}),
    m(58, "GSX-R750", "", "Suzuki", "sport", 2024, 750, 148, 86, 190, 13099, 6.5, 810, 4,
       "жидкостное", "механика", "Япония", "https://www.suzukicycles.com/gsx-r750/",
       {"power": 9, "comfort": 5, "handling": 9, "value": 8}),
    m(60, "YZF-R7", "", "Yamaha", "sport", 2024, 689, 73, 67, 188, 9199, 4.3, 835, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/yzf-r7/",
       {"power": 7, "comfort": 5, "handling": 9, "value": 9}),

    # Naked / streetfighter
    m(61, "Tuono V4", "", "Aprilia", "naked", 2024, 1077, 175, 121, 213, 16299, 6.5, 825, 4,
       "жидкостное", "механика", "Италия", "https://www.aprilia.com/tuono-v4/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),
    m(62, "Tuono 660", "", "Aprilia", "naked", 2024, 659, 95, 67, 183, 10499, 4.5, 820, 2,
       "жидкостное", "механика", "Италия", "https://www.aprilia.com/tuono-660/",
       {"power": 7, "comfort": 7, "handling": 9, "value": 8}),
    m(63, "Trident 660", "", "Triumph", "naked", 2024, 660, 81, 64, 189, 8595, 4.6, 805, 3,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/trident-660/",
       {"power": 7, "comfort": 7, "handling": 8, "value": 10}),
    m(64, "CB650R", "", "Honda", "naked", 2024, 649, 94, 64, 202, 9499, 5.5, 810, 4,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/CB650R/",
       {"power": 7, "comfort": 7, "handling": 8, "value": 9}),
    m(65, "XSR900", "", "Yamaha", "naked", 2024, 889, 119, 93, 193, 10499, 5.0, 810, 3,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/xsr900/",
       {"power": 8, "comfort": 7, "handling": 9, "value": 9}),
    m(66, "890 Duke R", "", "KTM", "naked", 2024, 889, 121, 99, 169, 11999, 4.5, 834, 2,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/890-duke-r/",
       {"power": 8, "comfort": 6, "handling": 10, "value": 8}),
    m(67, "1290 Super Duke R", "", "KTM", "naked", 2024, 1301, 180, 140, 189, 19499, 6.0, 835, 2,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/1290-super-duke-r/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),
    m(68, "SV650", "", "Suzuki", "naked", 2024, 645, 75, 64, 198, 7299, 4.6, 785, 2,
       "жидкостное", "механика", "Япония", "https://www.suzukicycles.com/sv650/",
       {"power": 6, "comfort": 7, "handling": 8, "value": 10}),
    m(69, "R1300R", "", "BMW", "naked", 2024, 1300, 145, 149, 239, 15995, 5.6, 820, 2,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/r1300r/",
       {"power": 9, "comfort": 8, "handling": 8, "value": 8}),
    m(70, "Svartpilen 401", "", "Husqvarna", "naked", 2024, 399, 45, 39, 158, 5999, 3.5, 820, 1,
       "жидкостное", "механика", "Австрия", "https://www.husqvarna-motorcycles.com/svartpilen-401/",
       {"power": 5, "comfort": 6, "handling": 9, "value": 9}),
    m(71, "Brutale 800", "", "MV Agusta", "naked", 2024, 798, 140, 87, 195, 14598, 6.0, 830, 3,
       "жидкостное", "механика", "Италия", "https://www.mvagusta.com/brutale-800/",
       {"power": 9, "comfort": 6, "handling": 9, "value": 7}),

    # Спорт-туринг
    m(72, "K1600B", "", "BMW", "tour", 2024, 1649, 160, 175, 336, 22995, 6.7, 750, 6,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/k1600b/",
       {"power": 10, "comfort": 10, "handling": 7, "value": 7}),

    # Туризм
    m(73, "Gold Wing Tour", "", "Honda", "tour", 2024, 1833, 124, 170, 379, 32700, 5.5, 745, 6,
       "жидкостное", "автомат", "Япония", "https://www.honda.co.jp/GoldWingTour/",
       {"power": 9, "comfort": 10, "handling": 7, "value": 7}),
    m(74, "Star Venture", "", "Yamaha", "tour", 2024, 1854, 126, 170, 437, 25199, 6.5, 715, 4,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/star-venture/",
       {"power": 9, "comfort": 10, "handling": 6, "value": 7}),

    # Тур-эндуро / эндуро
    m(75, "V-Strom 650", "", "Suzuki", "sport-tour", 2024, 645, 70, 62, 217, 9099, 4.5, 835, 2,
       "жидкостное", "механика", "Япония", "https://www.suzukicycles.com/v-strom-650/",
       {"power": 6, "comfort": 8, "handling": 8, "value": 10}),
    m(76, "V-Strom 1050", "", "Suzuki", "sport-tour", 2024, 1037, 107, 100, 247, 14499, 5.5, 855, 2,
       "жидкостное", "механика", "Япония", "https://www.suzukicycles.com/v-strom-1050/",
       {"power": 8, "comfort": 9, "handling": 8, "value": 9}),
    m(77, "Ténéré 700", "", "Yamaha", "enduro", 2024, 689, 73, 68, 204, 10799, 4.7, 875, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/tenere-700/",
       {"power": 6, "comfort": 7, "handling": 10, "value": 9}),
    m(78, "390 Adventure", "", "KTM", "enduro", 2024, 399, 43, 37, 158, 7299, 3.5, 855, 1,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/390-adventure/",
       {"power": 5, "comfort": 7, "handling": 9, "value": 9}),
    m(79, "G310GS", "", "BMW", "enduro", 2024, 313, 34, 28, 169, 5995, 3.5, 835, 1,
       "жидкостное", "механика", "Германия", "https://www.bmw-motorrad.com/g310gs/",
       {"power": 5, "comfort": 7, "handling": 8, "value": 9}),
    m(80, "Tuareg 660", "", "Aprilia", "enduro", 2024, 659, 80, 70, 204, 11999, 4.7, 860, 2,
       "жидкостное", "механика", "Италия", "https://www.aprilia.com/tuareg-660/",
       {"power": 7, "comfort": 8, "handling": 9, "value": 8}),
    m(81, "KLR650", "", "Kawasaki", "enduro", 2024, 652, 41, 49, 211, 6999, 4.5, 870, 1,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/klr650/",
       {"power": 5, "comfort": 7, "handling": 7, "value": 9}),
    m(82, "Himalayan", "", "Royal Enfield", "enduro", 2024, 411, 24, 32, 199, 5499, 3.5, 805, 1,
       "воздушно-масляное", "механика", "Индия", "https://www.royalenfield.com/himalayan/",
       {"power": 3, "comfort": 7, "handling": 7, "value": 9}),
    # Круизер
    m(84, "Sportster S", "", "Harley-Davidson", "cruiser", 2024, 1252, 121, 125, 228, 16399, 5.0, 753, 2,
       "жидкостное", "механика", "США", "https://www.harley-davidson.com/sportster-s/",
       {"power": 8, "comfort": 7, "handling": 7, "value": 7}),
    m(85, "Iron 883", "", "Harley-Davidson", "cruiser", 2022, 883, 50, 70, 247, 9499, 5.0, 760, 2,
       "воздушно-масляное", "механика", "США", "https://www.harley-davidson.com/iron-883/",
       {"power": 5, "comfort": 7, "handling": 6, "value": 7}),
    m(87, "Bolt R-Spec", "", "Yamaha", "cruiser", 2024, 942, 65, 80, 247, 8999, 5.0, 690, 2,
       "воздушно-масляное", "механика", "Япония", "https://www.yamaha-motor.com/bolt-r-spec/",
       {"power": 6, "comfort": 7, "handling": 7, "value": 8}),
    m(88, "Chief Bobber", "", "Indian", "cruiser", 2024, 1890, 95, 162, 304, 19499, 5.7, 660, 2,
       "воздушно-масляное", "механика", "США", "https://www.indianmotorcycle.com/chief-bobber/",
       {"power": 7, "comfort": 8, "handling": 6, "value": 7}),

    # Классик / cafe racer
    m(89, "Z650RS", "", "Kawasaki", "classic", 2024, 649, 67, 64, 187, 8999, 4.3, 820, 2,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z650rs/",
       {"power": 6, "comfort": 7, "handling": 8, "value": 9}),
    m(90, "Continental GT 650", "", "Royal Enfield", "classic", 2024, 648, 47, 52, 211, 6549, 3.8, 800, 2,
       "воздушно-масляное", "механика", "Индия", "https://www.royalenfield.com/continental-gt-650/",
       {"power": 5, "comfort": 6, "handling": 7, "value": 10}),
    m(91, "Interceptor 650", "", "Royal Enfield", "classic", 2024, 648, 47, 52, 202, 5999, 3.8, 804, 2,
       "воздушно-масляное", "механика", "Индия", "https://www.royalenfield.com/interceptor-650/",
       {"power": 5, "comfort": 7, "handling": 7, "value": 10}),
    m(92, "Speed Twin", "", "Triumph", "classic", 2024, 1200, 100, 112, 216, 13495, 4.9, 805, 2,
       "жидкостное", "механика", "Великобритания", "https://www.triumphmotorcycles.com/speed-twin/",
       {"power": 8, "comfort": 8, "handling": 8, "value": 8}),
    m(93, "V7", "", "Moto Guzzi", "classic", 2024, 853, 65, 73, 223, 9890, 4.8, 780, 2,
       "воздушно-масляное", "механика", "Италия", "https://www.motoguzzi.com/v7/",
       {"power": 5, "comfort": 7, "handling": 7, "value": 8}),
    m(94, "CB1100", "", "Honda", "classic", 2022, 1140, 89, 91, 252, 11999, 5.6, 779, 4,
       "воздушно-масляное", "механика", "Япония", "https://www.honda.co.jp/CB1100/",
       {"power": 6, "comfort": 8, "handling": 7, "value": 7}),

    # Мотард
    m(95, "690 SMC R", "", "KTM", "supermoto", 2024, 693, 74, 73, 147, 11999, 4.3, 890, 1,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/690-smc-r/",
       {"power": 7, "comfort": 5, "handling": 10, "value": 7}),
    m(96, "Dorsoduro 900", "", "Aprilia", "supermoto", 2020, 896, 95, 90, 212, 11499, 5.5, 870, 2,
       "жидкостное", "механика", "Италия", "https://www.aprilia.com/dorsoduro-900/",
       {"power": 7, "comfort": 6, "handling": 9, "value": 7}),

    # Кросс
    m(98, "MC 450F", "", "GasGas", "motocross", 2024, 450, 60, 52, 105, 10599, 6.5, 960, 1,
       "жидкостное", "механика", "Испания", "https://www.gasgas.com/mc-450f/",
       {"power": 9, "comfort": 3, "handling": 10, "value": 9}),
    m(99, "250 SX-F", "", "KTM", "motocross", 2024, 250, 47, 30, 99, 9899, 6.0, 950, 1,
       "жидкостное", "механика", "Австрия", "https://www.ktm.com/250-sx-f/",
       {"power": 7, "comfort": 3, "handling": 10, "value": 8}),

    # ===== Историчные годы для популярных моделей =====
    # MT-07 (база 2024 = $8199)
    m(100, "MT-07", "", "Yamaha", "naked", 2022, 689, 73, 67, 184, 6805, 4.3, 805, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-07/",
       {"power": 6, "comfort": 7, "handling": 9, "value": 10}),
    m(101, "MT-07", "", "Yamaha", "naked", 2023, 689, 73, 67, 184, 7543, 4.3, 805, 2,
       "жидкостное", "механика", "Япония", "https://www.yamaha-motor.com/mt-07/",
       {"power": 6, "comfort": 7, "handling": 9, "value": 10}),

    # Z900 (база 2024 = $9499)
    m(102, "Z900", "", "Kawasaki", "naked", 2022, 948, 125, 98, 212, 7884, 5.4, 820, 4,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z900/",
       {"power": 8, "comfort": 7, "handling": 8, "value": 9}),
    m(103, "Z900", "", "Kawasaki", "naked", 2023, 948, 125, 98, 212, 8739, 5.4, 820, 4,
       "жидкостное", "механика", "Япония", "https://www.kawasaki.com/z900/",
       {"power": 8, "comfort": 7, "handling": 8, "value": 9}),

    # Africa Twin 1100 (база 2024 = $14999)
    m(104, "Africa Twin 1100", "", "Honda", "tour-enduro", 2022, 1084, 102, 105, 226, 12449, 5.0, 850, 2,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/AfricaTwin/",
       {"power": 8, "comfort": 9, "handling": 9, "value": 9}),
    m(105, "Africa Twin 1100", "", "Honda", "tour-enduro", 2023, 1084, 102, 105, 226, 13799, 5.0, 850, 2,
       "жидкостное", "механика", "Япония", "https://www.honda.co.jp/AfricaTwin/",
       {"power": 8, "comfort": 9, "handling": 9, "value": 9}),

    # Panigale V4 (база 2024 = $24995)
    m(106, "Panigale V4", "", "Ducati", "sport", 2022, 1103, 215, 124, 198, 20746, 7.0, 850, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/panigale-v4/",
       {"power": 10, "comfort": 5, "handling": 10, "value": 7}),
    m(107, "Panigale V4", "", "Ducati", "sport", 2023, 1103, 215, 124, 198, 22995, 7.0, 850, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/panigale-v4/",
       {"power": 10, "comfort": 5, "handling": 10, "value": 7}),

    # Streetfighter V4 history (база $21995)
    m(108, "Streetfighter V4", "", "Ducati", "naked", 2022, 1103, 208, 123, 199, 18256, 7.0, 845, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/streetfighter-v4/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),
    m(109, "Streetfighter V4", "", "Ducati", "naked", 2023, 1103, 208, 123, 199, 20235, 7.0, 845, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/streetfighter-v4/",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),

    # Multistrada V4 history (база $21695)
    m(110, "Multistrada V4", "", "Ducati", "sport-tour", 2022, 1158, 170, 125, 215, 18007, 6.0, 840, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/multistrada-v4/",
       {"power": 10, "comfort": 9, "handling": 9, "value": 7}),
    m(111, "Multistrada V4", "", "Ducati", "sport-tour", 2023, 1158, 170, 125, 215, 19959, 6.0, 840, 4,
       "жидкостное", "механика", "Италия", "https://www.ducati.com/multistrada-v4/",
       {"power": 10, "comfort": 9, "handling": 9, "value": 7}),

    # ===== Категория A1 (до 125 куб, до 11 кВт ≈ 15 л.с.) =====
    m(112, "CB125R", "", "Honda", "naked", 2024, 124, 13, 11, 130, 4800, 2.4, 816, 1,
       "жидкостное", "механика", "Япония", "",
       {"power": 3, "comfort": 6, "handling": 8, "value": 9}),
    m(113, "MT-125", "", "Yamaha", "naked", 2024, 124, 15, 12, 142, 5200, 2.6, 810, 1,
       "жидкостное", "механика", "Япония", "",
       {"power": 3, "comfort": 6, "handling": 8, "value": 9}),
    m(114, "125 Duke", "", "KTM", "naked", 2024, 125, 15, 12, 148, 5500, 2.5, 820, 1,
       "жидкостное", "механика", "Австрия", "",
       {"power": 3, "comfort": 6, "handling": 9, "value": 9}),
    m(115, "RS 125", "", "Aprilia", "sport", 2024, 125, 15, 11, 148, 5800, 2.6, 820, 1,
       "жидкостное", "механика", "Италия", "",
       {"power": 3, "comfort": 5, "handling": 9, "value": 8}),
    m(116, "YZF-R125", "", "Yamaha", "sport", 2024, 124, 15, 12, 142, 5500, 2.4, 825, 1,
       "жидкостное", "механика", "Япония", "",
       {"power": 3, "comfort": 5, "handling": 9, "value": 9}),

    # ===== A2 (до 35 кВт ≈ 47 л.с., и kW/kg ≤ 0.2) =====
    m(117, "MT-03", "", "Yamaha", "naked", 2024, 321, 42, 30, 168, 5600, 3.5, 780, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 5, "comfort": 7, "handling": 8, "value": 9}),
    m(118, "Ninja 400", "", "Kawasaki", "sport", 2024, 399, 45, 38, 168, 5800, 4.0, 785, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 5, "comfort": 6, "handling": 8, "value": 9}),
    m(119, "390 Duke", "", "KTM", "naked", 2024, 399, 44, 37, 159, 5700, 3.7, 820, 1,
       "жидкостное", "механика", "Австрия", "",
       {"power": 5, "comfort": 6, "handling": 9, "value": 9}),
    m(120, "CB500F", "", "Honda", "naked", 2024, 471, 47, 43, 189, 7200, 3.8, 785, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 6, "comfort": 7, "handling": 8, "value": 9}),
    m(121, "CBR500R", "", "Honda", "sport-tour", 2024, 471, 47, 43, 192, 7500, 3.8, 785, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 6, "comfort": 7, "handling": 8, "value": 9}),
    m(122, "G310R", "", "BMW", "naked", 2024, 313, 34, 28, 164, 5500, 3.5, 785, 1,
       "жидкостное", "механика", "Германия", "",
       {"power": 4, "comfort": 6, "handling": 8, "value": 8}),
    m(123, "XSR700", "", "Yamaha", "naked", 2024, 689, 73, 68, 186, 8500, 4.3, 835, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 7, "comfort": 7, "handling": 8, "value": 9}),

    # ===== Заново добавленные (ранее удалённые из-за фото) =====
    m(124, "CRF300L", "", "Honda", "enduro", 2024, 286, 27, 26, 142, 5500, 3.0, 880, 1,
       "жидкостное", "механика", "Япония", "",
       {"power": 4, "comfort": 6, "handling": 9, "value": 9}),
    m(125, "Rebel 1100", "", "Honda", "cruiser", 2024, 1084, 87, 98, 223, 9500, 4.7, 700, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 7, "comfort": 8, "handling": 7, "value": 9}),

    # ===== Дополнительные новые модели (батч 2) =====
    # Sport
    m(126, "RS 660", "", "Aprilia", "sport", 2024, 660, 100, 67, 183, 11500, 4.5, 820, 2,
       "жидкостное", "механика", "Италия", "",
       {"power": 8, "comfort": 6, "handling": 9, "value": 8}),
    m(127, "CBR650R", "", "Honda", "sport", 2024, 649, 95, 64, 207, 9800, 5.4, 810, 4,
       "жидкостное", "механика", "Япония", "",
       {"power": 7, "comfort": 6, "handling": 8, "value": 9}),
    m(128, "Ninja 650", "", "Kawasaki", "sport", 2024, 649, 67, 65, 196, 7900, 4.5, 790, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 6, "comfort": 7, "handling": 8, "value": 9}),

    # Naked
    m(129, "Speed Triple 1200 RR", "", "Triumph", "naked", 2024, 1160, 180, 125, 199, 20500, 6.5, 830, 3,
       "жидкостное", "механика", "Великобритания", "",
       {"power": 10, "comfort": 6, "handling": 10, "value": 7}),
    m(130, "CB650R", "", "Honda", "naked", 2024, 649, 95, 64, 202, 9300, 5.5, 810, 4,
       "жидкостное", "механика", "Япония", "",
       {"power": 7, "comfort": 7, "handling": 8, "value": 9}),
    m(131, "Vitpilen 401", "", "Husqvarna", "naked", 2024, 399, 44, 39, 152, 5800, 3.5, 820, 1,
       "жидкостное", "механика", "Австрия", "",
       {"power": 5, "comfort": 6, "handling": 9, "value": 9}),
    m(132, "Brutale 800 RR", "", "MV Agusta", "naked", 2024, 798, 140, 87, 175, 17500, 6.0, 830, 3,
       "жидкостное", "механика", "Италия", "",
       {"power": 9, "comfort": 6, "handling": 10, "value": 7}),

    # Sport-touring
    m(133, "R1250RT", "", "BMW", "sport-tour", 2023, 1254, 136, 143, 279, 20500, 5.7, 805, 2,
       "жидкостное", "механика", "Германия", "",
       {"power": 9, "comfort": 10, "handling": 7, "value": 7}),
    m(134, "Versys 1000 SE", "", "Kawasaki", "sport-tour", 2024, 1043, 120, 102, 257, 18000, 6.0, 840, 4,
       "жидкостное", "механика", "Япония", "",
       {"power": 9, "comfort": 9, "handling": 8, "value": 8}),
    m(135, "Versys 650", "", "Kawasaki", "sport-tour", 2024, 649, 67, 61, 217, 9500, 5.0, 845, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 6, "comfort": 8, "handling": 8, "value": 9}),
    m(136, "NT1100", "", "Honda", "sport-tour", 2024, 1084, 101, 104, 248, 14200, 5.4, 820, 2,
       "жидкостное", "механика", "Япония", "",
       {"power": 8, "comfort": 9, "handling": 7, "value": 8}),

    # Tour
    m(137, "Roadmaster", "", "Indian", "tour", 2024, 1890, 122, 171, 437, 32000, 6.0, 673, 2,
       "воздушно-масляное", "механика", "США", "",
       {"power": 9, "comfort": 10, "handling": 6, "value": 7}),

    # Tour-enduro
    m(138, "R1250GS", "", "BMW", "tour-enduro", 2023, 1254, 136, 143, 249, 20500, 5.6, 850, 2,
       "жидкостное", "механика", "Германия", "",
       {"power": 9, "comfort": 9, "handling": 9, "value": 8}),
    m(139, "R1250GS", "Adventure", "BMW", "tour-enduro", 2023, 1254, 136, 143, 268, 22000, 5.8, 870, 2,
       "жидкостное", "механика", "Германия", "",
       {"power": 9, "comfort": 10, "handling": 8, "value": 8}),

    # Enduro
    m(140, "CRF300 Rally", "", "Honda", "enduro", 2024, 286, 27, 26, 153, 6200, 3.0, 885, 1,
       "жидкостное", "механика", "Япония", "",
       {"power": 4, "comfort": 7, "handling": 9, "value": 9}),

    # Classic
    m(141, "Bonneville T100", "", "Triumph", "classic", 2024, 900, 65, 80, 213, 11000, 4.4, 790, 2,
       "жидкостное", "механика", "Великобритания", "",
       {"power": 6, "comfort": 8, "handling": 7, "value": 8}),

    # Year variants for S1000RR
    m(142, "S1000RR", "", "BMW", "sport", 2022, 999, 207, 113, 197, 15154, 6.4, 824, 4,
       "жидкостное", "механика", "Германия", "",
       {"power": 10, "comfort": 6, "handling": 10, "value": 8}),
    m(143, "S1000RR", "", "BMW", "sport", 2023, 999, 210, 113, 197, 16462, 6.4, 824, 4,
       "жидкостное", "механика", "Германия", "",
       {"power": 10, "comfort": 6, "handling": 10, "value": 8}),
]


# ===== Поисковая ссылка на производителя/дилера =====
def make_search_url(moto):
    """Перенаправление через Google: первый результат — официальный сайт
    производителя или авторизованный дилер."""
    parts = [moto["brand"], moto["name"]]
    if moto.get("trim"):
        parts.append(moto["trim"])
    parts.append(str(moto["year"]))
    parts.append("motorcycle")
    q = urllib.parse.quote_plus(" ".join(parts))
    return f"https://www.google.com/search?q={q}"


for _m in MOTORCYCLES:
    _m["url"] = make_search_url(_m)


# ===== Категория прав =====
def license_category(moto):
    """Минимальная категория прав, нужная чтобы ездить на этом мотоцикле без
    ограничения мощности. A1 ≤ 125cc / 11kW; A2 ≤ 35kW и kW/kg ≤ 0.2; иначе A.
    1 PS = 0.7355 kW, но в спецификациях часто округлено — даём допуск 0.1 kW."""
    cc = moto.get("cc", 0)
    hp = moto.get("hp", 0)
    weight = moto.get("weight", 1) or 1
    kw = round(hp * 0.7355, 1)
    kw_per_kg = kw / weight
    if cc <= 125 and kw <= 11.1:
        return "A1"
    if kw <= 35.1 and kw_per_kg <= 0.201:
        return "A2"
    return "A"


def license_categories_allowed(moto):
    """Список категорий, на которые можно ездить на этом мотоцикле.
    A1-bike: A1, A2, A. A2-bike: A2, A. A-bike: A."""
    cat = license_category(moto)
    if cat == "A1":
        return ["A1", "A2", "A"]
    if cat == "A2":
        return ["A2", "A"]
    return ["A"]


for _m in MOTORCYCLES:
    _m["license"] = license_category(_m)
    _m["license_allowed"] = license_categories_allowed(_m)


# ===== Подключение локальных фото =====
LOCAL_IMG_DIR = os.path.join(os.path.dirname(__file__), "static", "images")


def refresh_images():
    """Перепроверяет наличие фото на диске. Дешёвая операция — stat только
    для мотоциклов без уже найденного изображения."""
    for moto in MOTORCYCLES:
        if moto["image"]:
            continue
        local_path = os.path.join(LOCAL_IMG_DIR, f"{moto['id']}.jpg")
        if os.path.exists(local_path):
            moto["image"] = f"/static/images/{moto['id']}.jpg"


refresh_images()


# ===== Группировка моделей для каталога =====
def get_grouped_models(lang=DEFAULT_LANG):
    """Группирует MOTORCYCLES по (brand, name).
    Возвращает список карточек с локализованными country/cooling/transmission."""
    groups = {}
    for moto in MOTORCYCLES:
        key = f"{moto['brand']}|{moto['name']}"
        if key not in groups:
            groups[key] = []
        groups[key].append(moto)

    type_order = list(TYPE_NAMES.keys())
    out = []
    for key, raw_variants in groups.items():
        variants = [localize_moto(v, lang) for v in raw_variants]
        sorted_v = sorted(variants, key=lambda v: (-v["year"], v["trim"] != ""))
        preview = next((v for v in sorted_v if v.get("image")), sorted_v[0])
        first = variants[0]
        prices = [v["price"] for v in variants]
        hps = [v["hp"] for v in variants]
        weights = [v["weight"] for v in variants]
        ccs = [v["cc"] for v in variants]
        # объединяем разрешённые категории прав по всем вариантам
        allowed_set = set()
        for v in variants:
            allowed_set.update(v.get("license_allowed", []))
        # минимальная категория среди вариантов (ниже = доступнее)
        rank = {"A1": 0, "A2": 1, "A": 2}
        min_lic = min((v.get("license", "A") for v in variants),
                      key=lambda x: rank.get(x, 2))
        out.append({
            "key": key,
            "brand": first["brand"],
            "name": first["name"],
            "type": first["type"],
            "country": first["country"],
            "preview_image": preview.get("image", ""),
            "min_price": min(prices),
            "max_price": max(prices),
            "min_hp": min(hps),
            "max_hp": max(hps),
            "min_weight": min(weights),
            "max_weight": max(weights),
            "min_cc": min(ccs),
            "max_cc": max(ccs),
            "trims": sorted({v["trim"] for v in variants}),
            "years": sorted({v["year"] for v in variants}),
            "transmissions": sorted({v["transmission"] for v in variants}),
            "license": min_lic,
            "license_allowed": sorted(allowed_set),
            "variants": variants,
        })
    out.sort(key=lambda g: (type_order.index(g["type"]), g["brand"], g["name"]))
    return out


# Старый ruplural оставлен для совместимости (теперь учитывает текущий язык).
@app.template_filter("ruplural")
def ru_plural_filter(n, forms_str):
    return plural_t_filter(n, forms_str)


# ===== График цен по годам =====
def price_by_year(moto):
    """Цены от года выпуска модели до текущего (2026).
    Применяем коэффициент износа к base = moto['price']."""
    base = moto["price"]
    start_year = moto["year"]
    current_year = 2026

    # Новая или будущая модель — только одна точка
    if start_year >= current_year:
        return [{"year": start_year, "price": base}]

    coeffs = {0: 1.0, 1: 0.92, 2: 0.83, 3: 0.75, 4: 0.68,
              5: 0.62, 6: 0.57, 7: 0.53}
    result = []
    for y in range(start_year, current_year + 1):
        age = current_year - y
        c = coeffs.get(age, max(0.40, 0.53 - (age - 7) * 0.03))
        result.append({"year": y, "price": int(base * c)})
    return result


def build_spec_groups(strings):
    """Спецификации с локализованными метками и единицами для текущего языка."""
    return [
        (strings["spec_engine"], [
            (strings["spec_displacement"], "cc",         lambda v: f"{v} {strings['u_cc']}"),
            (strings["spec_power"],        "hp",         lambda v: f"{v} {strings['u_hp']}"),
            (strings["spec_torque"],       "torque",     lambda v: f"{v} {strings['u_nm']}"),
            (strings["spec_cylinders"],    "cylinders",  lambda v: str(v)),
            (strings["spec_cooling"],      "cooling",    lambda v: v),
        ]),
        (strings["spec_chassis"], [
            (strings["spec_weight"],       "weight",       lambda v: f"{v} {strings['u_kg']}"),
            (strings["spec_seat_height"],  "seat_height",  lambda v: f"{v} {strings['u_mm']}"),
            (strings["spec_consume"],      "consume",      lambda v: f"{v:.1f} {strings['u_l_per_100']}"),
        ]),
        (strings["spec_general"], [
            (strings["spec_transmission"], "transmission", lambda v: v),
            (strings["spec_country"],      "country",      lambda v: v),
            (strings["spec_year"],         "year",         lambda v: str(v)),
            (strings["spec_price"],        "price",        lambda v: f"${v:,}"),
        ]),
    ]


def build_spec_rows(motos, strings):
    """Готовые отформатированные значения характеристик для шаблона."""
    groups = []
    for title, rows in build_spec_groups(strings):
        out_rows = []
        for label, key, fmt in rows:
            values = [moto[key] for moto in motos]
            formatted = [fmt(v) for v in values]
            same = len(set(values)) == 1
            best_index = None
            if not same:
                if key in ("hp", "torque"):
                    best_val = max(values)
                    best_index = values.index(best_val)
                elif key in ("weight", "consume", "price"):
                    best_val = min(values)
                    best_index = values.index(best_val)
            out_rows.append({
                "label": label, "key": key, "vals": formatted,
                "same": same, "best": best_index,
            })
        groups.append({"title": title, "rows": out_rows})
    return groups


# ===== Роуты =====
@app.route("/")
def index():
    refresh_images()
    lang = g.lang
    grouped = get_grouped_models(lang)
    brands = sorted({grp["brand"] for grp in grouped})
    types = list(TYPE_NAMES.keys())
    countries = sorted({grp["country"] for grp in grouped})
    years = sorted({moto["year"] for moto in MOTORCYCLES}, reverse=True)
    transmissions = sorted({tr_trans(moto["transmission"], lang) for moto in MOTORCYCLES})
    return render_template(
        "index.html",
        grouped=grouped,
        total_models=len(MOTORCYCLES),
        brands=brands,
        types=types,
        countries=countries,
        years=years,
        transmissions=transmissions,
        type_names=type_names_for(lang),
    )


@app.route("/compare/<path:ids>")
def compare(ids):
    refresh_images()
    lang = g.lang
    parsed = [int(x) for x in ids.split("/") if x.isdigit()]
    if len(parsed) < 2 or len(parsed) > 4:
        abort(404)

    by_id = {moto["id"]: moto for moto in MOTORCYCLES}
    raw_motos = [by_id[i] for i in parsed if i in by_id]
    if len(raw_motos) < 2:
        abort(404)

    motos = [localize_moto(m, lang) for m in raw_motos]
    selected_ids = {moto["id"] for moto in motos}
    alternatives = [localize_moto(m, lang) for m in MOTORCYCLES
                    if m["id"] not in selected_ids][:8]
    price_data = [price_by_year(m) for m in raw_motos]
    spec_groups = build_spec_rows(motos, make_strings(lang))

    return render_template(
        "compare.html",
        motos=motos,
        alternatives=alternatives,
        price_data=price_data,
        spec_groups=spec_groups,
        type_names=type_names_for(lang),
    )


@app.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    parsed = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    by_id = {moto["id"]: moto for moto in MOTORCYCLES}
    motos = [by_id[i] for i in parsed if i in by_id]
    return jsonify(motos)


@app.route("/api/ai-advice", methods=["POST"])
@(limiter.limit("10 per hour; 30 per day") if limiter else (lambda f: f))
def ai_advice():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()
    messages = payload.get("messages") or []
    system = payload.get("system") or ""

    if not key:
        return jsonify({"error": "API ключ не указан"}), 400
    if not messages:
        return jsonify({"error": "Сообщения отсутствуют"}), 400

    body = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1500,
        "messages": messages,
    }
    if system:
        body["system"] = system

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        return jsonify({"text": text})
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read())
            msg = err_body.get("error", {}).get("message") or str(err_body)
        except Exception:
            msg = f"HTTP {e.code}"
        return jsonify({"error": msg}), e.code
    except urllib.error.URLError as e:
        return jsonify({"error": f"Сетевая ошибка: {e.reason}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== SEO / Sitemap / Pricing / Error Handlers =====
@app.route("/robots.txt")
def robots_txt():
    return app.send_static_file("robots.txt")


@app.route("/sitemap.xml")
def sitemap_xml():
    base = request.url_root.rstrip("/")
    urls = [f"{base}/"]
    by_id = {moto["id"]: moto for moto in MOTORCYCLES}
    # парные сравнения первой попавшейся модели каждого бренда — не плодим миллион URL
    seen_brands = set()
    anchors = []
    for moto in MOTORCYCLES:
        if moto["brand"] not in seen_brands:
            anchors.append(moto["id"])
            seen_brands.add(moto["brand"])
    for i in range(len(anchors) - 1):
        urls.append(f"{base}/compare/{anchors[i]}/{anchors[i+1]}")
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        body.append(f"  <url><loc>{u}</loc></url>")
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404,
                           message=make_strings(g.lang).get("err_404", "Not found")), 404


@app.errorhandler(429)
def rate_limited(_e):
    return render_template("error.html", code=429,
                           message=make_strings(g.lang).get("err_429", "Too many requests")), 429


@app.errorhandler(500)
def server_error(_e):
    return render_template("error.html", code=500,
                           message=make_strings(g.lang).get("err_500", "Server error")), 500


if __name__ == "__main__":
    print(f"Сервер запущен: http://127.0.0.1:{Config.PORT}")
    app.run(debug=True, port=Config.PORT)
