"""MotoBase — конфигурация через переменные окружения."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-prod")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    DEBUG = os.environ.get("FLASK_ENV", "production") == "development"
    PORT = int(os.environ.get("PORT", 5001))

    AI_FREE_REQUESTS_PER_DAY = int(os.environ.get("AI_FREE_REQUESTS_PER_DAY", 5))
    AI_PREMIUM_REQUESTS_PER_DAY = int(os.environ.get("AI_PREMIUM_REQUESTS_PER_DAY", 100))

    GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "")

    ADSENSE_CLIENT = os.environ.get("ADSENSE_CLIENT", "")
    SHOW_ADS = os.environ.get("SHOW_ADS", "false").lower() == "true"

    AFFILIATE_ENABLED = os.environ.get("AFFILIATE_ENABLED", "false").lower() == "true"
