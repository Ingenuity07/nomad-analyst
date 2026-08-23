from django.db import migrations

def bootstrap_market_context_periodic_task(apps, schema_editor):
    try:
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        
        # Create a 1-hour interval schedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period='hours'
        )
        
        # Register the periodic market context refresh task
        PeriodicTask.objects.get_or_create(
            name="Refresh market context hourly",
            defaults={
                "interval": schedule,
                "task": "market.tasks.refresh_market_context",
                "enabled": True
            }
        )
    except Exception as e:
        print(f"Skipping periodic task bootstrap: {e}")

def reverse_market_context_periodic_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(name="Refresh market context hourly").delete()
    except Exception:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('market', '0008_alter_instrument_exchange'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(bootstrap_market_context_periodic_task, reverse_market_context_periodic_task),
    ]
