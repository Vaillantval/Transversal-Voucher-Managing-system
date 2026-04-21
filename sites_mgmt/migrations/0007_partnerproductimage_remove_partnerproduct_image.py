from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0006_partnerproduct_siteconfig_partner_conditions'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='partner_products/')),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='sites_mgmt.partnerproduct')),
            ],
            options={'ordering': ['order', 'pk']},
        ),
        migrations.RemoveField(
            model_name='partnerproduct',
            name='image',
        ),
    ]
