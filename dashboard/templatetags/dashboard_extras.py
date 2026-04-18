from django import template

register = template.Library()


@register.filter
def split(value, delimiter=','):
    return value.split(delimiter)


@register.filter
def smart_duration(minutes):
    """
    Converts a duration in minutes to a human-readable string.
    Integer division only:  min → h → j → mois → an(s)
    """
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return "—"

    if m <= 0:
        return "—"
    if m < 60:
        return f"{m} min"

    hours = m // 60
    if hours < 24:
        return f"{hours} h"

    days = m // 1440          # 60 * 24
    if days < 30:
        return f"{days} j"

    # Approximate months: 30-day months
    months = days // 30
    if months < 12:
        return f"{months} mois"

    # Approximate years: 365-day years (leap years handled below)
    # Use 365.25 average to stay accurate over long spans, then floor
    years = int(days // 365.25)
    if years == 1:
        return "1 an"
    return f"{years} ans"


@register.filter
def htg(value):
    """Format a number as HTG currency with space thousands separator."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    # Format with comma thousands separator then swap to space (French style)
    formatted = f"{n:,.0f}".replace(",", "\u202f")  # narrow no-break space
    return f"{formatted} HTG"
