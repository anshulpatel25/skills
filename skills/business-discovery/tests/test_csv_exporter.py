"""Unit tests for CSV Exporter and export_csv.py script."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.csv_exporter import (
    CSVExporter,
    CSVExporterError,
    CSVFileWriteError,
    InvalidInputError,
)
from scripts.export_csv import main as export_csv_main
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


def test_format_business_row(sample_discovery_result):
    """Test formatting a BusinessInfo object into a CSV row dictionary."""
    biz = sample_discovery_result.businesses[0]
    row = CSVExporter.format_business_row(rank=1, biz=biz)

    assert row["Rank"] == 1
    assert row["Name"] == "Apex Plumbers"
    assert row["Average Rating"] == 4.9
    assert row["Total Ratings"] == 128
    assert row["Distance (meters)"] == 150.0
    assert row["Distance (km)"] == 0.15
    assert row["Address"] == "Paldi Cross Rd, Ahmedabad"
    assert row["Business Status"] == "OPERATIONAL"
    assert row["Phone Number"] == "+91 98765 43210"
    assert row["Website"] == "https://apexplumbers.example.com"
    assert row["Categories"] == "plumber, point_of_interest"
    assert row["Latitude"] == 23.0130
    assert row["Longitude"] == 72.5640
    assert row["Place ID"] == "place_1"


def test_generate_default_filename():
    """Test default CSV filename generation."""
    fn1 = CSVExporter.generate_default_filename("plumbers", "Paldi, Ahmedabad")
    assert fn1 == "business_discovery_plumbers_paldi.csv"

    fn2 = CSVExporter.generate_default_filename("dentists", "Navrangpura")
    assert fn2 == "business_discovery_dentists_navrangpura.csv"

    fn3 = CSVExporter.generate_default_filename("", "")
    assert fn3 == "business_discovery_results.csv"


def test_export_to_csv_success(tmp_path, sample_discovery_result):
    """Test exporting discovery result to CSV in specified output directory."""
    output_filename = "test_output.csv"
    csv_file_path = CSVExporter.export_to_csv(
        result=sample_discovery_result,
        output_filename=output_filename,
        output_dir=tmp_path,
    )

    assert csv_file_path.exists()
    assert csv_file_path.parent == tmp_path

    # Verify CSV file contents
    with open(csv_file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["Name"] == "Apex Plumbers"
    assert rows[0]["Average Rating"] == "4.9"
    assert rows[0]["Total Ratings"] == "128"
    assert rows[0]["Distance (km)"] == "0.15"

    assert rows[1]["Name"] == "City Plumbing Services"
    assert rows[1]["Phone Number"] == ""


def test_export_to_csv_invalid_input():
    """Test raise InvalidInputError when result is not a BusinessDiscoveryResult."""
    with pytest.raises(InvalidInputError, match="valid BusinessDiscoveryResult"):
        CSVExporter.export_to_csv(result="not_a_result_object")


def test_export_to_csv_file_write_error(sample_discovery_result):
    """Test raise CSVFileWriteError when writing CSV fails."""
    invalid_dir = Path("/non_existent_dir_12345/sub_dir")
    with patch.object(Path, "mkdir", side_effect=PermissionError("Permission denied")):
        with pytest.raises(CSVFileWriteError, match="Failed to write CSV file"):
            CSVExporter.export_to_csv(
                result=sample_discovery_result,
                output_filename="output.csv",
                output_dir=invalid_dir,
            )


def test_load_result_from_json(tmp_path, sample_discovery_result):
    """Test loading and validating BusinessDiscoveryResult from JSON file."""
    json_path = tmp_path / "sample_results.json"
    with open(json_path, mode="w", encoding="utf-8") as f:
        f.write(sample_discovery_result.model_dump_json(indent=2))

    loaded_result = CSVExporter.load_result_from_json(json_path)
    assert loaded_result.purpose == sample_discovery_result.purpose
    assert loaded_result.total_found == 2
    assert loaded_result.businesses[0].name == "Apex Plumbers"


def test_load_result_from_json_invalid_file(tmp_path):
    """Test raise InvalidInputError for non-existent or invalid JSON file."""
    non_existent = tmp_path / "missing.json"
    with pytest.raises(InvalidInputError, match="JSON input file not found"):
        CSVExporter.load_result_from_json(non_existent)

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("invalid json content")
    with pytest.raises(InvalidInputError, match="Failed to parse discovery result"):
        CSVExporter.load_result_from_json(corrupt_json)


def test_export_csv_cli_from_input_json(tmp_path, sample_discovery_result, monkeypatch):
    """Test export_csv.py CLI script with --input-json option."""
    monkeypatch.chdir(tmp_path)
    json_path = tmp_path / "discovery_input.json"
    json_path.write_text(sample_discovery_result.model_dump_json(indent=2))

    output_csv_name = "from_json_export.csv"
    exit_code = export_csv_main([
        "--input-json", str(json_path),
        "--output", output_csv_name,
    ])

    assert exit_code == 0
    expected_csv_path = tmp_path / output_csv_name
    assert expected_csv_path.exists()


def test_export_csv_cli_live_search(tmp_path, sample_discovery_result, monkeypatch):
    """Test export_csv.py CLI script with live search arguments."""
    monkeypatch.chdir(tmp_path)

    with patch("scripts.export_csv.GoogleMapsService") as mock_service_cls, \
         patch("scripts.export_csv.Config.from_env") as mock_config_func:
        mock_config_func.return_value.api_key = "dummy_key"
        mock_service = mock_service_cls.return_value
        mock_service.search_businesses.return_value = sample_discovery_result

        exit_code = export_csv_main([
            "--area", "Paldi, Ahmedabad, Gujarat, India",
            "--radius", "5000",
            "--purpose", "plumbers",
            "--output", "live_search_results.csv",
        ])

        assert exit_code == 0
        expected_csv_path = tmp_path / "live_search_results.csv"
        assert expected_csv_path.exists()


def test_discover_cli_output_csv_option(tmp_path, sample_discovery_result, monkeypatch):
    """Test discover.py CLI script with --output-csv option."""
    monkeypatch.chdir(tmp_path)

    with patch("scripts.discover.GoogleMapsService") as mock_service_cls, \
         patch("scripts.discover.Config.from_env") as mock_config_func:
        mock_config_func.return_value.api_key = "dummy_key"
        mock_service = mock_service_cls.return_value
        mock_service.search_businesses.return_value = sample_discovery_result

        csv_name = "discover_exported.csv"
        exit_code = discover_main([
            "--area", "Paldi, Ahmedabad, Gujarat, India",
            "--radius", "5000",
            "--purpose", "plumbers",
            "--output-csv", csv_name,
        ])

        assert exit_code == 0
        assert (tmp_path / csv_name).exists()
