from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_auto_generate_vouchers'),
        ('sites_mgmt', '0005_remove_auto_generate_vouchers'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutoGenConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False, verbose_name='Génération automatique activée')),
                ('count_per_tier', models.PositiveIntegerField(default=100, verbose_name='Vouchers à générer par forfait')),
                ('delay_hours', models.PositiveIntegerField(default=24, verbose_name='Délai avant génération (heures après alerte stock)')),
                ('sites', models.ManyToManyField(blank=True, related_name='autogen_configs', to='sites_mgmt.hotspotsite', verbose_name='Sites concernés')),
            ],
            options={
                'verbose_name': 'Configuration génération automatique',
            },
        ),
    ]
