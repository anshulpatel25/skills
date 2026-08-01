"""Google Maps API service layer for Geocoding and Places API integration."""

import math
import time
from typing import List, Optional
import googlemaps
from googlemaps.exceptions import ApiError, HTTPError, Timeout

try:
    from .models import (
        BusinessDiscoveryResult,
        BusinessInfo,
        BusinessSearchParams,
        LocationCoordinates,
        LocationOrigin,
    )
except ImportError:
    from models import (
        BusinessDiscoveryResult,
        BusinessInfo,
        BusinessSearchParams,
        LocationCoordinates,
        LocationOrigin,
    )


class GoogleMapsServiceError(Exception):
    """Base exception for Google Maps service layer errors."""

    pass


class GeocodingError(GoogleMapsServiceError):
    """Raised when geocoding a location fails."""

    pass


class PlacesSearchError(GoogleMapsServiceError):
    """Raised when querying Places API fails."""

    pass


class GoogleMapsService:
    """Clean architecture service layer wrapping Google Maps SDK operations."""

    def __init__(
        self,
        api_key: str,
        client: Optional[googlemaps.Client] = None,
        page_delay_seconds: float = 2.0,
    ) -> None:
        """Initialize service with Google Maps API key or injected client instance.

        Args:
            api_key: Google Maps API key.
            client: Optional googlemaps.Client instance for dependency injection.
            page_delay_seconds: Delay in seconds between paginated requests (Google API requirement).
        """
        self.client = client or googlemaps.Client(key=api_key)
        self.page_delay_seconds = page_delay_seconds

    @staticmethod
    def calculate_distance_meters(coord1: LocationCoordinates, coord2: LocationCoordinates) -> float:
        """Calculate Haversine distance between two latitude/longitude coordinates in meters.

        Args:
            coord1: Starting coordinate (origin).
            coord2: Destination coordinate (target).

        Returns:
            Distance in meters rounded to 2 decimal places.
        """
        earth_radius_meters = 6371000.0
        lat1, lon1 = math.radians(coord1.latitude), math.radians(coord1.longitude)
        lat2, lon2 = math.radians(coord2.latitude), math.radians(coord2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        return round(earth_radius_meters * c, 2)

    def geocode_address(self, address: str) -> LocationOrigin:
        """Geocode an area string into latitude and longitude coordinates.

        Args:
            address: Human-readable location or area (e.g. 'Paldi, Ahmedabad, Gujarat, India').

        Returns:
            LocationOrigin object containing coordinates and formatted address.

        Raises:
            GeocodingError: If geocoding fails or no results are returned.
        """
        try:
            results = self.client.geocode(address)
            if not results:
                raise GeocodingError(f"No geocoding location found for: '{address}'")

            first_result = results[0]
            geometry = first_result.get("geometry", {})
            location = geometry.get("location", {})

            if "lat" not in location or "lng" not in location:
                raise GeocodingError(f"Invalid geometry returned for address: '{address}'")

            formatted_address = first_result.get("formatted_address", address)
            coordinates = LocationCoordinates(latitude=location["lat"], longitude=location["lng"])

            return LocationOrigin(
                query_address=address,
                formatted_address=formatted_address,
                coordinates=coordinates,
            )

        except (ApiError, HTTPError, Timeout) as err:
            raise GeocodingError(f"Google Geocoding API request failed: {err}") from err
        except Exception as err:
            if isinstance(err, GeocodingError):
                raise
            raise GeocodingError(f"Unexpected error during geocoding: {err}") from err

    def search_businesses(self, params: BusinessSearchParams) -> BusinessDiscoveryResult:
        """Discover top matching businesses within radius, sorted by rating or distance.

        Fetches up to params.max_results across paginated responses, extracts average rating
        and rating counts, and ranks the results accordingly.

        Args:
            params: BusinessSearchParams object containing search inputs and preferences.

        Returns:
            BusinessDiscoveryResult containing top businesses ranked by rating.

        Raises:
            GeocodingError: If target area cannot be geocoded.
            PlacesSearchError: If Places API request fails.
        """
        origin = self.geocode_address(params.area)

        try:
            location_tuple = (origin.coordinates.latitude, origin.coordinates.longitude)
            raw_places: List[dict] = []
            page_token: Optional[str] = None

            while len(raw_places) < params.max_results:
                kwargs = {
                    "location": location_tuple,
                    "radius": params.radius_meters,
                    "keyword": params.purpose,
                }
                if page_token:
                    kwargs["page_token"] = page_token

                response = self.client.places_nearby(**kwargs)
                results_batch = response.get("results", [])
                raw_places.extend(results_batch)

                page_token = response.get("next_page_token")
                if not page_token or len(raw_places) >= params.max_results:
                    break

                if self.page_delay_seconds > 0:
                    time.sleep(self.page_delay_seconds)

            businesses: List[BusinessInfo] = []

            for place in raw_places:
                place_loc = place.get("geometry", {}).get("location", {})
                if not place_loc or "lat" not in place_loc or "lng" not in place_loc:
                    continue

                business_coords = LocationCoordinates(
                    latitude=place_loc["lat"],
                    longitude=place_loc["lng"],
                )

                dist = self.calculate_distance_meters(origin.coordinates, business_coords)
                place_id = place.get("place_id", "")
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

                phone: Optional[str] = None
                website: Optional[str] = None

                if params.fetch_details and place_id:
                    try:
                        details = self.client.place(
                            place_id=place_id,
                            fields=["formatted_phone_number", "website"],
                        ).get("result", {})
                        phone = details.get("formatted_phone_number")
                        website = details.get("website")
                    except Exception:
                        pass

                avg_rating = place.get("rating")
                num_ratings = place.get("user_ratings_total")

                business = BusinessInfo(
                    place_id=place_id,
                    name=place.get("name", "Unknown Business"),
                    address=place.get("vicinity") or place.get("formatted_address") or "N/A",
                    coordinates=business_coords,
                    distance_meters=dist,
                    average_rating=avg_rating,
                    rating=avg_rating,
                    user_ratings_total=num_ratings,
                    total_ratings=num_ratings,
                    business_status=place.get("business_status"),
                    phone_number=phone,
                    website=website,
                    google_maps_url=maps_url,
                    types=place.get("types", []),
                )
                businesses.append(business)

            # Deduplicate by place_id if any duplicate returned across pages
            seen_place_ids = set()
            unique_businesses: List[BusinessInfo] = []
            for b in businesses:
                if b.place_id not in seen_place_ids:
                    seen_place_ids.add(b.place_id)
                    unique_businesses.append(b)

            # Sort businesses
            if params.sort_by == "rating":
                # Primary: Average rating (desc), Secondary: Number of ratings (desc), Tertiary: Distance (asc)
                unique_businesses.sort(
                    key=lambda b: (
                        b.average_rating if b.average_rating is not None else -1.0,
                        b.user_ratings_total if b.user_ratings_total is not None else -1,
                        -b.distance_meters,
                    ),
                    reverse=True,
                )
            else:
                # Sort strictly by distance ascending
                unique_businesses.sort(key=lambda b: b.distance_meters)

            # Cap at max_results
            top_businesses = unique_businesses[: params.max_results]

            return BusinessDiscoveryResult(
                origin=origin,
                radius_meters=params.radius_meters,
                purpose=params.purpose,
                total_found=len(top_businesses),
                businesses=top_businesses,
            )

        except (ApiError, HTTPError, Timeout) as err:
            raise PlacesSearchError(f"Google Places API request failed: {err}") from err
        except Exception as err:
            if isinstance(err, PlacesSearchError):
                raise
            raise PlacesSearchError(f"Unexpected error during places search: {err}") from err
