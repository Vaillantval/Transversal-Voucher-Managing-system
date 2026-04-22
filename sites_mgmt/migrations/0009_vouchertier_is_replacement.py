from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0008_alter_vouchertier'),
    ]

    operations = [
        migrations.AddField(
            model_name='vouchertier',
            name='is_replacement',
            field=models.BooleanField(default=False, verbose_name='Remplacement'),
        ),
    ]
