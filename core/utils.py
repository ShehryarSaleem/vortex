import os
import yaml
import random
import re
from django.conf import settings
from .context_schema import LandingConfig, Testimonial, VisaServiceCountries

def load_config(slug: str) -> LandingConfig:
    config_path = os.path.join(settings.BASE_DIR, f"config/{slug}.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return LandingConfig(**data)


def load_testimonial() -> Testimonial:
    config_path = os.path.join(settings.BASE_DIR, "config/testmonial.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Testimonial(**data)


def load_visa_services_countries() -> VisaServiceCountries:
    config_path = os.path.join(settings.BASE_DIR, "config/visa_service_countries.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VisaServiceCountries(**data)


def get_country_code_from_filename(filename: str) -> str:
    """Extract country code from filename like eu_ge_01.png -> eu_ge, us_01.png -> us_01"""
    # Remove extension
    name = os.path.splitext(filename)[0]
    # Match patterns: eu_ge_01 -> eu_ge, us_01 -> us_01, au_01 -> au_01
    match = re.match(r'^([a-z]{2}_[a-z]{2})_\d+$|^([a-z]{2}_\d+)$', name)
    if match:
        return match.group(1) or match.group(2)
    # Fallback: take first part before underscore
    parts = name.split('_')
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return parts[0] if parts else name


def get_random_success_stories(max_items: int = 6):
    """Get random success story images ensuring no same country appears together"""
    # Assuming static files are at BASE_DIR/static
    testimonial_dir = os.path.join(settings.BASE_DIR, "static/img/testimentional")

    # Get all image files
    image_files = []
    if os.path.exists(testimonial_dir):
        for file in os.listdir(testimonial_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                country_code = get_country_code_from_filename(file)
                image_files.append({
                    'image': f'img/testimentional/{file}',
                    'country_code': country_code
                })

    if not image_files:
        return []

    # Shuffle all images
    random.shuffle(image_files)

    # Select images ensuring no same country appears consecutively
    selected = []
    used_countries = set()

    for img in image_files:
        if len(selected) >= max_items:
            break

        country = img['country_code']

        # If this country was just used, skip it for now
        if country in used_countries:
            continue

        selected.append(img)
        used_countries.add(country)

        # Reset used countries after a few items to allow variety
        if len(used_countries) >= 3:
            used_countries.clear()

    # If we still need more items and have remaining images
    remaining = [img for img in image_files if img not in selected]
    while len(selected) < max_items and remaining:
        random.shuffle(remaining)
        for img in remaining:
            if len(selected) >= max_items:
                break
            country = img['country_code']
            # Check if last selected item is from same country
            if selected and selected[-1]['country_code'] == country:
                continue
            selected.append(img)
            remaining.remove(img)

    return selected[:max_items]
