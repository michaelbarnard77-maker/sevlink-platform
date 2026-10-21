from django.db import migrations


def seed(apps, schema_editor):
    Province = apps.get_model('portal', 'Province')
    City = apps.get_model('portal', 'City')
    alias = schema_editor.connection.alias
    for code, name in [('GP', 'Gauteng'), ('WC', 'Western Cape'), ('EC', 'Eastern Cape'),
                       ('FS', 'Free State'), ('KZN', 'KwaZulu-Natal'), ('LP', 'Limpopo'),
                       ('MP', 'Mpumalanga'), ('NC', 'Northern Cape'), ('NW', 'North West')]:
        province, _ = Province.objects.using(alias).get_or_create(code=code, defaults={'name': name})
        names = ['Cape Town'] if code == 'WC' else ['Johannesburg', 'Pretoria', 'Meyerton', 'Vanderbijlpark', 'Heidelberg', 'Nigel'] if code == 'GP' else []
        for city in names:
            City.objects.using(alias).get_or_create(province=province, name=city)
    # Deliberately no address inference or browser-demo data import.


class Migration(migrations.Migration):
    dependencies = [('portal', '0014_regional_subcontractors')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
