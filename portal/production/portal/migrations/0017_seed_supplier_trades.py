from django.db import migrations


def seed(apps, schema_editor):
    Trade = apps.get_model("portal", "TradeCategory")
    for name in ('Plumbing', 'Electrical', 'Doors & locks', 'Painting', 'Tiling', 'General maintenance', 'Roofing', 'Gutters & Downpipes', 'Damp & Waterproofing', 'Ceilings & Drywall', 'Carpentry & Cupboards', 'Windows & Glass', 'Gates & Garage Doors', 'Appliances', 'Air Conditioning & Ventilation', 'Gardens & Outdoor Areas', 'Pest Control', 'Cleaning & Waste Removal', 'Renovations & Refurbishments'):
        Trade.objects.using(schema_editor.connection.alias).get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("portal", "0016_supplier_profiles_teams_compliance")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
