from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_adminvouchergenlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='autogenconfig',
            name='notify_site_admin',
            field=models.BooleanField(default=True, verbose_name='Envoyer notification aux admins du site'),
        ),
    ]
