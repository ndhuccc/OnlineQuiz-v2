"""Flask 模式：無 Channels / Daphne / WebSocket，僅 ORM + 業務邏輯。"""
from .settings import *  # noqa: F403

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "quiz",
]

ASGI_APPLICATION = None
