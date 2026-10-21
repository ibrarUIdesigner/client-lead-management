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
    Market("New York", "United States", GLOBAL_SOURCES),
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
    Market("San Francisco", "United States", GLOBAL_SOURCES),
    Market("Toronto", "Canada", GLOBAL_SOURCES),
    Market("Sydney", "Australia", GLOBAL_SOURCES),
    Market("Chicago", "United States", GLOBAL_SOURCES),
    Market("Los Angeles", "United States", GLOBAL_SOURCES),
    Market("Miami", "United States", GLOBAL_SOURCES),
    Market(
        "Manchester",
        "United Kingdom",
        frozenset({"yell", "apollo", "serpapi", "scrapingbee"}),
    ),
    Market("Berlin", "Germany", GLOBAL_SOURCES),
    Market("Dublin", "Ireland", GLOBAL_SOURCES),
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
    return city.strip().casefold() == ANYWHERE_CITY.casefold()


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
    return [market for market in ANYWHERE_MARKETS if market.sources & enabled]
