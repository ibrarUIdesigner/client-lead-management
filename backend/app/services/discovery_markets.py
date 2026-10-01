from dataclasses import dataclass

ANYWHERE_CITY = "Anywhere"
ANYWHERE_COUNTRY = "Worldwide"
ANYWHERE_CAP = 48


@dataclass(frozen=True)
class Market:
    city: str
    country: str
    sources: frozenset[str]


# Directories only publish certain places. An "anywhere" search uses those
# places so a category can be run without typing a city.
ANYWHERE_MARKETS: tuple[Market, ...] = (
    Market(
        "Lahore",
        "Pakistan",
        frozenset({"openstreetmap", "google", "yelp", "businesslist", "epages"}),
    ),
    Market("Karachi", "Pakistan", frozenset({"businesslist", "epages"})),
    Market("Islamabad", "Pakistan", frozenset({"businesslist", "epages"})),
    Market(
        "London",
        "United Kingdom",
        frozenset({"openstreetmap", "google", "yelp", "yell"}),
    ),
    Market("Manchester", "United Kingdom", frozenset({"yell"})),
    Market("Birmingham", "United Kingdom", frozenset({"yell"})),
    Market("Portland", "United States", frozenset({"openstreetmap", "google", "yelp"})),
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
        )
        if selected
    }
    return [market for market in ANYWHERE_MARKETS if market.sources & enabled]
