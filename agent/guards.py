"""Checks on the model's answer before it is accepted.

unfetched_days(): dates the answer talks about without their data having been fetched,
i.e. invented content. Dates are recognised in ISO, German and English notation.
"""
import re
from datetime import date

from .tools.calendar import fetched_days

MONTHS = {
    'jan': 1, 'januar': 1, 'january': 1, 'feb': 2, 'februar': 2, 'february': 2,
    'mär': 3, 'märz': 3, 'maerz': 3, 'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'mai': 5, 'may': 5, 'jun': 6, 'juni': 6, 'june': 6, 'jul': 7, 'juli': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'okt': 10, 'oktober': 10, 'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dez': 12, 'dezember': 12, 'dec': 12, 'december': 12,
}
_MONTH = '|'.join(sorted(MONTHS, key=len, reverse=True))  # longest first: 'november' before 'nov'

# Each pattern returns (year or None, month as number or name, day).
_PATTERNS = [
    (re.compile(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b'),                                  # 2026-11-04
     lambda m: (m[1], m[2], m[3])),
    (re.compile(r'\b(\d{1,2})\.(\d{1,2})\.(?:(\d{4})\b)?'),                           # 4.11.2026 / 4.11.
     lambda m: (m[3], m[2], m[1])),
    (re.compile(rf'\b(\d{{1,2}})\.?\s*({_MONTH})\.?(?:\s*(\d{{4}}))?\b', re.I),       # 4. November 2026
     lambda m: (m[3], m[2], m[1])),
    (re.compile(rf'\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(\d{{4}}))?', re.I),  # Nov 4th, 2026
     lambda m: (m[3], m[1], m[2])),
]


def dates_in(text: str) -> set[str]:
    """ISO dates mentioned in the text. Things that are no real date (14.30, 30 February) are skipped."""
    years = re.findall(r'\b(20\d\d)\b', text)
    default_year = int(max(set(years), key=years.count)) if years else date.today().year
    found = set()
    for pattern, parts in _PATTERNS:
        for match in pattern.finditer(text):
            year, month, day = parts(match)
            month = int(month) if month.isdigit() else MONTHS.get(month.lower().rstrip('.'))
            try:
                found.add(date(int(year) if year else default_year, month, int(day)).isoformat())
            except (TypeError, ValueError):
                pass
    return found


def unfetched_days(answer: str, results) -> list[str]:
    return sorted(dates_in(answer) - fetched_days(results))
