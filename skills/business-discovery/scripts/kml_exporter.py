"""KML Exporter module for Business Discovery skill.

Provides domain-level exporting capabilities to transform BusinessDiscoveryResult
data models into KML (Keyhole Markup Language) files in the current working directory.
Follows Clean Architecture, SOLID, and CUPID principles with comprehensive error handling.
"""

import json
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import Optional, Union

try:
    from .models import BusinessDiscoveryResult, BusinessInfo
except ImportError:
    from models import BusinessDiscoveryResult, BusinessInfo

logger = logging.getLogger(__name__)


class KMLExporterError(Exception):
    """Base exception class for KML exporter errors."""

    pass


class KMLFileWriteError(KMLExporterError):
    """Raised when writing the KML output file fails due to I/O or permission errors."""

    pass


class InvalidInputError(KMLExporterError):
    """Raised when input data or JSON structure for KML generation is invalid."""

    pass


class KMLExporter:
    """Service class responsible for exporting Business Discovery results to KML format.

    Adheres to Single Responsibility Principle (SRP) by handling only KML XML structure
    formatting and file persistence.
    """

    KML_NAMESPACE = "http://www.opengis.net/kml/2.2"

    @classmethod
    def format_business_description(cls, rank: int, biz: BusinessInfo) -> str:
        """Format business details into a clean HTML description block for KML placemarks.

        Args:
            rank: 1-indexed rank position of the business.
            biz: BusinessInfo instance.

        Returns:
            HTML string suitable for insertion inside KML description tags.
        """
        lines = [
            f"<b>Rank:</b> #{rank}",
            f"<b>Name:</b> {biz.name}",
            f"<b>Address:</b> {biz.address}",
        ]

        if biz.average_rating is not None:
            total_str = f" ({biz.user_ratings_total:,} reviews)" if biz.user_ratings_total else ""
            lines.append(f"<b>Rating:</b> ⭐ {biz.average_rating:.1f}{total_str}")

        if biz.distance_meters is not None:
            dist_str = f"{biz.distance_meters:.0f} m" if biz.distance_meters < 1000 else f"{biz.distance_meters / 1000:.2f} km"
            lines.append(f"<b>Distance:</b> {dist_str}")

        if biz.business_status:
            lines.append(f"<b>Status:</b> {biz.business_status}")

        if biz.phone_number:
            lines.append(f"<b>Phone:</b> {biz.phone_number}")

        if biz.website:
            lines.append(f'<b>Website:</b> <a href="{biz.website}">{biz.website}</a>')

        if biz.google_maps_url:
            lines.append(f'<b>Google Maps:</b> <a href="{biz.google_maps_url}">View on Google Maps</a>')

        if biz.types:
            lines.append(f"<b>Categories:</b> {', '.join(biz.types)}")

        return "<br/>\n".join(lines)

    @classmethod
    def _ns(cls, tag: str) -> str:
        """Helper to qualify tag with KML XML namespace."""
        return f"{{{cls.KML_NAMESPACE}}}{tag}"

    @classmethod
    def create_kml_document(cls, result: BusinessDiscoveryResult) -> ET.Element:
        """Construct the ElementTree XML structure for a complete KML document.

        Args:
            result: BusinessDiscoveryResult domain model instance.

        Returns:
            ET.Element root node representing the KML document.
        """
        # Register default namespace prefix to avoid ns0: prefixes
        ET.register_namespace("", cls.KML_NAMESPACE)

        kml = ET.Element(cls._ns("kml"))
        doc = ET.SubElement(kml, cls._ns("Document"))

        # Document Header metadata
        doc_name = ET.SubElement(doc, cls._ns("name"))
        doc_name.text = f"Business Discovery - {result.purpose.title()} ({result.origin.query_address})"

        doc_desc = ET.SubElement(doc, cls._ns("description"))
        doc_desc.text = (
            f"Top {result.total_found} discovered businesses matching '{result.purpose}' "
            f"within {result.radius_meters} meters of {result.origin.formatted_address}."
        )

        # Add Origin Placemark
        origin_pm = ET.SubElement(doc, cls._ns("Placemark"))
        origin_name = ET.SubElement(origin_pm, cls._ns("name"))
        origin_name.text = f"📍 Search Origin: {result.origin.query_address}"
        origin_desc = ET.SubElement(origin_pm, cls._ns("description"))
        origin_desc.text = f"Formatted Address: {result.origin.formatted_address}"

        origin_point = ET.SubElement(origin_pm, cls._ns("Point"))
        origin_coords = ET.SubElement(origin_point, cls._ns("coordinates"))
        # KML coordinates format: longitude,latitude,altitude
        origin_coords.text = f"{result.origin.coordinates.longitude},{result.origin.coordinates.latitude},0"

        # Add Business Placemarks
        for rank, biz in enumerate(result.businesses, start=1):
            pm = ET.SubElement(doc, cls._ns("Placemark"))

            name_elem = ET.SubElement(pm, cls._ns("name"))
            rating_suffix = f" (⭐ {biz.average_rating:.1f})" if biz.average_rating is not None else ""
            name_elem.text = f"{rank}. {biz.name}{rating_suffix}"

            desc_elem = ET.SubElement(pm, cls._ns("description"))
            desc_elem.text = cls.format_business_description(rank, biz)

            point_elem = ET.SubElement(pm, cls._ns("Point"))
            coords_elem = ET.SubElement(point_elem, cls._ns("coordinates"))
            # KML standard requires longitude,latitude,altitude
            coords_elem.text = f"{biz.coordinates.longitude},{biz.coordinates.latitude},0"

        return kml

    @classmethod
    def export_to_kml(
        cls,
        result: BusinessDiscoveryResult,
        output_filename: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Export a BusinessDiscoveryResult instance to a formatted KML file.

        The file is stored in the specified directory or defaults to the
        current working directory (Path.cwd()).

        Args:
            result: BusinessDiscoveryResult model containing business listings.
            output_filename: Optional filename or path for the KML file.
            output_dir: Optional directory path. Defaults to current working directory.

        Returns:
            Path object pointing to the generated KML file.

        Raises:
            InvalidInputError: If result is not a valid BusinessDiscoveryResult.
            KMLFileWriteError: If file writing or directory creation fails.
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
            # Ensure target directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            kml_root = cls.create_kml_document(result)

            # Generate pretty-printed XML for readability
            raw_xml = ET.tostring(kml_root, encoding="utf-8")
            reparsed = minidom.parseString(raw_xml)
            pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8")

            with open(file_path, mode="wb") as kml_file:
                kml_file.write(pretty_xml)

            logger.info("Successfully wrote KML file with %d placemarks to %s", len(result.businesses), file_path)
            return file_path

        except Exception as err:
            raise KMLFileWriteError(f"Failed to write KML file to '{file_path}': {err}") from err

    @staticmethod
    def generate_default_filename(purpose: str, area: str) -> str:
        """Generate a clean, descriptive default KML filename based on search purpose and area.

        Args:
            purpose: Search keyword/purpose (e.g., 'plumbers').
            area: Location query string (e.g., 'Paldi, Ahmedabad').

        Returns:
            Sanitized KML filename string.
        """
        clean_purpose = "".join(c if c.isalnum() else "_" for c in purpose.strip().lower())
        area_first_part = area.split(",")[0].strip().lower() if area else ""
        clean_area = "".join(c if c.isalnum() else "_" for c in area_first_part)

        norm_purpose = "_".join(filter(None, clean_purpose.split("_")))
        norm_area = "_".join(filter(None, clean_area.split("_")))

        if norm_purpose and norm_area:
            return f"business_discovery_{norm_purpose}_{norm_area}.kml"
        elif norm_purpose:
            return f"business_discovery_{norm_purpose}.kml"
        return "business_discovery_results.kml"

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
