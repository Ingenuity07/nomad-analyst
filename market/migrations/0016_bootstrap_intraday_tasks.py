from django.db import migrations


def bootstrap_intraday_update_task(apps, schema_editor):
    try:
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

        # 5-minute interval for intraday incremental updates
        schedule_5m, _ = IntervalSchedule.objects.get_or_create(
            every=5,
            period='minutes'
        )

        # Register the intraday incremental update task.
        # The task itself checks market hours and skips if the market is closed.
        PeriodicTask.objects.get_or_create(
            name="Run intraday 5m incremental update",
            defaults={
                "interval": schedule_5m,
                "task": "market.tasks.run_intraday_incremental_update",
                "enabled": True,
            }
        )
    except Exception as e:
        print(f"Skipping intraday periodic task bootstrap: {e}")


def reverse_intraday_update_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(name="Run intraday 5m incremental update").delete()
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0015_bootstrap_daily_recommendation_task'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_intraday_update_task,
            reverse_intraday_update_task
        ),
    ]
