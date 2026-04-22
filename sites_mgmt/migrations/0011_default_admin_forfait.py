from django.db import migrations


def create_default_admin_forfait(apps, schema_editor):
    VoucherTier = apps.get_model('sites_mgmt', 'VoucherTier')
    HotspotSite = apps.get_model('sites_mgmt', 'HotspotSite')

    if VoucherTier.objects.filter(is_admin_code=True).exists():
        return

    tier = VoucherTier.objects.create(
        label         = 'Forfait Admin',
        duration      = 120,
        unit          = 'days',
        price_htg     = 0,
        is_admin_code = True,
        max_vouchers  = 10,
        is_active     = True,
    )
    tier.sites.set(HotspotSite.objects.filter(is_active=True))


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0010_vouchertier_admin_code'),
    ]

    operations = [
        migrations.RunPython(create_default_admin_forfait, migrations.RunPython.noop),
    ]
