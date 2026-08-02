"""Unit tests for KML Exporter and export_kml.py script."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.kml_exporter import (
    KMLExporter,
    KMLExporterError,
    KMLFileWriteError,
    InvalidInputError,
)
from scripts.export_kml import main as export_kml_main
from scripts.discover import main as discover_main
from scripts.models import (
    BusinessDiscoveryResult,
    BusinessInfo,
    LocationCoordinates,
    LocationOrigin,
)


@pytest.fixture
def sample_discovery_result() -> BusinessDiscoveryResult:
    """Fixture returning a mock BusinessDiscoveryResult instance."""
    origin = LocationOrigin(
        query_address="Paldi, Ahmedabad, Gujarat, India",
        formatted_address="Paldi, Ahmedabad, Gujarat 380007, India",
        coordinates=LocationCoordinates(latitude=23.0120, longitude=72.5630),
    )
    biz1 = BusinessInfo(
        place_id="place_1",
        name="Apex Plumbers",
        address="Paldi Cross Rd, Ahmedabad",
        coordinates=LocationCoordinates(latitude=23.0130, longitude=72.5640),
        distance_meters=150.0,
        average_rating=4.9,
        rating=4.9,
        user_ratings_total=128,
        total_ratings=128,
        business_status="OPERATIONAL",
        phone_number="+91 98765 43210",
        website="https://apexplumbers.example.com",
        google_maps_url="https://www.google.com/maps/place/?q=place_id:place_1",
        types=["plumber", "point_of_interest"],
    )
    biz2 = BusinessInfo(
        place_id="place_2",
        name="City Plumbing Services",
        address="Vasna, Ahmedabad",
        coordinates=LocationCoordinates(latitude=23.0000, longitude=72.5500),
        distance_meters=1850.0,
        average_rating=4.5,
        rating=4.5,
        user_ratings_total=45,
        total_ratings=45,
        business_status="OPERATIONAL",
        phone_number=None,
        website=None,
        google_maps_url="https://www.google.com/maps/place/?q=place_id:place_2",
        types=["plumber"],
    )
    return BusinessDiscoveryResult(
        origin=origin,
        radius_meters=5000,
        purpose="plumbers",
        total_found=2,
        businesses=[biz1, biz2],
    )


def test_format_business_description(sample_discovery_result):
    """Test formatting HTML description block for KML placemarks."""
    biz = sample_discovery_result.businesses[0]
    html_desc = KMLExporter.format_business_description(rank=1, biz=biz)

    assert "<b>Rank:</b> #1" in html_desc
    assert "<b>Name:</b> Apex Plumbers" in html_desc
    assert "⭐ 4.9" in html_desc
    assert "(128 reviews)" in html_desc
    assert "+91 98765 43210" in html_desc
    assert "https://apexplumbers.example.com" in html_desc


def test_create_kml_document(sample_discovery_result):
    """Test constructing XML ElementTree structure for KML."""
    kml_root = KMLExporter.create_kml_document(sample_discovery_result)

    assert kml_root.tag.endswith("kml")
    doc = kml_root.find("{http://www.opengis.net/kml/2.2}Document")
    assert doc is not None

    placemarks = doc.findall("{http://www.opengis.net/kml/2.2}Placemark")
    # 1 Origin placemark + 2 Business placemarks = 3
    assert len(placemarks) == 3

    # Check origin placemark coordinates (longitude,latitude,0)
    origin_coords = placemarks[0].find(".//{http://www.opengis.net/kml/2.2}coordinates").text
    assert origin_coords == "72.563,23.012,0"

    # Check first business placemark coordinates
    biz_coords = placemarks[1].find(".//{http://www.opengis.net/kml/2.2}coordinates").text
    assert biz_coords == "72.564,23.013,0"


def test_generate_default_filename():
    """Test default KML filename generation."""
    fn1 = KMLExporter.generate_default_filename("plumbers", "Paldi, Ahmedabad")
    assert fn1 == "business_discovery_plumbers_paldi.kml"

    fn2 = KMLExporter.generate_default_filename("dentists", "Navrangpura")
    assert fn2 == "business_discovery_dentists_navrangpura.kml"

    fn3 = KMLExporter.generate_default_filename("", "")
    assert fn3 == "business_discovery_results.kml"


def test_export_to_kml_success(tmp_path, sample_discovery_result):
    """Test exporting discovery result to KML file."""
    output_filename = "test_output.kml"
    kml_file_path = KMLExporter.export_to_kml(
        result=sample_discovery_result,
        output_filename=output_filename,
        output_dir=tmp_path,
    )

    assert kml_file_path.exists()
    assert kml_file_path.parent == tmp_path

    # Parse created XML to verify valid format
    tree = ET.parse(kml_file_path)
    root = tree.getroot()
    assert root.tag.endswith("kml")


def test_export_to_kml_invalid_input():
    """Test raise InvalidInputError when result is invalid."""
    with pytest.raises(InvalidInputError, match="valid BusinessDiscoveryResult"):
        KMLExporter.export_to_kml(result="not_a_result_object")


def test_export_to_kml_file_write_error(sample_discovery_result):
    """Test raise KMLFileWriteError when writing file fails."""
    invalid_dir = Path("/non_existent_dir_12345/sub_dir")
    with patch.object(Path, "mkdir", side_effect=PermissionError("Permission denied")):
        with pytest.raises(KMLFileWriteError, match="Failed to write KML file"):
            KMLExporter.export_to_kml(
                result=sample_discovery_result,
                output_filename="output.kml",
                output_dir=invalid_dir,
            )


def test_load_result_from_json(tmp_path, sample_discovery_result):
    """Test loading and validating BusinessDiscoveryResult from JSON for KML export."""
    json_path = tmp_path / "sample_results.json"
    json_path.write_text(sample_discovery_result.model_dump_json(indent=2))

    loaded_result = KMLExporter.load_result_from_json(json_path)
    assert loaded_result.purpose == sample_discovery_result.purpose
    assert loaded_result.total_found == 2


def test_export_kml_cli_from_input_json(tmp_path, sample_discovery_result, monkeypatch):
    """Test export_kml.py CLI script with --input-json option."""
    monkeypatch.chdir(tmp_path)
    json_path = tmp_path / "discovery_input.json"
    json_path.write_text(sample_discovery_result.model_dump_json(indent=2))

    output_kml_name = "from_json_export.kml"
    exit_code = export_kml_main([
        "--input-json", str(json_path),
        "--output", output_kml_name,
    ])

    assert exit_code == 0
    expected_kml_path = tmp_path / output_kml_name
    assert expected_kml_path.exists()


def test_export_kml_cli_live_search(tmp_path, sample_discovery_result, monkeypatch):
    """Test export_kml.py CLI script with live search parameters."""
    monkeypatch.chdir(tmp_path)

    with patch("scripts.export_kml.GoogleMapsService") as mock_service_cls, \
         patch("scripts.export_kml.Config.from_env") as mock_config_func:
        mock_config_func.return_value.api_key = "dummy_key"
        mock_service = mock_service_cls.return_value
        mock_service.search_businesses.return_value = sample_discovery_result

        exit_code = export_kml_main([
            "--area", "Paldi, Ahmedabad, Gujarat, India",
            "--radius", "5000",
            "--purpose", "plumbers",
            "--output", "live_search_results.kml",
        ])

        assert exit_code == 0
        expected_kml_path = tmp_path / "live_search_results.kml"
        assert expected_kml_path.exists()


def test_discover_cli_output_kml_option(tmp_path, sample_discovery_result, monkeypatch):
    """Test discover.py CLI script with --output-kml option."""
    monkeypatch.chdir(tmp_path)

    with patch("scripts.discover.GoogleMapsService") as mock_service_cls, \
         patch("scripts.discover.Config.from_env") as mock_config_func:
        mock_config_func.return_value.api_key = "dummy_key"
        mock_service = mock_service_cls.return_value
        mock_service.search_businesses.return_value = sample_discovery_result

        kml_name = "discover_exported.kml"
        exit_code = discover_main([
            "--area", "Paldi, Ahmedabad, Gujarat, India",
            "--radius", "5000",
            "--purpose", "plumbers",
            "--output-kml", kml_name,
        ])

        assert exit_code == 0
        assert (tmp_path / kml_name).exists()
