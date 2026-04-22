from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0009_vouchertier_is_replacement'),
    ]

    operations = [
        migrations.AddField(
            model_name='vouchertier',
            name='is_admin_code',
            field=models.BooleanField(default=False, verbose_name='Code Admin'),
        ),
        migrations.AddField(
            model_name='vouchertier',
            name='max_vouchers',
            field=models.PositiveSmallIntegerField(default=100, verbose_name='Max par création'),
        ),
    ]
