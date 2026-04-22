from zoneinfo import ZoneInfo

# Fuseau horaire de référence de l'application
TZ_HAITI = ZoneInfo('America/Port-au-Prince')


def find_tier(tiers, minutes):
    """Retourne le VoucherTier correspondant à une durée en minutes (match exact ±2 min)."""
    for t in tiers:
        if abs(t.duration_minutes - minutes) <= 2:
            return t
    return None
