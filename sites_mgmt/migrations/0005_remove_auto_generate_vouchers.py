from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0004_hotspotsite_sites_mgmt__is_acti_6c9a3b_idx'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hotspotsite',
            name='auto_generate_vouchers',
        ),
    ]
