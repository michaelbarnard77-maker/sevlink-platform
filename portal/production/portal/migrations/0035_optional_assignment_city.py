from django.db import migrations,models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[('portal','0034_removal_receipt')]
    operations=[migrations.AlterField(model_name='jobassignment',name='city',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to='portal.city'))]
