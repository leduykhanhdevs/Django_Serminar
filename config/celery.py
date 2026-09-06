"""Celery configuration for deadline, retention, and export work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("privacyhub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

