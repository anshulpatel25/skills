# Business Discovery Skill

A pythonic, clean architecture AI skill that discovers top businesses matching a specified purpose within a given radius of a location using the Google Maps API.

## Features
- **Top Max 50 Results**: Automatically navigates Places API pagination to collect and return top max 50 businesses.
- **Ratings & Review Counts**: Extracts average ratings (e.g. ⭐ 4.9) and total review counts (e.g. 128 reviews) for every business.
- **Rating-based Ranking**: Ranks businesses primarily by highest average rating, then number of reviews, and distance.
- **Geocoding**: Converts natural language area descriptions (e.g. `"Paldi, Ahmedabad, Gujarat, India"`) into exact coordinates.
- **Distance Calculation**: Computes exact straight-line distance (in meters and km) from search origin for each result.
- **Rich & JSON Output**: Supports formatted CLI tables or clean JSON output for LLM/agent consumption.
- **Dependency Management**: Powered by `uv` with PEP 723 inline script metadata.

## Requirements
- Python 3.10+
- `uv` package manager
- Google Maps API Key with **Geocoding API** and **Places API** enabled.

## Environment Setup
Set `GOOGLE_MAPS_API_KEY` in your environment or in a `.env` file in the project directory:

```bash
export GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
```

## Usage

### Using `uv run`
Execute the discovery script directly with `uv`:

```bash
uv run scripts/discover.py --area "Paldi, Ahmedabad, Gujarat, India" --radius 5000 --purpose "plumbers" --max-results 50
```

### Options
- `--area`: Address or area string (Required)
- `--radius`: Search radius in meters (Required, e.g. `5000`)
- `--purpose`: Business purpose / keyword (Required, e.g. `"plumbers"`, `"cafes"`)
- `--max-results`: Maximum top results to return (Default: `50`, Capped at `50`)
- `--sort-by`: Sorting criteria (`rating` or `distance`, Default: `rating`)
- `--json`: Output raw JSON for programmatic integration
- `--fetch-details`: Fetch additional place details (phone number, website)
