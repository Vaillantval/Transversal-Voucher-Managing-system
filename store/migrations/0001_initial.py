from django.db import migrations, models
import django.db.models.deletion
import store.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites_mgmt', '0013_hotspotsite_coords'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreBanner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Titre')),
                ('subtitle', models.CharField(blank=True, max_length=200, verbose_name='Sous-titre')),
                ('image', models.ImageField(upload_to='banners/', verbose_name='Image')),
                ('cta_text', models.CharField(default='Voir les plans', max_length=50, verbose_name='Texte bouton')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={'verbose_name': 'Bannière', 'verbose_name_plural': 'Bannières', 'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='CustomerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=64, unique=True)),
                ('full_name', models.CharField(max_length=100, verbose_name='Nom complet')),
                ('phone', models.CharField(max_length=20, verbose_name='Téléphone')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('preferred_site', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='sites_mgmt.hotspotsite', verbose_name='Site préféré'
                )),
            ],
            options={'verbose_name': 'Profil client', 'verbose_name_plural': 'Profils clients'},
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='store.cart')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites_mgmt.hotspotsite')),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites_mgmt.vouchertier')),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(default=store.models._gen_reference, max_length=30, unique=True)),
                ('status', models.CharField(
                    choices=[('pending','En attente'),('paid','Payé'),('processing','En traitement'),('delivered','Livré'),('failed','Échoué')],
                    default='pending', max_length=20
                )),
                ('total_htg', models.DecimalField(decimal_places=2, max_digits=10)),
                ('plopplop_transaction_id', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='store.customerprofile')),
            ],
            options={'verbose_name': 'Commande', 'verbose_name_plural': 'Commandes', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=8)),
                ('voucher_codes', models.JSONField(default=list)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='store.order')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites_mgmt.hotspotsite')),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sites_mgmt.vouchertier')),
            ],
        ),
    ]
