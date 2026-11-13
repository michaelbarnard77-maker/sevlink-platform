"""Reserve recognized historical printed ranges without renumbering any records."""
import re
from django.db import migrations


def reserve(apps,schema_editor):
    Sequence=apps.get_model('portal','DocumentSequence')
    for model,field,prefix in [('JobQuotation','reference','SQ'),('JobInvoice','number','SI')]:
        maxima={}
        for value in apps.get_model('portal',model).objects.values_list(field,flat=True).iterator():
            match=re.fullmatch(prefix+r'-(\d{4})-(\d{4})',value or '')
            if match:
                year,count=map(int,match.groups())
                maxima[year]=max(maxima.get(year,0),count)
        for year,value in maxima.items():
            row,_=Sequence.objects.get_or_create(prefix=prefix,year=year)
            if row.last_value<value:
                row.last_value=value;row.save(update_fields=['last_value'])


class Migration(migrations.Migration):
    dependencies=[('portal','0012_operationsfeedbackresolution')]
    operations=[migrations.RunPython(reserve,migrations.RunPython.noop)]
