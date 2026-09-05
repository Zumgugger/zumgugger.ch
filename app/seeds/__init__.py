"""Seed data management for WebsiteCMS."""

from typing import Any, Dict, List

from app.seeds.band import get_band_seed
from app.seeds.rolfing import get_rolfing_seed


# Registry of available seed types
SEED_TYPES = {
    "band": get_band_seed,
    "rolfing": get_rolfing_seed,
}


def load_seed(site_type: str) -> Dict[str, Any]:
    """Load seed data for a specific site type.
    
    Args:
        site_type: The type of site (band, rolfing, etc.)
        
    Returns:
        Dictionary containing all seed data for the site type.
        
    Raises:
        ValueError: If site_type is not recognized.
    """
    if site_type not in SEED_TYPES:
        available = ", ".join(sorted(SEED_TYPES.keys()))
        raise ValueError(
            f"Unknown site type: '{site_type}'. Available types: {available}"
        )
    
    return SEED_TYPES[site_type]()


def get_available_site_types() -> List[str]:
    """Get list of available site types.
    
    Returns:
        List of available site type names.
    """
    return sorted(SEED_TYPES.keys())


def validate_seed_data(seed_data: Dict[str, Any]) -> bool:
    """Validate that seed data has the required structure.
    
    Args:
        seed_data: The seed data dictionary to validate.
        
    Returns:
        True if valid, raises ValueError otherwise.
    """
    required_keys = ["site_type", "content", "config"]
    
    for key in required_keys:
        if key not in seed_data:
            raise ValueError(f"Seed data missing required key: {key}")
    
    content = seed_data["content"]
    required_content_keys = [
        "hero_headline",
        "hero_cta_text",
        "services",
        "impressum_content",
        "datenschutz_content",
    ]
    
    for key in required_content_keys:
        if key not in content:
            raise ValueError(f"Seed content missing required key: {key}")
    
    config = seed_data["config"]
    required_config_keys = ["theme_name", "module_states", "module_order"]
    
    for key in required_config_keys:
        if key not in config:
            raise ValueError(f"Seed config missing required key: {key}")
    
    return True


__all__ = [
    "load_seed",
    "get_available_site_types",
    "validate_seed_data",
    "SEED_TYPES",
]
