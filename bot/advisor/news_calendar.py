"""High-impact XAUUSD economic event calendar.

No free public API exists for ForexFactory or Investing.com's economic
calendars - both are scraped in practice, which is fragile and breaks
often. The events that actually move gold (NFP, CPI, FOMC, Fed speeches,
GDP, PPI) are published on fixed, pre-announced government/Fed schedules
months in advance, so this module maintains that schedule directly
instead of depending on a scrape that could silently start returning
wrong data.

Maintenance: FOMC_DECISIONS_UTC is sourced from
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm and needs
a yearly top-up. CPI_RELEASES_UTC / PPI_RELEASES_UTC / GDP_RELEASES_UTC
are approximate (BLS/BEA publish exact dates a few months ahead on
bls.gov and bea.gov) - correct them there if a date shifts.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple


class NewsEvent(NamedTuple):
    name: str
    when_utc: datetime


# FOMC statement + press conference (Powell) - second day of each meeting,
# ~18:00 UTC (14:00 ET) for the statement, press conference follows shortly
# after. Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_DECISIONS_UTC: list[date] = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]
FOMC_TIME_UTC = (18, 0)  # hour, minute

# CPI is released monthly, usually 8:30 ET, typically the second week of the
# following month. Approximate - verify against bls.gov/cpi if trading
# around these dates.
CPI_RELEASES_UTC: list[date] = [
    date(2026, 1, 13), date(2026, 2, 11), date(2026, 3, 11), date(2026, 4, 10),
    date(2026, 5, 12), date(2026, 6, 10), date(2026, 7, 14), date(2026, 8, 12),
    date(2026, 9, 10), date(2026, 10, 13), date(2026, 11, 10), date(2026, 12, 10),
]

# PPI is released monthly, usually a day or two before or after CPI.
# Approximate - verify against bls.gov/ppi.
PPI_RELEASES_UTC: list[date] = [
    date(2026, 1, 14), date(2026, 2, 12), date(2026, 3, 12), date(2026, 4, 13),
    date(2026, 5, 13), date(2026, 6, 11), date(2026, 7, 15), date(2026, 8, 13),
    date(2026, 9, 11), date(2026, 10, 14), date(2026, 11, 12), date(2026, 12, 11),
]

# US GDP (advance estimate), quarterly, ~last week of the month following
# quarter end. Approximate - verify against bea.gov.
GDP_RELEASES_UTC: list[date] = [
    date(2026, 1, 29), date(2026, 4, 30), date(2026, 7, 30), date(2026, 10, 29),
]

RELEASE_TIME_UTC = (12, 30)  # 8:30 ET for CPI/PPI/GDP/NFP


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    offset = (4 - d.weekday()) % 7  # Monday=0 ... Friday=4
    return d + timedelta(days=offset)


def _nfp_dates_around(now: datetime) -> list[date]:
    """NFP (Employment Situation) is always the first Friday of the month."""
    dates = []
    for delta_months in (-1, 0, 1, 2):
        month = now.month + delta_months
        year = now.year
        while month > 12:
            month -= 12
            year += 1
        while month < 1:
            month += 12
            year -= 1
        dates.append(_first_friday(year, month))
    return dates


def _combine(d: date, hm: tuple[int, int]) -> datetime:
    return datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=timezone.utc)


def get_upcoming_events(now_utc: datetime | None = None, within_days: int = 14) -> list[NewsEvent]:
    """All tracked high-impact events within `within_days` of now, soonest first."""
    now_utc = now_utc or datetime.now(timezone.utc)
    horizon = now_utc + timedelta(days=within_days)
    events: list[NewsEvent] = []

    for d in FOMC_DECISIONS_UTC:
        events.append(NewsEvent("Fed Interest Rate Decision + Powell Press Conference", _combine(d, FOMC_TIME_UTC)))
    for d in CPI_RELEASES_UTC:
        events.append(NewsEvent("CPI / Core CPI", _combine(d, RELEASE_TIME_UTC)))
    for d in PPI_RELEASES_UTC:
        events.append(NewsEvent("PPI", _combine(d, RELEASE_TIME_UTC)))
    for d in GDP_RELEASES_UTC:
        events.append(NewsEvent("US GDP", _combine(d, RELEASE_TIME_UTC)))
    for d in _nfp_dates_around(now_utc):
        events.append(NewsEvent("Non-Farm Payrolls (NFP)", _combine(d, RELEASE_TIME_UTC)))

    events = [e for e in events if now_utc <= e.when_utc <= horizon]
    events.sort(key=lambda e: e.when_utc)
    return events


def get_next_high_impact_event(now_utc: datetime | None = None) -> tuple[NewsEvent, float] | None:
    """(event, minutes_until) for the soonest upcoming event, or None."""
    now_utc = now_utc or datetime.now(timezone.utc)
    upcoming = get_upcoming_events(now_utc, within_days=14)
    if not upcoming:
        return None
    event = upcoming[0]
    minutes_until = (event.when_utc - now_utc).total_seconds() / 60.0
    return event, minutes_until


def news_status(now_utc: datetime | None = None) -> dict:
    """Returns {'level': 'clear'|'warning'|'danger', 'event': str|None,
    'minutes_until': float|None} for direct use by the scoring engine."""
    result = get_next_high_impact_event(now_utc)
    if result is None:
        return {"level": "clear", "event": None, "minutes_until": None}
    event, minutes_until = result
    if minutes_until <= 5:
        level = "danger"
    elif minutes_until <= 30:
        level = "warning"
    elif minutes_until <= 120:
        level = "upcoming"
    else:
        level = "clear"
    return {"level": level, "event": event.name, "minutes_until": round(minutes_until, 1)}
