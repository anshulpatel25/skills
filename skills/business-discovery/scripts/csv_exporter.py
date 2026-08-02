"""CSV Exporter module for Business Discovery skill.

Provides domain-level exporting capabilities to transform BusinessDiscoveryResult
data models into formatted CSV files in the current working directory.
Follows Clean Architecture, SOLID, and CUPID principles with comprehensive error handling.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from .models import BusinessDiscoveryResult, BusinessInfo
except ImportError:
    from models import BusinessDiscoveryResult, BusinessInfo

logger = logging.getLogger(__name__)


class CSVExporterError(Exception):
    """Base exception class for CSV exporter errors."""

    pass


class CSVFileWriteError(CSVExporterError):
    """Raised when writing the CSV output file fails due to I/O or permission errors."""

    pass


class InvalidInputError(CSVExporterError):
    """Raised when input data or JSON structure for CSV generation is invalid."""

    pass


class CSVExporter:
    """Service class responsible for exporting Business Discovery results to CSV format.

    Adheres to Single Responsibility Principle (SRP) by handling only CSV data
    formatting, transformation, and file persistence.
    """

    # Field mapping defining CSV column order, headers, and model keys
    CSV_FIELDS: List[Dict[str, str]] = [
        {"header": "Rank", "key": "rank"},
        {"header": "Name", "key": "name"},
        {"header": "Average Rating", "key": "average_rating"},
        {"header": "Total Ratings", "key": "user_ratings_total"},
        {"header": "Distance (meters)", "key": "distance_meters"},
        {"header": "Distance (km)", "key": "distance_km"},
        {"header": "Address", "key": "address"},
        {"header": "Business Status", "key": "business_status"},
        {"header": "Phone Number", "key": "phone_number"},
        {"header": "Website", "key": "website"},
        {"header": "Google Maps URL", "key": "google_maps_url"},
        {"header": "Categories", "key": "types"},
        {"header": "Latitude", "key": "latitude"},
        {"header": "Longitude", "key": "longitude"},
        {"header": "Place ID", "key": "place_id"},
    ]

    @classmethod
    def format_business_row(cls, rank: int, biz: BusinessInfo) -> Dict[str, Any]:
        """Transform a BusinessInfo domain object into a flat dictionary row for CSV output.

        Args:
            rank: 1-indexed rank order position of the business.
            biz: BusinessInfo instance.

        Returns:
            Flat dictionary mapping CSV header strings to formatted row values.
        """
        # Calculate distance in kilometers for user convenience
        distance_km = round(biz.distance_meters / 1000.0, 2) if biz.distance_meters is not None else ""

        # Join place types/categories into comma-separated string
        categories_str = ", ".join(biz.types) if biz.types else ""

        # Extract coordinates safely
        lat = biz.coordinates.latitude if biz.coordinates else ""
        lng = biz.coordinates.longitude if biz.coordinates else ""

        return {
            "Rank": rank,
            "Name": biz.name or "",
            "Average Rating": biz.average_rating if biz.average_rating is not None else "",
            "Total Ratings": biz.user_ratings_total if biz.user_ratings_total is not None else "",
            "Distance (meters)": biz.distance_meters if biz.distance_meters is not None else "",
            "Distance (km)": distance_km,
            "Address": biz.address or "",
            "Business Status": biz.business_status or "",
            "Phone Number": biz.phone_number or "",
            "Website": biz.website or "",
            "Google Maps URL": biz.google_maps_url or "",
            "Categories": categories_str,
            "Latitude": lat,
            "Longitude": lng,
            "Place ID": biz.place_id or "",
        }

    @classmethod
    def export_to_csv(
        cls,
        result: BusinessDiscoveryResult,
        output_filename: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Export a BusinessDiscoveryResult instance to a CSV file.

        The file is saved in the specified output directory or defaults to the
        current working directory (Path.cwd()).

        Args:
            result: BusinessDiscoveryResult model containing business listings.
            output_filename: Optional filename or relative path for output.
            output_dir: Optional directory target. Defaults to current working directory.

        Returns:
            Path object pointing to the generated CSV file.

        Raises:
            InvalidInputError: If result is not a valid BusinessDiscoveryResult.
            CSVFileWriteError: If file writing or directory creation fails.
        """
        if not isinstance(result, BusinessDiscoveryResult):
            raise InvalidInputError("Provided data must be a valid BusinessDiscoveryResult instance.")

        # Determine target directory (defaulting to Current Working Directory)
        base_dir = Path(output_dir).resolve() if output_dir else Path.cwd()

        # Determine target file path
        if output_filename:
            file_path = Path(output_filename)
            if not file_path.is_absolute():
                file_path = base_dir / file_path
        else:
            file_path = base_dir / cls.generate_default_filename(result.purpose, result.origin.query_address)

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            headers = [field["header"] for field in cls.CSV_FIELDS]

            with open(file_path, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=headers)
                writer.writeheader()

                for rank, biz in enumerate(result.businesses, start=1):
                    row = cls.format_business_row(rank, biz)
                    writer.writerow(row)

            logger.info("Successfully wrote CSV file with %d records to %s", len(result.businesses), file_path)
            return file_path

        except Exception as err:
            raise CSVFileWriteError(f"Failed to write CSV file to '{file_path}': {err}") from err

    @staticmethod
    def generate_default_filename(purpose: str, area: str) -> str:
        """Generate a clean, descriptive default CSV filename based on search purpose and area.

        Args:
            purpose: Search keyword/purpose (e.g., 'plumbers').
            area: Location query string (e.g., 'Paldi, Ahmedabad').

        Returns:
            Sanitized CSV filename string.
        """
        # Sanitize purpose and area to valid filename characters
        clean_purpose = "".join(c if c.isalnum() else "_" for c in purpose.strip().lower())
        area_first_part = area.split(",")[0].strip().lower() if area else ""
        clean_area = "".join(c if c.isalnum() else "_" for c in area_first_part)

        # Remove duplicate underscores
        norm_purpose = "_".join(filter(None, clean_purpose.split("_")))
        norm_area = "_".join(filter(None, clean_area.split("_")))

        if norm_purpose and norm_area:
            return f"business_discovery_{norm_purpose}_{norm_area}.csv"
        elif norm_purpose:
            return f"business_discovery_{norm_purpose}.csv"
        return "business_discovery_results.csv"

    @classmethod
    def load_result_from_json(cls, json_path: Union[str, Path]) -> BusinessDiscoveryResult:
        """Load and validate a BusinessDiscoveryResult model from a JSON file.

        Args:
            json_path: Path to JSON input file.

        Returns:
            Validated BusinessDiscoveryResult model.

        Raises:
            InvalidInputError: If file is missing, unreadable, or violates model schema.
        """
        path = Path(json_path)
        if not path.is_file():
            raise InvalidInputError(f"JSON input file not found: '{path}'")

        try:
            with open(path, mode="r", encoding="utf-8") as f:
                data = json.load(f)
            return BusinessDiscoveryResult.model_validate(data)
        except Exception as err:
            raise InvalidInputError(f"Failed to parse discovery result from JSON file '{path}': {err}") from err
