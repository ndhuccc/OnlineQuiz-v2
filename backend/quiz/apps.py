from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _configure_sqlite(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")


class QuizConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "quiz"
    verbose_name = "線上測驗"

    def ready(self) -> None:
        import atexit

        from django.db.utils import OperationalError

        from quiz.services.session_fsm import invalidate_pending_schedules, recover_expired_timers

        connection_created.connect(_configure_sqlite, dispatch_uid="quiz_sqlite_wal")
        atexit.register(invalidate_pending_schedules)

        try:
            from django.utils.autoreload import autoreload_started

            autoreload_started.connect(
                lambda **_: invalidate_pending_schedules(),
                dispatch_uid="quiz_cancel_timers_on_reload",
            )
        except Exception:
            pass

        try:
            recover_expired_timers()
        except OperationalError:
            pass
