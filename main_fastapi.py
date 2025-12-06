from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import yaml
import os
import random
import re
from context_schema import LandingConfig, Testimonial, VisaServiceCountries
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="vortex ease", version="1.0.0", description="Provides visa services"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def load_config(slug: str) -> LandingConfig:
    config_path = os.path.join(os.path.dirname(__file__), f"config/{slug}.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return LandingConfig(**data)


def load_testimonial() -> Testimonial:
    config_path = os.path.join(os.path.dirname(__file__), "config/testmonial.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Testimonial(**data)


def load_visa_services_countries() -> VisaServiceCountries:
    config_path = os.path.join(
        os.path.dirname(__file__), "config/visa_service_countries.yaml"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VisaServiceCountries(**data)


def get_country_code_from_filename(filename: str) -> str:
    """Extract country code from filename like eu_ge_01.png -> eu_ge, us_01.png -> us_01"""
    # Remove extension
    name = os.path.splitext(filename)[0]
    # Match patterns: eu_ge_01 -> eu_ge, us_01 -> us_01, au_01 -> au_01
    match = re.match(r"^([a-z]{2}_[a-z]{2})_\d+$|^([a-z]{2}_\d+)$", name)
    if match:
        return match.group(1) or match.group(2)
    # Fallback: take first part before underscore
    parts = name.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return parts[0] if parts else name


def get_random_success_stories(max_items: int = 6):
    """Get random success story images ensuring no same country appears together"""
    testimonial_dir = os.path.join(
        os.path.dirname(__file__), "static/img/testimentional"
    )

    # Get all image files
    image_files = []
    if os.path.exists(testimonial_dir):
        for file in os.listdir(testimonial_dir):
            if file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                country_code = get_country_code_from_filename(file)
                image_files.append(
                    {
                        "image": f"img/testimentional/{file}",
                        "country_code": country_code,
                    }
                )

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

        country = img["country_code"]

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
            country = img["country_code"]
            # Check if last selected item is from same country
            if selected and selected[-1]["country_code"] == country:
                continue
            selected.append(img)
            remaining.remove(img)

    return selected[:max_items]


Testimonial_Config = load_testimonial()

Visa_Countries_Config = load_visa_services_countries()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    print(Visa_Countries_Config)
    # Get random success stories
    success_stories = get_random_success_stories(max_items=6)

    # Create a modified testimonial config with random images
    testimonial_context = Testimonial_Config
    if success_stories:
        # Update reviews with random images
        from context_schema import Reviews

        reviews = []
        for story in success_stories:
            # Create review entry with just the image
            reviews.append(
                Reviews(
                    text="",
                    name="",
                    country_flag="",
                    country_name="",
                    image=story["image"],
                )
            )
        # Create new testimonial object with updated reviews
        testimonial_context = Testimonial(
            title=Testimonial_Config.title,
            heading=Testimonial_Config.heading,
            reviews=reviews,
        )

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "context": testimonial_context,
            "visa_countries": Visa_Countries_Config.countries,
        },
    )


@app.get("/tourist-visa/{slug}/", response_class=HTMLResponse)
async def visa_detail_page(request: Request, slug: str):
    CONFIG = load_config(slug.replace("-", "_"))
    return templates.TemplateResponse(
        "tourist_visa_detail.html",
        {
            "request": request,
            "config": CONFIG,
            "slug": slug,
            "visa_countries": Visa_Countries_Config.countries,
        },
    )


@app.get("/services", response_class=HTMLResponse)
async def services(request: Request):
    return templates.TemplateResponse(
        "services.html",
        {"request": request, "visa_countries": Visa_Countries_Config.countries},
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse(
        "contact_us.html",
        {"request": request, "visa_countries": Visa_Countries_Config.countries},
    )


@app.get("/service-details/tourist-visa", response_class=HTMLResponse)
async def tourist_visa_service_details(request: Request):
    return templates.TemplateResponse("service_details.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    return templates.TemplateResponse("faq.html", {"request": request})


@app.get("/team", response_class=HTMLResponse)
async def team(request: Request):
    return templates.TemplateResponse("team.html", {"request": request})


@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def terms_and_conditions(request: Request):
    return templates.TemplateResponse("terms_and_conditions.html", {"request": request})


@app.get("/blog/tourist-visa-tips", response_class=HTMLResponse)
async def blog_tourist_visa_tips(request: Request):
    return templates.TemplateResponse(
        "blog_tourist_visa_tips.html", {"request": request}
    )


@app.get("/blog/student-visa-guide", response_class=HTMLResponse)
async def blog_student_visa_guide(request: Request):
    return templates.TemplateResponse(
        "blog_student_visa_guide.html", {"request": request}
    )


@app.get("/blog/work-visa-requirements", response_class=HTMLResponse)
async def blog_work_visa_requirements(request: Request):
    return templates.TemplateResponse(
        "blog_work_visa_requirements.html", {"request": request}
    )


@app.get("/blogs", response_class=HTMLResponse)
async def blogs(request: Request):
    # List all blog pages with images
    blog_pages = [
        {
            "title": "Tourist Visa Tips: Essential Advice for Your Journey",
            "description": "Comprehensive tips for a smooth tourist visa application process.",
            "url": "/blog/tourist-visa-tips",
            "image": "/static/img/blog/blog-01.jpg",
        },
        {
            "title": "Student Visa Guide: Your Path to International Education",
            "description": "A complete guide for obtaining a student visa for your studies abroad.",
            "url": "/blog/student-visa-guide",
            "image": "/static/img/blog/blog-02.jpg",
        },
        {
            "title": "Work Visa Requirements: Navigating Global Employment",
            "description": "Understand the requirements for securing a work visa in various countries.",
            "url": "/blog/work-visa-requirements",
            "image": "/static/img/blog/blog-03.jpg",
        },
    ]

    return templates.TemplateResponse(
        "blogs.html", {"request": request, "blog_pages": blog_pages}
    )


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request):
    query = request.query_params.get("s", "").lower().strip()
    results = []

    if query:
        # Search through countries
        for country in Visa_Countries_Config.countries:
            if query in country.name.lower() or query in country.slug.lower():
                results.append(
                    {
                        "title": f"{country.name} Tourist Visa",
                        "description": f"Get your {country.name} tourist visa. {country.title}",
                        "url": f"/tourist-visa/{country.slug}/",
                    }
                )

        # Search through services
        services = [
            {
                "name": "Tourist Visa",
                "desc": "Explore the world with our tourist visa services",
                "url": "/service-details/tourist-visa",
            },
            {
                "name": "Student Visa",
                "desc": "Pursue your education abroad with our student visa assistance",
                "url": "/services",
            },
            {
                "name": "Business Visa",
                "desc": "Expand your business globally with our business visa services",
                "url": "/services",
            },
            {
                "name": "Family Visa",
                "desc": "Reunite with your loved ones through our family visa services",
                "url": "/services",
            },
            {
                "name": "Job Seeker Visa",
                "desc": "Find employment opportunities abroad with our job seeker visa assistance",
                "url": "/services",
            },
            {
                "name": "Migrate Visa",
                "desc": "Start a new life abroad with our immigration visa services",
                "url": "/services",
            },
        ]

        for service in services:
            if query in service["name"].lower() or query in service["desc"].lower():
                results.append(
                    {
                        "title": service["name"],
                        "description": service["desc"],
                        "url": service["url"],
                    }
                )

        # Search through pages
        pages = [
            {
                "name": "About Us",
                "desc": "Learn more about VortexEase and our services",
                "url": "/about",
            },
            {
                "name": "FAQ",
                "desc": "Frequently asked questions about visas and immigration",
                "url": "/faq",
            },
            {
                "name": "Contact",
                "desc": "Get in touch with our team for visa assistance",
                "url": "/contact",
            },
            {
                "name": "Tourist Visa Tips",
                "desc": "Essential tips and guide for tourist visa applications",
                "url": "/blog/tourist-visa-tips",
            },
            {
                "name": "Student Visa Guide",
                "desc": "Complete guide to student visa applications and requirements",
                "url": "/blog/student-visa-guide",
            },
            {
                "name": "Work Visa Requirements",
                "desc": "Work visa requirements and application process explained",
                "url": "/blog/work-visa-requirements",
            },
        ]

        for page in pages:
            if query in page["name"].lower() or query in page["desc"].lower():
                results.append(
                    {
                        "title": page["name"],
                        "description": page["desc"],
                        "url": page["url"],
                    }
                )

    return templates.TemplateResponse(
        "search.html", {"request": request, "query": query, "results": results}
    )
