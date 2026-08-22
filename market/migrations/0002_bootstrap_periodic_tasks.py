from django.db import migrations

def bootstrap_periodic_tasks(apps, schema_editor):
    try:
        # Import models dynamically to prevent load-order issues
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        
        # Create a 30-minute interval schedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period='minutes'  # IntervalSchedule.MINUTES
        )
        
        # Register the periodic stock quote updates task
        PeriodicTask.objects.get_or_create(
            name="Update stock quotes every 30 minutes",
            defaults={
                "interval": schedule,
                "task": "market.tasks.update_instrument_quotes",
                "enabled": True
            }
        )
    except Exception as e:
        # Prevent migration failure if django_celery_beat tables are not loaded
        print(f"Skipping periodic task bootstrap: {e}")

def reverse_periodic_tasks(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(name="Update stock quotes every 30 minutes").delete()
    except Exception:
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('market', '0001_initial'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(bootstrap_periodic_tasks, reverse_periodic_tasks),
    ]
