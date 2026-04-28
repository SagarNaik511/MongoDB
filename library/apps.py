"""
library/apps.py
Runs MongoDB initialization (indexes + sample data) when Django starts.
"""
from django.apps import AppConfig


class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'library'

    def ready(self):
        """Called when Django app is fully loaded."""
        try:
            from library.db import initialize_indexes, seed_sample_data
            initialize_indexes()
            seed_sample_data()
        except Exception as e:
            print(f"[WARN] Startup init warning: {e}")