from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100, verbose_name='Prénom')),
                ('last_name', models.CharField(max_length=100, verbose_name='Nom')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('address', models.TextField(verbose_name='Adresse')),
                ('phone', models.CharField(max_length=30, verbose_name='Téléphone')),
                ('accepted_equipment', models.BooleanField(default=False, verbose_name='Détient équipement réseau')),
                ('accepted_conditions', models.BooleanField(default=False, verbose_name='Accepte les conditions')),
                ('status', models.CharField(
                    choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Rejeté')],
                    default='pending', max_length=20, verbose_name='Statut',
                )),
                ('admin_notes', models.TextField(blank=True, verbose_name='Notes admin')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='partner_application',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Compte créé',
                )),
            ],
            options={
                'verbose_name': 'Demande partenaire',
                'verbose_name_plural': 'Demandes partenaires',
                'ordering': ['-created_at'],
            },
        ),
    ]
