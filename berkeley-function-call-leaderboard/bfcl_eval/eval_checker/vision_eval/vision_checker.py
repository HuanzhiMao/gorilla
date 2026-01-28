import re
import numpy as np
from geopy.distance import geodesic


def vision_checker(model_response: str, possible_answer_list: list[str]) -> dict:
    """
    Check model's coordinate prediction against ground truth coordinates.
    
    Extracts (latitude, longitude) from model_response, computes geodesic distance
    to ground truth, and returns a score using the formula:
        score = 5000 * exp(-10 * distance_km / 14916.862)
    """
    # Parse model response to extract coordinates
    model_coords = extract_coordinates_from_response(model_response)
    
    if model_coords is None:
        return {
            "score": 0.0,
            "error_message": "Could not extract coordinates from model response.",
            "error_type": "vision_geogesser:coordinate_extraction_failed",
            "details": {
                "model_coordinate": model_response,
                "ground_truth_coordinate": possible_answer_list,
            },
        }
    
    # Parse ground truth coordinates
    assert len(possible_answer_list) == 1, "There should be only one ground truth coordinate"
    ground_truth_coords = parse_coordinate_string(possible_answer_list[0])
    
    # Compute geodesic distance in kilometers
    distance_km = geodesic(model_coords, ground_truth_coords).kilometers
    
    # Compute score using the GeoGuessr-style formula
    # 5000 * exp(-10 * distance / 14916.862)
    # 14916.862 km is roughly half the Earth's circumference
    score = 5000 * np.exp(-10 * distance_km / 14916.862)
    
    return {
        "score": float(score),
        "details": {
            "distance_km": float(distance_km),
            "model_coordinate": model_coords,
            "ground_truth_coordinate": ground_truth_coords,
        },
    }


def extract_coordinates_from_response(response: str) -> tuple[float, float] | None:
    """
    Extract (latitude, longitude) from model response.
    
    Handles formats like:
        - "{'answer': '(78.2259000, 15.6486000)', ...}"
        - "(78.2259, 15.6486)"
        - "78.2259, 15.6486"
        - "I do not know" -> returns None
    """
    if not isinstance(response, str):
        response = str(response)
    
    # Match coordinate pattern: optional parens, lat, lon
    pattern = r"\(?([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\)?"
    
    matches = re.findall(pattern, response)
    for match in matches:
        try:
            lat = float(match[0])
            lon = float(match[1])
            if is_valid_coordinate(lat, lon):
                return (lat, lon)
        except ValueError:
            continue
    
    return None


def parse_coordinate_string(coord_str: str) -> tuple[float, float] | None:
    """
    Parse a coordinate string like "78.2232, 15.6267" into (lat, lon) tuple.
    """
    assert isinstance(coord_str, str), "Coordinate string must be a string"
    
    # Remove parentheses if present
    coord_str = coord_str.strip().strip("()")
    
    # Split by comma
    parts = coord_str.split(",")
    if len(parts) != 2:
        raise ValueError(f"Invalid coordinate string: {coord_str}")
    
    lat = float(parts[0].strip())
    lon = float(parts[1].strip())
    if is_valid_coordinate(lat, lon):
        return (lat, lon)
    else:
        raise ValueError(f"Invalid coordinate: {lat}, {lon}")


def is_valid_coordinate(lat: float, lon: float) -> bool:
    """
    Check if coordinates are within valid ranges.
    Latitude: -90 to 90
    Longitude: -180 to 180
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180
