"""Which period to compare with, and which past pairs count as 'the same kind of comparison'.

Rules (each returns a note naming the rule, so the report can say how the base was chosen):
  yoy, a calendar month or month to date      same calendar days a year earlier     calendar_month_last_year
  yoy, anything else                          same weekdays, 364 days earlier        same_weekdays_364_days
  pop, a whole calendar month                 the whole previous month               calendar_month
  pop, month to date (1st .. day d)           1st .. day d of the previous month     month_to_date
  pop, a single day                           the same weekday a week earlier        same_weekday_last_week
  pop, anything else                          the window right before, same length   previous_window

History pairs repeat the same rule further back, so a z-score always compares like with like
(the 0.1 code always used year-on-year history, even when the question was month on month).
"""

from __future__ import annotations

import calendar
import datetime as dt

DAY = dt.timedelta(days=1)


def _month_end(y, m):
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def _add_months(d: dt.date, k: int, day=None) -> dt.date:
    y, m = divmod(d.month - 1 + k, 12)
    y, m = d.year + y, m + 1
    return dt.date(y, m, min(day or d.day, calendar.monthrange(y, m)[1]))


def month_kind(w: tuple) -> str | None:
    a, b = w
    if a.day != 1 or a.year != b.year or a.month != b.month:
        return None
    if b == _month_end(b.year, b.month):
        return "calendar_month"
    return "month_to_date" if (b - a).days >= 7 else None


def base(cur: tuple, how: str) -> tuple:
    """(base window, rule name)."""
    a, b = cur
    mk = month_kind(cur)
    if how == "yoy":
        if mk:
            return (_add_months(a, -12), _add_months(b, -12, b.day) if mk == "month_to_date" else _month_end(b.year - 1, b.month)), \
                "calendar_month_last_year"
        return (a - 364 * DAY, b - 364 * DAY), "same_weekdays_364_days"
    if how == "pop":
        if mk == "calendar_month":
            p = _add_months(a, -1)
            return (p, _month_end(p.year, p.month)), "calendar_month"
        if mk == "month_to_date":
            p = _add_months(a, -1)
            return (p, _add_months(b, -1, b.day)), "month_to_date"
        if a == b:
            return (a - 7 * DAY, b - 7 * DAY), "same_weekday_last_week"
        n = (b - a).days + 1
        return (a - n * DAY, b - n * DAY), "previous_window"
    raise ValueError(f"unknown base '{how}'")


def step_back(cur: tuple, k: int) -> tuple:
    """The window k steps before cur, of the same kind: months step by months, other windows by their own length."""
    a, b = cur
    mk = month_kind(cur)
    if mk == "calendar_month":
        p = _add_months(a, -k)
        return (p, _month_end(p.year, p.month))
    if mk == "month_to_date":
        return (_add_months(a, -k), _add_months(b, -k, b.day))
    n = (b - a).days + 1
    if n == 1:
        return (a - 7 * k * DAY, b - 7 * k * DAY)
    return (a - n * k * DAY, b - n * k * DAY)


def explicit_kind(cur: tuple, b: tuple) -> tuple:
    """(how, rule) of an explicit base: the rule it matches, if any, so history can follow the same rule;
    else (None, 'explicit_offset'), and history keeps the same distance between the two windows."""
    for how in ("pop", "yoy"):
        got, rule = base(cur, how)
        if got == tuple(b):
            return how, rule
    return None, "explicit_offset"


def history(cur: tuple, b: tuple, how: str | None, k: int) -> list[tuple]:
    """k past (window, base) pairs of the same kind as (cur, b), newest first.

    how: 'yoy' / 'pop' re-apply that rule to each past window; None keeps the explicit offset between cur and b."""
    out = []
    shift = (cur[0] - b[0], cur[1] - b[1])
    for i in range(1, k + 1):
        w = step_back(cur, i)
        if how in ("yoy", "pop"):
            out.append((w, base(w, how)[0]))
        else:
            out.append((w, (w[0] - shift[0], w[1] - shift[1])))
    return out


def days(w: tuple) -> list[dt.date]:
    return [w[0] + i * DAY for i in range((w[1] - w[0]).days + 1)]
