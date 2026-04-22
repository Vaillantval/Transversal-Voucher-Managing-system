from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0007_partnerproductimage_remove_partnerproduct_image'),
    ]

    operations = [
        # Nouveaux champs
        migrations.AddField(
            model_name='vouchertier',
            name='duration',
            field=models.PositiveIntegerField(default=24, verbose_name='Durée'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='vouchertier',
            name='unit',
            field=models.CharField(
                choices=[('hours', 'Heures'), ('days', 'Jours'),
                         ('months', 'Mois'), ('years', 'Années')],
                default='hours', max_length=10, verbose_name='Unité'
            ),
        ),
        migrations.AddField(
            model_name='vouchertier',
            name='price_htg_default',
            field=models.DecimalField(decimal_places=2, default=0,
                                      max_digits=10, verbose_name='Prix (HTG)'),
        ),
        migrations.AddField(
            model_name='vouchertier',
            name='sites',
            field=models.ManyToManyField(
                blank=True, related_name='tiers',
                to='sites_mgmt.hotspotsite', verbose_name='Sites'
            ),
        ),
        # Copier price_htg existant vers le nouveau champ (migration de données)
        migrations.RunSQL(
            "UPDATE sites_mgmt_vouchertier SET price_htg_default = price_htg, "
            "duration = COALESCE(max_minutes / 60, 24), unit = 'hours'",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Supprimer les anciens champs
        migrations.RemoveField(model_name='vouchertier', name='min_minutes'),
        migrations.RemoveField(model_name='vouchertier', name='max_minutes'),
        migrations.RemoveField(model_name='vouchertier', name='price_htg'),
        # Renommer le nouveau champ prix
        migrations.RenameField(
            model_name='vouchertier',
            old_name='price_htg_default',
            new_name='price_htg',
        ),
        # Mettre à jour le ordering
        migrations.AlterModelOptions(
            name='vouchertier',
            options={
                'ordering': ['duration', 'unit'],
                'verbose_name': 'Forfait tarifaire',
                'verbose_name_plural': 'Forfaits tarifaires',
            },
        ),
    ]
