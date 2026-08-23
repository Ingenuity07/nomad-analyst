from django.db import migrations
from django.utils import timezone

def bootstrap_universes(apps, schema_editor):
    Universe = apps.get_model('market', 'Universe')
    UniverseMembership = apps.get_model('market', 'UniverseMembership')
    Instrument = apps.get_model('market', 'Instrument')

    # 1. Create standard universes
    nifty50, _ = Universe.objects.get_or_create(
        name="NIFTY50",
        defaults={
            "description": "Nifty 50 Index Universe",
            "is_active": True
        }
    )
    Universe.objects.get_or_create(
        name="NIFTY100",
        defaults={
            "description": "Nifty 100 Index Universe",
            "is_active": True
        }
    )
    Universe.objects.get_or_create(
        name="NIFTY500",
        defaults={
            "description": "Nifty 500 Index Universe",
            "is_active": True
        }
    )

    # 2. Add all currently active equities to NIFTY50 universe
    equities = Instrument.objects.filter(instrument_type="EQUITY", is_active=True)
    for eq in equities:
        UniverseMembership.objects.get_or_create(
            universe=nifty50,
            instrument=eq,
            defaults={
                "is_active": True,
                "added_at": timezone.now()
            }
        )

def reverse_bootstrap_universes(apps, schema_editor):
    Universe = apps.get_model('market', 'Universe')
    UniverseMembership = apps.get_model('market', 'UniverseMembership')
    UniverseMembership.objects.all().delete()
    Universe.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('market', '0010_universe_stockopportunitysnapshot_universemembership'),
    ]

    operations = [
        migrations.RunPython(bootstrap_universes, reverse_bootstrap_universes),
    ]
