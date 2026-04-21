from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0005_remove_auto_generate_vouchers'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='partner_conditions',
            field=models.TextField(blank=True, verbose_name='Conditions de partenariat'),
        ),
        migrations.CreateModel(
            name='PartnerProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Nom')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('price_usd', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Prix (USD)')),
                ('image', models.ImageField(blank=True, null=True, upload_to='partner_products/', verbose_name='Image')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Produit partenaire',
                'verbose_name_plural': 'Produits partenaires',
                'ordering': ['name'],
            },
        ),
    ]
