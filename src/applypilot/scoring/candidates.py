"""Eligibility checks for the focused job-review shortlist."""

import re

ROLE_PATTERNS = (
    re.compile(r"\bit support\b", re.I),
    re.compile(r"\bhelp\s*desk\b", re.I),
    re.compile(r"\bservice desk\b", re.I),
    re.compile(r"\b(?:technical )?support (?:engineer|specialist|analyst)\b", re.I),
    re.compile(r"\bdata analyst\b", re.I),
    re.compile(r"\bdigital marketing\b", re.I),
    re.compile(r"\bmarketing (?:analyst|specialist)\b", re.I),
)

EMEA_LOCATIONS = (
    "zambia", "africa", "emea", "europe", "united kingdom", "great britain",
    "uk", "ireland", "germany", "netherlands", "france", "spain", "portugal",
    "poland", "sweden", "norway", "denmark", "finland", "switzerland",
    "belgium", "austria", "italy", "czechia", "czech republic", "romania",
    "greece", "hungary", "ukraine", "estonia", "latvia", "lithuania",
    "south africa", "kenya", "nigeria", "ghana", "rwanda", "uganda",
    "tanzania", "botswana", "malawi", "egypt", "morocco", "tunisia",
    "united arab emirates", "uae", "saudi arabia", "qatar", "israel",
    "turkey", "turkiye", "jordan", "bahrain", "kuwait", "oman",
)

WORLDWIDE_REMOTE_PATTERNS = (
    re.compile(r"\bremote (?:worldwide|anywhere|global)\b", re.I),
    re.compile(r"\b(?:worldwide|global) remote\b", re.I),
    re.compile(r"\bwork remotely from anywhere\b", re.I),
    re.compile(r"\bremote from anywhere\b", re.I),
    re.compile(r"\bremote - any location\b", re.I),
)


def is_qualifying_job(job: dict) -> bool:
    """Return whether a job matches a target role and eligible geography."""
    title = job.get("title") or ""
    if not any(pattern.search(title) for pattern in ROLE_PATTERNS):
        return False

    location = job.get("location") or ""
    url = job.get("url") or ""
    scope = f"{location} {url}".lower()
    if any(place in scope for place in EMEA_LOCATIONS):
        return True

    description = job.get("full_description") or ""
    remote_scope = f"{scope} {description}"
    return any(pattern.search(remote_scope) for pattern in WORLDWIDE_REMOTE_PATTERNS)
