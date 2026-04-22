from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0011_default_admin_forfait'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='partner_conditions_pdf',
            field=models.FileField(blank=True, null=True, upload_to='site_config/', verbose_name='PDF conditions de partenariat'),
        ),
    ]
