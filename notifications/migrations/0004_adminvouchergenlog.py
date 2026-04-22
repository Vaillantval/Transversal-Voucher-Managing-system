import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_autogenconfig'),
        ('sites_mgmt', '0011_default_admin_forfait'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminVoucherGenLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateField()),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_gen_logs',
                    to='sites_mgmt.hotspotsite',
                )),
                ('tier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_gen_logs',
                    to='sites_mgmt.vouchertier',
                )),
            ],
            options={
                'verbose_name': 'Log génération vouchers admin',
                'unique_together': {('site', 'tier')},
            },
        ),
    ]
