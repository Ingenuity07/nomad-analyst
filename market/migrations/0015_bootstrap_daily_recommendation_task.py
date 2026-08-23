from django.db import migrations


def bootstrap_daily_recommendation_task(apps, schema_editor):
    try:
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

        # Reuse or create a 24-hour interval schedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=24,
            period='hours'
        )

        # Register the periodic daily recommendation scan task
        PeriodicTask.objects.get_or_create(
            name="Run daily stock recommendation scan",
            defaults={
                "interval": schedule,
                "task": "market.tasks.run_daily_recommendation_scan",
                "enabled": True
            }
        )
    except Exception as e:
        print(f"Skipping recommendation periodic task bootstrap: {e}")


def reverse_daily_recommendation_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(name="Run daily stock recommendation scan").delete()
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0014_stockrecommendation'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_daily_recommendation_task,
            reverse_daily_recommendation_task
        ),
    ]
