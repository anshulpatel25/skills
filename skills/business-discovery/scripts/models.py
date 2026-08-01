"""Domain models for Business Discovery skill."""

from typing import List, Optional
from pydantic import BaseModel, Field


class LocationCoordinates(BaseModel):
    """Geographic coordinates (latitude, longitude)."""

    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")


class LocationOrigin(BaseModel):
    """Origin location resolved from geocoding."""

    query_address: str = Field(..., description="Original requested area query")
    formatted_address: str = Field(..., description="Formatted address from Google Maps API")
    coordinates: LocationCoordinates = Field(..., description="Resolved lat/lng coordinates")


class BusinessSearchParams(BaseModel):
    """Search request parameters."""

    area: str = Field(..., min_length=1, description="Target area or location description")
    radius_meters: int = Field(..., gt=0, le=50000, description="Search radius in meters (max 50,000)")
    purpose: str = Field(..., min_length=1, description="Business purpose, service, or keyword")
    max_results: int = Field(default=50, ge=1, le=60, description="Maximum results to return (default 50, max 50)")
    sort_by: str = Field(default="rating", description="Sorting criteria: 'rating' (default) or 'distance'")
    fetch_details: bool = Field(default=False, description="Fetch additional place details (phone, website)")


class BusinessInfo(BaseModel):
    """Individual business entity details."""

    place_id: str = Field(..., description="Unique Google Place ID")
    name: str = Field(..., description="Business name")
    address: str = Field(..., description="Business vicinity or address")
    coordinates: LocationCoordinates = Field(..., description="Business location coordinates")
    distance_meters: float = Field(..., ge=0, description="Straight-line distance from origin in meters")
    average_rating: Optional[float] = Field(default=None, description="Average user rating score out of 5.0")
    rating: Optional[float] = Field(default=None, description="Average user rating score (alias)")
    user_ratings_total: Optional[int] = Field(default=None, description="Total number of ratings / reviews")
    total_ratings: Optional[int] = Field(default=None, description="Total number of ratings / reviews (alias)")
    business_status: Optional[str] = Field(default=None, description="Status (e.g. OPERATIONAL)")
    phone_number: Optional[str] = Field(default=None, description="Formatted phone number if fetched")
    website: Optional[str] = Field(default=None, description="Official website URL if fetched")
    google_maps_url: Optional[str] = Field(default=None, description="Direct Google Maps URL")
    types: List[str] = Field(default_factory=list, description="Google Maps place types")


class BusinessDiscoveryResult(BaseModel):
    """Complete search result payload."""

    origin: LocationOrigin = Field(..., description="Geocoded center origin of the search")
    radius_meters: int = Field(..., description="Search radius used in meters")
    purpose: str = Field(..., description="Search purpose keyword used")
    total_found: int = Field(..., description="Total number of matching businesses returned")
    businesses: List[BusinessInfo] = Field(default_factory=list, description="List of top matching businesses")
