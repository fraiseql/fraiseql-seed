"""Column groups for correlated multi-column generation."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from faker import Faker

# ---------------------------------------------------------------------------
# Locale infrastructure
# ---------------------------------------------------------------------------

COUNTRY_TO_LOCALE: dict[str, str] = {
    "United States": "en_US",
    "France": "fr_FR",
    "Germany": "de_DE",
    "Japan": "ja_JP",
    "United Kingdom": "en_GB",
    "Italy": "it_IT",
    "Spain": "es_ES",
    "Brazil": "pt_BR",
    "Canada": "en_CA",
    "Australia": "en_AU",
    "Mexico": "es_MX",
    "Netherlands": "nl_NL",
    "Poland": "pl_PL",
    "Sweden": "sv_SE",
    "Norway": "no_NO",
}

LOCALE_TO_COUNTRY: dict[str, str] = {v: k for k, v in COUNTRY_TO_LOCALE.items()}

_SUPPORTED_LOCALES: list[str] = list(COUNTRY_TO_LOCALE.values())

_faker_instances: dict[str, Faker] = {}


def _get_faker(locale: str) -> Faker:
    """Get or create a Faker instance for the given locale."""
    if locale not in _faker_instances:
        _faker_instances[locale] = Faker(locale)
    return _faker_instances[locale]


@dataclass
class ColumnGroup:
    """A group of semantically related columns generated atomically."""

    name: str
    fields: frozenset[str]
    generator: Callable[[dict[str, Any]], dict[str, Any]]
    min_match: int = 2


def generate_address(context: dict[str, Any]) -> dict[str, Any]:
    """Generate coherent address components from a single locale."""
    country_override = context.get("country")

    if country_override:
        locale = COUNTRY_TO_LOCALE.get(country_override, "en_US")
    else:
        locale = random.choice(_SUPPORTED_LOCALES)

    fake = _get_faker(locale)

    country = country_override or LOCALE_TO_COUNTRY.get(locale, fake.country())
    city = fake.city()
    state = fake.state() if hasattr(fake, "state") else fake.city()
    postal_code = fake.postcode()
    street = fake.street_address()
    address = fake.address()
    zipcode = postal_code

    return {
        "country": country,
        "state": state,
        "city": city,
        "postal_code": postal_code,
        "street": street,
        "address": address,
        "zip": zipcode,
        "zipcode": zipcode,
        "zip_code": zipcode,
        "_locale": locale,
    }


def generate_person(context: dict[str, Any]) -> dict[str, Any]:
    """Generate coherent person name and email."""
    locale = context.get("_locale", "en_US")
    fake = _get_faker(locale)

    first_name = fake.first_name()
    last_name = fake.last_name()
    name = f"{first_name} {last_name}"

    email_local = f"{first_name.lower()}.{last_name.lower()}"
    email_suffix = context.get("_email_suffix")
    if email_suffix is not None:
        email_local = f"{email_local}{email_suffix}"
    email = f"{email_local}@{fake.free_email_domain()}"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "name": name,
        "email": email,
    }


LOCALE_CENTROIDS: dict[str, tuple[float, float]] = {
    "en_US": (39.8, -98.6),
    "fr_FR": (46.6, 2.2),
    "de_DE": (51.2, 10.4),
    "ja_JP": (36.2, 138.3),
    "en_GB": (53.5, -2.4),
    "it_IT": (42.5, 12.6),
    "es_ES": (40.0, -3.7),
    "pt_BR": (-14.2, -51.9),
    "en_CA": (56.1, -106.3),
    "en_AU": (-25.3, 133.8),
    "es_MX": (23.6, -102.6),
    "nl_NL": (52.1, 5.3),
    "pl_PL": (51.9, 19.1),
    "sv_SE": (62.0, 15.0),
    "no_NO": (64.5, 12.5),
}

_GEO_JITTER = 5.0  # degrees of random jitter around centroid


def generate_geo(context: dict[str, Any]) -> dict[str, Any]:
    """Generate coherent lat/lng pair, biased by locale if available."""
    locale = context.get("_locale")

    if locale and locale in LOCALE_CENTROIDS:
        center_lat, center_lng = LOCALE_CENTROIDS[locale]
        lat = center_lat + random.uniform(-_GEO_JITTER, _GEO_JITTER)
        lng = center_lng + random.uniform(-_GEO_JITTER, _GEO_JITTER)
    else:
        lat = random.uniform(-90, 90)
        lng = random.uniform(-180, 180)

    # Clamp to valid ranges
    lat = max(-90.0, min(90.0, lat))
    lng = max(-180.0, min(180.0, lng))

    lat = round(lat, 6)
    lng = round(lng, 6)

    return {
        "latitude": lat,
        "longitude": lng,
        "lat": lat,
        "lng": lng,
        "lon": lng,
    }


BUILTIN_GROUPS: list[ColumnGroup] = [
    ColumnGroup(
        name="address",
        fields=frozenset(
            {
                "country",
                "state",
                "city",
                "postal_code",
                "street",
                "address",
                "zip",
                "zipcode",
                "zip_code",
            }
        ),
        generator=generate_address,
    ),
    ColumnGroup(
        name="person",
        fields=frozenset({"first_name", "last_name", "name", "email"}),
        generator=generate_person,
    ),
    ColumnGroup(
        name="geo",
        fields=frozenset({"latitude", "longitude", "lat", "lng", "lon"}),
        generator=generate_geo,
    ),
]


class GroupRegistry:
    """Registry for detecting and managing column groups."""

    def __init__(self, groups: list[ColumnGroup] | None = None):
        self._groups = groups if groups is not None else BUILTIN_GROUPS

    def detect_groups(self, column_names: set[str]) -> list[ColumnGroup]:
        """Return active groups where >= min_match columns are present."""
        return [
            group for group in self._groups if len(column_names & group.fields) >= group.min_match
        ]

    def col_to_group(
        self,
        active_groups: list[ColumnGroup],
        column_names: set[str],
    ) -> dict[str, ColumnGroup]:
        """Build reverse lookup: column name -> owning group (only for existing columns)."""
        result: dict[str, ColumnGroup] = {}
        for group in active_groups:
            for col in group.fields & column_names:
                result[col] = group
        return result
