"""Unit tests for Business Discovery skill modules."""

import json
import pytest
from unittest.mock import MagicMock, patch

from scripts.config import Config, ConfigurationError
from scripts.models import (
    BusinessSearchParams,
    LocationCoordinates,
    LocationOrigin,
)
from scripts.maps_service import (
    GoogleMapsService,
    GeocodingError,
    PlacesSearchError,
)
from scripts.discover import main


def test_config_from_env_missing(monkeypatch):
    """Test ConfigurationError raised when API key is missing."""
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="GOOGLE_MAPS_API_KEY environment variable is not set"):
        Config.from_env()


def test_config_from_env_explicit():
    """Test loading Config from explicit key."""
    config = Config.from_env(explicit_key="test_key_123")
    assert config.api_key == "test_key_123"


def test_calculate_distance_meters():
    """Test Haversine distance calculation."""
    coord1 = LocationCoordinates(latitude=23.0120, longitude=72.5630)
    coord2 = LocationCoordinates(latitude=23.0360, longitude=72.5610)

    dist = GoogleMapsService.calculate_distance_meters(coord1, coord2)
    assert 2500 < dist < 2800


def test_geocode_address_success():
    """Test successful address geocoding."""
    mock_client = MagicMock()
    mock_client.geocode.return_value = [
        {
            "formatted_address": "Paldi, Ahmedabad, Gujarat, India",
            "geometry": {"location": {"lat": 23.0120, "lng": 72.5630}},
        }
    ]

    service = GoogleMapsService(api_key="test_key", client=mock_client)
    origin = service.geocode_address("Paldi, Ahmedabad, Gujarat, India")

    assert origin.query_address == "Paldi, Ahmedabad, Gujarat, India"
    assert origin.formatted_address == "Paldi, Ahmedabad, Gujarat, India"
    assert origin.coordinates.latitude == 23.0120
    assert origin.coordinates.longitude == 72.5630


def test_search_businesses_rating_sorting_and_capping():
    """Test business search ranks by average rating descending and caps at max_results."""
    mock_client = MagicMock()
    mock_client.geocode.return_value = [
        {
            "formatted_address": "Paldi, Ahmedabad, Gujarat, India",
            "geometry": {"location": {"lat": 23.0120, "lng": 72.5630}},
        }
    ]

    # Generate 60 mock results with varying ratings
    mock_places = []
    for i in range(1, 61):
        mock_places.append({
            "place_id": f"place_{i}",
            "name": f"Plumber Service {i}",
            "vicinity": f"Address {i}",
            "geometry": {"location": {"lat": 23.0120 + (i * 0.0001), "lng": 72.5630 + (i * 0.0001)}},
            "rating": round((i % 5) + 1.0, 1),  # Ratings range 1.0 to 5.0
            "user_ratings_total": i * 10,
            "business_status": "OPERATIONAL",
            "types": ["plumber"],
        })

    mock_client.places_nearby.return_value = {"results": mock_places}

    service = GoogleMapsService(api_key="test_key", client=mock_client, page_delay_seconds=0)
    params = BusinessSearchParams(
        area="Paldi, Ahmedabad, Gujarat, India",
        radius_meters=5000,
        purpose="plumbers",
        max_results=50,
        sort_by="rating",
    )

    result = service.search_businesses(params)

    # Should cap at top 50 results
    assert result.total_found == 50
    assert len(result.businesses) == 50

    # Primary business should have the highest average rating
    top_biz = result.businesses[0]
    second_biz = result.businesses[1]

    assert top_biz.average_rating >= second_biz.average_rating
    assert top_biz.rating == top_biz.average_rating
    assert top_biz.user_ratings_total is not None
    assert top_biz.total_ratings == top_biz.user_ratings_total


def test_cli_main_json_output_with_ratings(capsys):
    """Test CLI execution producing JSON output with average rating and rating count."""
    mock_result = {
        "results": [
            {
                "place_id": "place_top",
                "name": "Top Plumber",
                "vicinity": "Paldi",
                "geometry": {"location": {"lat": 23.0125, "lng": 72.5635}},
                "rating": 4.9,
                "user_ratings_total": 120,
                "business_status": "OPERATIONAL",
                "types": ["plumber"],
            }
        ]
    }

    with patch("googlemaps.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.geocode.return_value = [
            {
                "formatted_address": "Paldi, Ahmedabad, Gujarat, India",
                "geometry": {"location": {"lat": 23.0120, "lng": 72.5630}},
            }
        ]
        mock_client.places_nearby.return_value = mock_result

        exit_code = main([
            "--area", "Paldi, Ahmedabad, Gujarat, India",
            "--radius", "5000",
            "--purpose", "plumbers",
            "--api-key", "dummy_key",
            "--max-results", "50",
            "--json"
        ])

        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_found"] == 1
        biz = data["businesses"][0]
        assert biz["name"] == "Top Plumber"
        assert biz["average_rating"] == 4.9
        assert biz["user_ratings_total"] == 120
