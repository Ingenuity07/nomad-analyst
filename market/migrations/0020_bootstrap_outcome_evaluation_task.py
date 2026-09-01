"""
0020_bootstrap_outcome_evaluation_task.py

Registers the Module 11 live outcome evaluation Celery beat task.

Task:
  evaluate_recommendation_outcomes — every 5 minutes during market hours
    (self-gated: skips if market is closed).

Design decision: historical backtests are NEVER auto-scheduled.
BacktestRunner.run() must be explicitly called.
"""
from django.db import migrations


def bootstrap_outcome_evaluation_task(apps, schema_editor):
    try:
        PeriodicTask     = apps.get_model("django_celery_beat", "PeriodicTask")
        IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    except LookupError:
        return  # django_celery_beat not installed

    interval_5m, _ = IntervalSchedule.objects.get_or_create(
        every=5, period="minutes"
    )

    PeriodicTask.objects.update_or_create(
        name="evaluate_recommendation_outcomes",
        defaults={
            "task": "market.tasks.evaluate_recommendation_outcomes",
            "interval": interval_5m,
            "enabled": True,
            "description": (
                "Module 11: Evaluate active recommendations against new market bars "
                "every 5 minutes. Self-gated on market hours. Idempotent."
            ),
        },
    )


def reverse_bootstrap(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
        PeriodicTask.objects.filter(
            name="evaluate_recommendation_outcomes"
        ).delete()
    except LookupError:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0019_recommendation_outcome_backtest_run"),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_outcome_evaluation_task,
            reverse_code=reverse_bootstrap,
        ),
    ]
