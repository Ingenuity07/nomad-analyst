from django.db import migrations

def bootstrap_daily_opportunity_task(apps, schema_editor):
    try:
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        
        # Create a 24-hour interval schedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=24,
            period='hours'
        )
        
        # Register the periodic daily opportunity scan task
        PeriodicTask.objects.get_or_create(
            name="Run daily stock opportunity scan",
            defaults={
                "interval": schedule,
                "task": "market.tasks.run_daily_opportunity_scan",
                "enabled": True
            }
        )
    except Exception as e:
        print(f"Skipping periodic task bootstrap: {e}")

def reverse_daily_opportunity_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(name="Run daily stock opportunity scan").delete()
    except Exception:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('market', '0011_bootstrap_universes'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(bootstrap_daily_opportunity_task, reverse_daily_opportunity_task),
    ]
