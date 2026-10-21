from dataclasses import dataclass

ANYWHERE_CITY = "Anywhere"
ANYWHERE_COUNTRY = "Worldwide"
ANYWHERE_CAP = 48


@dataclass(frozen=True)
class Market:
    city: str
    country: str
    sources: frozenset[str]


GLOBAL_SOURCES = frozenset(
    {"openstreetmap", "google", "yelp", "apollo", "serpapi", "scrapingbee"}
)

# Worldwide markets prioritizing major international business hubs
ANYWHERE_MARKETS: tuple[Market, ...] = (
    # United States
    Market("New York", "United States", GLOBAL_SOURCES),
    Market("San Francisco", "United States", GLOBAL_SOURCES),
    Market("Los Angeles", "United States", GLOBAL_SOURCES),
    Market("Chicago", "United States", GLOBAL_SOURCES),
    Market("Miami", "United States", GLOBAL_SOURCES),
    Market("Austin", "United States", GLOBAL_SOURCES),
    # United Kingdom
    Market(
        "London",
        "United Kingdom",
        frozenset(
            {
                "openstreetmap",
                "google",
                "yelp",
                "yell",
                "apollo",
                "serpapi",
                "scrapingbee",
            }
        ),
    ),
    Market(
        "Manchester",
        "United Kingdom",
        frozenset({"yell", "apollo", "serpapi", "scrapingbee"}),
    ),
    Market(
        "Birmingham",
        "United Kingdom",
        frozenset({"yell", "apollo", "serpapi", "scrapingbee"}),
    ),
    # Canada
    Market("Toronto", "Canada", GLOBAL_SOURCES),
    Market("Vancouver", "Canada", GLOBAL_SOURCES),
    Market("Montreal", "Canada", GLOBAL_SOURCES),
    # Australia
    Market("Sydney", "Australia", GLOBAL_SOURCES),
    Market("Melbourne", "Australia", GLOBAL_SOURCES),
    Market("Brisbane", "Australia", GLOBAL_SOURCES),
    # Germany / Europe
    Market("Berlin", "Germany", GLOBAL_SOURCES),
    Market("Munich", "Germany", GLOBAL_SOURCES),
    Market("Frankfurt", "Germany", GLOBAL_SOURCES),
    Market("Dublin", "Ireland", GLOBAL_SOURCES),
    # United Arab Emirates
    Market("Dubai", "United Arab Emirates", GLOBAL_SOURCES),
    Market("Abu Dhabi", "United Arab Emirates", GLOBAL_SOURCES),
    # Pakistan
    Market(
        "Lahore",
        "Pakistan",
        frozenset(
            {
                "openstreetmap",
                "google",
                "yelp",
                "businesslist",
                "epages",
                "apollo",
                "serpapi",
                "scrapingbee",
            }
        ),
    ),
    Market("Karachi", "Pakistan", frozenset({"businesslist", "epages"})),
    Market("Islamabad", "Pakistan", frozenset({"businesslist", "epages"})),
)


def is_anywhere(city: str, country: str) -> bool:
    c_city = city.strip().casefold()
    c_country = country.strip().casefold()
    return (
        c_city == ANYWHERE_CITY.casefold()
        or not c_city
        or c_country == ANYWHERE_COUNTRY.casefold()
    )


def markets_for(
    *,
    use_openstreetmap: bool,
    use_google: bool,
    use_yelp: bool,
    use_yell: bool,
    use_businesslist: bool,
    use_epages: bool,
    use_apollo: bool = False,
    use_serpapi: bool = False,
    use_scrapingbee: bool = False,
    country: str | None = None,
) -> list[Market]:
    enabled = {
        name
        for name, selected in (
            ("openstreetmap", use_openstreetmap),
            ("google", use_google),
            ("yelp", use_yelp),
            ("yell", use_yell),
            ("businesslist", use_businesslist),
            ("epages", use_epages),
            ("apollo", use_apollo),
            ("serpapi", use_serpapi),
            ("scrapingbee", use_scrapingbee),
        )
        if selected
    }
    if not enabled:
        return []

    markets = [market for market in ANYWHERE_MARKETS if market.sources & enabled]

    if country and country.strip().casefold() not in ("worldwide", "anywhere"):
        target_country = country.strip().casefold()
        country_markets = [
            m for m in markets if m.country.casefold() == target_country
        ]
        if country_markets:
            return country_markets
        # If country isn't in predefined list, dynamically create a target market for it
        return [
            Market(
                city="Capital",
                country=country.strip(),
                sources=frozenset(enabled),
            )
        ]

    return markets
