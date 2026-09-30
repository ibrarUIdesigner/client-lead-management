from app.services.directory_listings import (
    epages_profile_matches,
    is_pakistan,
    is_united_kingdom,
    listings_from_businesslist,
    listings_from_epages_profile,
    listings_from_yell,
    listings_from_yelp,
)

BUSINESSLIST_CARD = """
<div class="company with_img" id="cmap_0" data-cmpid="257901">
<div class="company_header"><h3>1 | <a href="/company/257901/north-cafe">North Cafe</a></h3>
<div class="address">12 Mall Road, <b>Lahore</b>, Pakistan</div></div>
<div class="s"><i class="fa fa-phone" aria-label="Phone number"></i>
<span><b>+923001112233</b></span></div>
<div class="s"><i class="fa fa-globe" aria-label="Website"></i><span>Website</span></div>
<div class="mapmarker hidden" data-ltd="31.5200" data-lng="74.3400" data-key="0"></div>
</div>
"""

YELL_CARD = """
<div class="businessCapsule">
<a class="businessCapsule--title" href="/biz/north-cafe-london-100/">North Cafe</a>
<span class="businessCapsule--telephone">020 7946 0991</span>
<span class="businessCapsule--address">1 High Street, London</span>
<a class="businessCapsule--website" href="https://northcafe.example">Website</a>
</div>
"""


def test_businesslist_reads_the_public_card() -> None:
    listings = listings_from_businesslist(
        BUSINESSLIST_CARD,
        category="cafe",
        city="Lahore",
        country="Pakistan",
    )

    assert len(listings) == 1
    lead = listings[0]
    assert lead.source == "businesslist"
    assert lead.source_key == "businesslist:257901"
    assert lead.phone == "+923001112233"
    assert "Mall Road" in (lead.notes or "")
    assert lead.website_status == "present"
    assert lead.website_url is None
    assert lead.google_maps_url is not None


def test_epages_profile_keeps_the_business_site_and_social_pages() -> None:
    payload = {
        "@type": "LocalBusiness",
        "name": "Virsa Pure",
        "email": "support@virsapure.com",
        "telephone": "+92 307 4735522",
        "address": "Office 104, Faisalabad",
        "sameAs": [
            "https://virsapure.com.pk/",
            "https://www.facebook.com/Virsapure",
            "https://www.instagram.com/virsapure/",
        ],
        "openingHours": "Mo-Fr 09:00-17:00",
        "hasMap": "https://www.google.com/maps/@31.43,73.08",
    }

    assert epages_profile_matches(
        payload,
        category="cafe",
        city="Faisalabad",
        require_category=False,
    )
    lead = listings_from_epages_profile(
        payload,
        category="cafe",
        city="Faisalabad",
        country="Pakistan",
        profile_url="https://epages.pk/business/virsa-pure/",
    )

    assert lead is not None
    assert lead.source_key == "epages:virsa-pure"
    assert lead.email == "support@virsapure.com"
    assert lead.website_url == "https://virsapure.com.pk/"
    assert lead.facebook_url == "https://www.facebook.com/Virsapure"
    assert lead.instagram_url == "https://www.instagram.com/virsapure/"
    assert "Hours: Mo-Fr 09:00-17:00" in lead.notes


def test_epages_category_page_keeps_a_city_match_without_the_search_word() -> None:
    payload = {
        "@type": "LocalBusiness",
        "name": "AL-Tuaam",
        "address": "Faisal Town, Lahore",
        "areaServed": [{"@type": "City", "name": "Lahore"}],
        "additionalType": [{"name": "Food & Drink"}],
    }

    assert epages_profile_matches(
        payload,
        category="cafe",
        city="Lahore",
        require_category=False,
    )
    elsewhere = {**payload, "address": "Civil Lines, Faisalabad", "areaServed": "Faisalabad"}
    assert not epages_profile_matches(
        elsewhere,
        category="cafe",
        city="Lahore",
        require_category=False,
    )


def test_yell_reads_a_public_result_card() -> None:
    listings = listings_from_yell(
        YELL_CARD,
        category="cafe",
        city="London",
        country="United Kingdom",
    )

    lead = listings[0]
    assert lead.source == "yell"
    assert lead.source_key == "yell:north-cafe-london-100"
    assert lead.phone == "020 7946 0991"
    assert lead.website_url == "https://northcafe.example"
    assert lead.website_status == "present"


def test_yelp_search_keeps_the_rating_phone_and_hours() -> None:
    listings = listings_from_yelp(
        {
            "businesses": [
                {
                    "id": "cafe-1",
                    "name": "North Cafe",
                    "is_closed": False,
                    "display_phone": "(503) 555-0100",
                    "rating": 4.5,
                    "review_count": 20,
                    "url": "https://www.yelp.com/biz/north-cafe",
                    "categories": [{"title": "Coffee & Tea"}],
                    "location": {"display_address": ["1 Main St", "Portland, OR"]},
                    "coordinates": {"latitude": 45.5, "longitude": -122.6},
                }
            ]
        },
        {
            "cafe-1": {
                "hours": [{"open": [{"day": 0, "start": "0800", "end": "1600"}]}],
            }
        },
        category="cafe",
        city="Portland",
        country="United States",
    )

    lead = listings[0]
    assert lead.source_key == "yelp:cafe-1"
    assert lead.phone == "(503) 555-0100"
    assert lead.industry == "Coffee & Tea"
    assert "Yelp rating 4.5 from 20 reviews" in lead.notes
    assert "Hours: Mon 08:00-16:00" in lead.notes
    assert lead.website_status == "missing"


def test_country_directories_stay_in_their_markets() -> None:
    assert is_pakistan("Pakistan")
    assert is_pakistan("PK")
    assert not is_pakistan("United States")
    assert is_united_kingdom("United Kingdom")
    assert is_united_kingdom("England")
    assert not is_united_kingdom("Pakistan")
