from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreUser',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('google_id',  models.CharField(max_length=64, unique=True)),
                ('email',      models.EmailField(unique=True)),
                ('full_name',  models.CharField(max_length=100, verbose_name='Nom complet')),
                ('phone',      models.CharField(blank=True, max_length=20, verbose_name='Téléphone')),
                ('address',    models.TextField(blank=True, verbose_name='Adresse')),
                ('avatar_url', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Utilisateur store', 'verbose_name_plural': 'Utilisateurs store'},
        ),
        # CustomerProfile: session_key nullable + store_user FK
        migrations.AlterField(
            model_name='customerprofile',
            name='session_key',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='store_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='profiles',
                to='store.storeuser',
            ),
        ),
        # Cart: session_key nullable + store_user OneToOne
        migrations.AlterField(
            model_name='cart',
            name='session_key',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='cart',
            name='store_user',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='cart',
                to='store.storeuser',
            ),
        ),
    ]
