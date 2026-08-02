# /// script
# dependencies = [
#     "googlemaps>=4.10.0",
#     "pydantic>=2.10.0",
#     "pydantic-settings>=2.0.0",
#     "python-dotenv>=1.0.1",
#     "rich>=13.9.0",
# ]
# ///

"""CLI Entry point for Business Discovery Skill using Google Maps API."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Add scripts directory to sys.path for direct script execution
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from .config import Config, ConfigurationError
    from .csv_exporter import CSVExporter, CSVExporterError
    from .maps_service import GoogleMapsService, GoogleMapsServiceError
    from .models import BusinessSearchParams
except ImportError:
    from config import Config, ConfigurationError
    from csv_exporter import CSVExporter, CSVExporterError
    from maps_service import GoogleMapsService, GoogleMapsServiceError
    from models import BusinessSearchParams

console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Discover businesses using Google Maps API based on area, radius, and purpose."
    )
    parser.add_argument(
        "--area",
        type=str,
        required=True,
        help="Target location or area string (e.g., 'Paldi, Ahmedabad, Gujarat, India').",
    )
    parser.add_argument(
        "--radius",
        type=int,
        required=True,
        help="Search radius in meters (e.g., 5000).",
    )
    parser.add_argument(
        "--purpose",
        type=str,
        required=True,
        help="Purpose of business / keyword search (e.g., 'plumbers').",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum top results to return (default 50, capped at 50).",
    )
    parser.add_argument(
        "--sort-by",
        type=str,
        choices=["rating", "distance"],
        default="rating",
        help="Ranking criteria: 'rating' (top rated, default) or 'distance'.",
    )
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help="Fetch additional place details such as phone number and website.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON format for programmatic use.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="Optional CSV filename/path to export results to current working directory.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional explicit Google Maps API Key override.",
    )
    return parser


def display_results_table(result) -> None:
    """Render formatted result summary and table using rich."""
    origin = result.origin
    console.print(
        Panel.fit(
            f"[bold green]Search Center:[/bold green] {origin.formatted_address}\n"
            f"[bold blue]Coordinates:[/bold blue] {origin.coordinates.latitude}, {origin.coordinates.longitude}\n"
            f"[bold yellow]Purpose:[/bold yellow] {result.purpose}\n"
            f"[bold magenta]Radius:[/bold magenta] {result.radius_meters} meters ({result.radius_meters / 1000:.1f} km)\n"
            f"[bold cyan]Top Businesses Displayed:[/bold cyan] {result.total_found}",
            title="🎯 Business Discovery Summary (Ranked by Rating)",
        )
    )

    if not result.businesses:
        console.print("[bold red]No matching businesses found within the specified radius.[/bold red]")
        return

    table = Table(
        title=f"Top {result.total_found} Discovered Businesses ({result.purpose})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Rank", style="bold yellow", width=5, justify="center")
    table.add_column("Business Name", style="bold white", min_width=22)
    table.add_column("Average Rating", style="bold green", justify="center")
    table.add_column("Total Ratings", style="magenta", justify="right")
    table.add_column("Distance", style="cyan", justify="right")
    table.add_column("Address / Vicinity", style="dim white")
    if any(b.phone_number for b in result.businesses):
        table.add_column("Phone", style="blue")

    for idx, biz in enumerate(result.businesses, start=1):
        dist_str = (
            f"{biz.distance_meters:.0f} m" if biz.distance_meters < 1000 else f"{biz.distance_meters / 1000:.2f} km"
        )
        avg_rating_str = f"⭐ {biz.average_rating:.1f}" if biz.average_rating is not None else "N/A"
        ratings_count_str = f"{biz.user_ratings_total:,}" if biz.user_ratings_total is not None else "N/A"

        row_data = [str(idx), biz.name, avg_rating_str, ratings_count_str, dist_str, biz.address]
        if any(b.phone_number for b in result.businesses):
            row_data.append(biz.phone_number or "N/A")

        table.add_row(*row_data)

    console.print(table)


def main(args_list: Optional[list[str]] = None) -> int:
    """Main CLI execution flow."""
    parser = create_parser()
    args = parser.parse_args(args_list)

    try:
        config = Config.from_env(explicit_key=args.api_key)
        service = GoogleMapsService(api_key=config.api_key)

        params = BusinessSearchParams(
            area=args.area,
            radius_meters=args.radius,
            purpose=args.purpose,
            max_results=min(args.max_results, 50),
            sort_by=args.sort_by,
            fetch_details=args.fetch_details,
        )

        result = service.search_businesses(params)

        if args.output_csv:
            csv_path = CSVExporter.export_to_csv(result, output_filename=args.output_csv, output_dir=Path.cwd())
            if not args.json:
                console.print(f"[bold green]✓ CSV file exported to:[/bold green] {csv_path}")

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            display_results_table(result)

        return 0

    except ConfigurationError as err:
        if args.json:
            console.print_json(data={"error": "ConfigurationError", "message": str(err)})
        else:
            console.print(f"[bold red]Configuration Error:[/bold red] {err}")
        return 1

    except GoogleMapsServiceError as err:
        if args.json:
            console.print_json(data={"error": type(err).__name__, "message": str(err)})
        else:
            console.print(f"[bold red]API Service Error:[/bold red] {err}")
        return 1

    except Exception as err:
        if args.json:
            console.print_json(data={"error": "UnexpectedError", "message": str(err)})
        else:
            console.print(f"[bold red]Unexpected Error:[/bold red] {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
