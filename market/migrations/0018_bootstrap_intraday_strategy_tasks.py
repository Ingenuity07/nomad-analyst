"""
0018_bootstrap_intraday_strategy_tasks.py

Registers Module 10 intraday strategy Celery beat tasks.

Tasks:
  run_intraday_strategy_scan         — every 5 minutes (self-gated on market hours)
  expire_intraday_session_recommendations — daily at 15:35 IST (10:05 UTC)

These tasks are idempotent and safe to re-run.
"""
from django.db import migrations


def bootstrap_intraday_strategy_tasks(apps, schema_editor):
    try:
        PeriodicTask   = apps.get_model("django_celery_beat", "PeriodicTask")
        IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
        CrontabSchedule  = apps.get_model("django_celery_beat", "CrontabSchedule")
    except LookupError:
        return  # django_celery_beat not installed

    # ── Intraday strategy scan — every 5 minutes ──────────────────────────────
    interval_5m, _ = IntervalSchedule.objects.get_or_create(
        every=5, period="minutes"
    )

    PeriodicTask.objects.update_or_create(
        name="run_intraday_strategy_scan",
        defaults={
            "task": "market.tasks.run_intraday_strategy_scan",
            "interval": interval_5m,
            "enabled": True,
            "description": (
                "Module 10: Intraday strategy signal scan. "
                "Runs every 5 minutes. Self-gated on market hours."
            ),
        },
    )

    # ── Session expiry — daily at 15:35 IST = 10:05 UTC ──────────────────────
    cron_1535_ist, _ = CrontabSchedule.objects.get_or_create(
        minute="5",
        hour="10",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )

    PeriodicTask.objects.update_or_create(
        name="expire_intraday_session_recommendations",
        defaults={
            "task": "market.tasks.expire_intraday_session_recommendations",
            "crontab": cron_1535_ist,
            "enabled": True,
            "description": (
                "Module 10: Expire ACTIVE intraday recommendations at market close (15:35 IST). "
                "Marks expired; never deletes records."
            ),
        },
    )


def reverse_bootstrap(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    except LookupError:
        return
    PeriodicTask.objects.filter(name__in=[
        "run_intraday_strategy_scan",
        "expire_intraday_session_recommendations",
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0017_stockrecommendation_intraday_fields"),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_intraday_strategy_tasks,
            reverse_code=reverse_bootstrap,
        ),
    ]
