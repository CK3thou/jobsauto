"""Normalize posting dates from job-board result formats to UTC timestamps."""

import re
from datetime import date, datetime, timedelta, timezone

_RELATIVE_DATE = re.compile(
    r"(?:posted\s+)?(?:(\d+)\+?\s*(hour|day|week|month)s?\s+ago|today|yesterday)",
    re.IGNORECASE,
)


def parse_posted_at(value: object, *, now: datetime | None = None) -> str | None:
    """Parse common ATS/job-board date values into an ISO UTC timestamp."""
    if value is None or str(value).strip().lower() in {"", "nat", "nan", "none"}:
        return None

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time(), timezone.utc)
    elif hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        if not isinstance(converted, datetime):
            return None
        parsed = converted
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        relative = _RELATIVE_DATE.search(text)
        if relative:
            relative_text = relative.group(0).lower()
            if "today" in relative_text:
                parsed = reference
            elif "yesterday" in relative_text:
                parsed = reference - timedelta(days=1)
            else:
                amount = int(relative.group(1))
                unit = relative.group(2).lower()
                duration = {
                    "hour": timedelta(hours=amount),
                    "day": timedelta(days=amount),
                    "week": timedelta(weeks=amount),
                    "month": timedelta(days=30 * amount),
                }[unit]
                parsed = reference - duration + timedelta(seconds=1)
        else:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError:
                parsed = None
                for date_format in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        parsed = datetime.strptime(text, date_format)
                        break
                    except ValueError:
                        continue
                if parsed is None:
                    return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def is_within_days(posted_at: str | None, days: int = 3, *, now: datetime | None = None) -> bool:
    """Return whether a normalized timestamp falls within the last N days."""
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    parsed = parse_posted_at(posted_at, now=reference)
    if parsed is None:
        return False
    posted = datetime.fromisoformat(parsed)
    return reference.astimezone(timezone.utc) - timedelta(days=days) <= posted <= reference.astimezone(timezone.utc)
