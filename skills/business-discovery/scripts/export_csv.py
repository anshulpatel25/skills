# /// script
# dependencies = [
#     "googlemaps>=4.10.0",
#     "pydantic>=2.10.0",
#     "pydantic-settings>=2.0.0",
#     "python-dotenv>=1.0.1",
#     "rich>=13.9.0",
# ]
# ///

"""CLI script to generate CSV files from Business Discovery results.

Exports business discovery search results into a CSV file in the current working directory.
Results can be generated via a live Google Maps API search or converted from an existing
JSON discovery output file.

Examples:
    1. Live Search & CSV Export:
       uv run skills/business-discovery/scripts/export_csv.py \\
           --area "Paldi, Ahmedabad, Gujarat, India" \\
           --radius 5000 \\
           --purpose "plumbers" \\
           --output "plumbers_paldi.csv"

    2. Convert Existing JSON Result to CSV:
       uv run skills/business-discovery/scripts/export_csv.py \\
           --input-json "results.json" \\
           --output "businesses.csv"
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add scripts directory to sys.path for direct script execution
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from rich.console import Console

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
    """Construct CLI argument parser for CSV export tool."""
    parser = argparse.ArgumentParser(
        description="Generate CSV files from Business Discovery results and save to the current working directory."
    )

    # Input mode options
    input_group = parser.add_argument_group("Input Data Options")
    input_group.add_argument(
        "--input-json",
        type=str,
        default=None,
        help="Path to an existing JSON result file produced by discover.py (bypasses live API search).",
    )
    input_group.add_argument(
        "--area",
        type=str,
        default=None,
        help="Target location or area string (e.g., 'Paldi, Ahmedabad, Gujarat, India'). Required if --input-json is not provided.",
    )
    input_group.add_argument(
        "--radius",
        type=int,
        default=None,
        help="Search radius in meters (e.g., 5000). Required if --input-json is not provided.",
    )
    input_group.add_argument(
        "--purpose",
        type=str,
        default=None,
        help="Purpose of business / keyword search (e.g., 'plumbers'). Required if --input-json is not provided.",
    )

    # Search options
    search_group = parser.add_argument_group("Search Refinement Options")
    search_group.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum top results to return (default 50, capped at 50).",
    )
    search_group.add_argument(
        "--sort-by",
        type=str,
        choices=["rating", "distance"],
        default="rating",
        help="Ranking criteria: 'rating' (top rated, default) or 'distance'.",
    )
    search_group.add_argument(
        "--fetch-details",
        action="store_true",
        help="Fetch additional place details such as phone number and website.",
    )
    search_group.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional explicit Google Maps API Key override.",
    )

    # Output options
    output_group = parser.add_argument_group("Output File Options")
    output_group.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output CSV filename or path (saved in the current working directory by default).",
    )

    return parser


def main(args_list: Optional[list[str]] = None) -> int:
    """Main CLI execution entry point for CSV exporter.

    Args:
        args_list: Optional argument string list (used for unit testing).

    Returns:
        Exit code: 0 for success, 1 for errors.
    """
    parser = create_parser()
    args = parser.parse_args(args_list)

    try:
        if args.input_json:
            # Case A: Load discovery result from pre-existing JSON file
            console.print(f"[bold blue]📄 Loading discovery results from JSON file:[/bold blue] {args.input_json}")
            result = CSVExporter.load_result_from_json(args.input_json)
        else:
            # Case B: Perform live Google Maps API search
            if not args.area or not args.radius or not args.purpose:
                parser.error(
                    "When --input-json is not specified, --area, --radius, and --purpose are required."
                )

            console.print(
                f"[bold cyan]🔍 Executing Business Discovery search...[/bold cyan]\n"
                f"  • [yellow]Area:[/yellow] {args.area}\n"
                f"  • [yellow]Radius:[/yellow] {args.radius} meters\n"
                f"  • [yellow]Purpose:[/yellow] {args.purpose}"
            )

            # Load configuration and initialize Google Maps service
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

        # Export discovery result to CSV in the current working directory
        cwd = Path.cwd()
        csv_path = CSVExporter.export_to_csv(
            result=result,
            output_filename=args.output,
            output_dir=cwd,
        )

        console.print(
            f"\n[bold green]✓ CSV output generated successfully![/bold green]\n"
            f"  • [bold white]Businesses Exported:[/bold white] [cyan]{len(result.businesses)}[/cyan]\n"
            f"  • [bold white]CSV File Location:[/bold white] [green]{csv_path}[/green]"
        )
        return 0

    except ConfigurationError as err:
        console.print(f"[bold red]Configuration Error:[/bold red] {err}")
        return 1
    except GoogleMapsServiceError as err:
        console.print(f"[bold red]API Service Error:[/bold red] {err}")
        return 1
    except CSVExporterError as err:
        console.print(f"[bold red]CSV Exporter Error:[/bold red] {err}")
        return 1
    except SystemExit as err:
        return err.code if isinstance(err.code, int) else 1
    except Exception as err:
        console.print(f"[bold red]Unexpected Error:[/bold red] {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
