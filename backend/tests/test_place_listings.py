from app.services.place_listings import (
    clamp_bbox,
    listings_from_google,
    listings_from_overpass,
    overpass_query,
)


def test_overpass_query_uses_a_known_category() -> None:
    bbox = clamp_bbox(31.4, 74.2, 31.6, 74.4)
    query = overpass_query("dentist", bbox)

    assert 'nwr["amenity"="dentist"]' in query
    assert "out center tags 30" in query


def test_large_areas_are_limited_to_the_city_center() -> None:
    bbox = clamp_bbox(24.0, 66.0, 37.0, 75.0)

    assert bbox.clamped is True
    assert abs((bbox.north - bbox.south) - 0.45) < 0.001
    assert abs((bbox.east - bbox.west) - 0.45) < 0.001


def test_openstreetmap_listing_without_a_website_is_a_strong_pitch() -> None:
    listings = listings_from_overpass(
        {
            "elements": [
                {
                    "type": "node",
                    "id": 42,
                    "lat": 31.52,
                    "lon": 74.35,
                    "tags": {
                        "name": "Smile Dental",
                        "amenity": "dentist",
                        "phone": "+92 42 111 222 333",
                        "addr:housenumber": "12",
                        "addr:street": "Mall Road",
                        "opening_hours": "Mo-Fr 09:00-17:00",
                    },
                }
            ]
        },
        category="dentist",
        city="Lahore",
        country="Pakistan",
    )

    assert len(listings) == 1
    lead = listings[0]
    assert lead.source_key == "osm:node:42"
    assert lead.source == "openstreetmap"
    assert lead.website_status == "missing"
    assert lead.lead_score == 85
    assert lead.phone == "+92 42 111 222 333"
    assert "Mall Road" in (lead.notes)
    assert "no website listed" in lead.description
    assert lead.google_maps_url is not None
    assert lead.google_maps_url.startswith("https://")


def test_a_facebook_link_is_not_treated_as_a_website() -> None:
    listings = listings_from_overpass(
        {
            "elements": [
                {
                    "type": "way",
                    "id": 9,
                    "center": {"lat": 47.6, "lon": -122.3},
                    "tags": {
                        "name": "Cedar Studio",
                        "craft": "photographer",
                        "website": "https://facebook.com/cedarstudio",
                        "contact:instagram": "@cedarstudio",
                    },
                }
            ]
        },
        category="photographer",
        city="Seattle",
        country="United States",
    )

    lead = listings[0]
    assert lead.website_url is None
    assert lead.website_status == "social_only"
    assert lead.facebook_url == "https://facebook.com/cedarstudio"
    assert lead.instagram_url == "https://instagram.com/cedarstudio"
    assert lead.lead_score == 72


def test_google_place_keeps_the_website_and_maps_link() -> None:
    listings = listings_from_google(
        {
            "places": [
                {
                    "id": "place-1",
                    "displayName": {"text": "Northwind Cafe"},
                    "formattedAddress": "1 Pike St, Seattle",
                    "nationalPhoneNumber": "(206) 555-0100",
                    "websiteUri": "https://northwind.example",
                    "googleMapsUri": "https://maps.google.com/?cid=1",
                    "businessStatus": "OPERATIONAL",
                    "location": {"latitude": 47.6, "longitude": -122.3},
                    "primaryTypeDisplayName": {"text": "Cafe"},
                },
                {
                    "id": "place-closed",
                    "displayName": {"text": "Closed Shop"},
                    "businessStatus": "CLOSED_PERMANENTLY",
                },
            ]
        },
        category="cafe",
        city="Seattle",
        country="United States",
    )

    assert len(listings) == 1
    lead = listings[0]
    assert lead.source_key == "google:place-1"
    assert lead.website_status == "present"
    assert lead.website_url == "https://northwind.example"
    assert lead.lead_score == 48
    assert lead.google_maps_url == "https://maps.google.com/?cid=1"
    assert "redesign" in lead.description
