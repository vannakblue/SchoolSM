from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.db.backends.signals import connection_created


def configure_sqlite_pragmas(sender, connection, **kwargs):
    """
    Guarantees local database data persistence and high concurrency by enabling
    Write-Ahead Logging (WAL) and 30s busy timeout for SQLite.
    """
    if connection.vendor == 'sqlite':
        try:
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode = WAL;')
            cursor.execute('PRAGMA synchronous = NORMAL;')
            cursor.execute('PRAGMA busy_timeout = 30000;')
        except Exception:
            pass


def on_post_migrate(sender, **kwargs):
    try:
        from .system_defaults import ensure_system_defaults
        ensure_system_defaults()
    except Exception:
        pass


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        connection_created.connect(configure_sqlite_pragmas)
        post_migrate.connect(on_post_migrate, sender=self)


