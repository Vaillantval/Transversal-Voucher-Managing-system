from zoneinfo import ZoneInfo

# Fuseau horaire de référence de l'application
TZ_HAITI = ZoneInfo('America/Port-au-Prince')


def find_tier(tiers, minutes):
    """Retourne le VoucherTier correspondant à une durée en minutes (pré-chargé)."""
    for t in tiers:
        if t.min_minutes <= minutes <= t.max_minutes:
            return t
    return None
