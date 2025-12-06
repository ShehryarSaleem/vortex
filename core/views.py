from django.shortcuts import render
from django.http import HttpRequest
from .utils import (
    load_config,
    load_testimonial,
    load_visa_services_countries,
    get_random_success_stories,
)
from .context_schema import Testimonial, Reviews

# Load global configs that don't change often or can be loaded per request
# For simplicity and to match FastAPI behavior, we'll load them in views or globally if static.
# However, loading in views ensures we pick up file changes without restart (mostly).
# But for performance, we might want to cache. Given the scale, loading in views is fine.

def home(request: HttpRequest):
    visa_countries_config = load_visa_services_countries()
    testimonial_config = load_testimonial()
    
    # Get random success stories
    success_stories = get_random_success_stories(max_items=6)

    # Create a modified testimonial config with random images
    testimonial_context = testimonial_config
    if success_stories:
        # Update reviews with random images
        reviews = []
        for story in success_stories:
            # Create review entry with just the image
            reviews.append(Reviews(
                text="",
                name="",
                country_flag="",
                country_name="",
                image=story['image']
            ))
        # Create new testimonial object with updated reviews
        testimonial_context = Testimonial(
            title=testimonial_config.title,
            heading=testimonial_config.heading,
            reviews=reviews
        )

    return render(request, "home.html", {
        "context": testimonial_context,
        "visa_countries": visa_countries_config.countries
    })


def visa_detail_page(request: HttpRequest, slug: str):
    visa_countries_config = load_visa_services_countries()
    config = load_config(slug.replace("-", "_"))
    
    # Preprocess sections for template logic
    sections_data = []
    sections = config.sections
    for i, section in enumerate(sections):
        # Convert Pydantic model to dict
        sec_data = section.model_dump() if hasattr(section, 'model_dump') else section.dict()
        sec_data['is_benefits'] = (section.title == 'Benefits')
        sec_data['is_estimated_cost'] = (section.title == 'Estimated Cost')
        
        # Next section
        if i < len(sections) - 1:
            next_sec = sections[i+1]
            next_sec_data = next_sec.model_dump() if hasattr(next_sec, 'model_dump') else next_sec.dict()
            sec_data['next_section'] = next_sec_data
            sec_data['is_estimated_cost_next'] = (next_sec.title == 'Estimated Cost')
        else:
            sec_data['next_section'] = None
            sec_data['is_estimated_cost_next'] = False
            
        # Prev section
        if i > 0:
            prev_sec = sections[i-1]
            prev_sec_data = prev_sec.model_dump() if hasattr(prev_sec, 'model_dump') else prev_sec.dict()
            sec_data['prev_section'] = prev_sec_data
            sec_data['is_benefits_prev'] = (prev_sec.title == 'Benefits')
        else:
            sec_data['prev_section'] = None
            sec_data['is_benefits_prev'] = False
            
        sections_data.append(sec_data)
    
    # Convert main config to dict and replace sections
    config_dict = config.model_dump() if hasattr(config, 'model_dump') else config.dict()
    config_dict['sections'] = sections_data

    return render(request, "tourist_visa_detail.html", {
        "config": config_dict,
        "slug": slug,
        "visa_countries": visa_countries_config.countries
    })


def services(request: HttpRequest):
    visa_countries_config = load_visa_services_countries()
    return render(request, "services.html", {
        "visa_countries": visa_countries_config.countries
    })


def contact(request: HttpRequest):
    visa_countries_config = load_visa_services_countries()
    return render(request, "contact_us.html", {
        "visa_countries": visa_countries_config.countries
    })


def tourist_visa_service_details(request: HttpRequest):
    return render(request, "service_details.html")


def about(request: HttpRequest):
    return render(request, "about.html")


def faq(request: HttpRequest):
    return render(request, "faq.html")


def team(request: HttpRequest):
    return render(request, "team.html")


def terms_and_conditions(request: HttpRequest):
    return render(request, "terms_and_conditions.html")


def blog_tourist_visa_tips(request: HttpRequest):
    return render(request, "blog_tourist_visa_tips.html")


def blog_student_visa_guide(request: HttpRequest):
    return render(request, "blog_student_visa_guide.html")


def blog_work_visa_requirements(request: HttpRequest):
    return render(request, "blog_work_visa_requirements.html")


def blogs(request: HttpRequest):
    # List all blog pages with images
    blog_pages = [
        {
            "title": "Tourist Visa Tips: Essential Advice for Your Journey",
            "description": "Comprehensive tips for a smooth tourist visa application process.",
            "url": "/blog/tourist-visa-tips",
            "image": "/static/img/blog/blog-01.jpg"
        },
        {
            "title": "Student Visa Guide: Your Path to International Education",
            "description": "A complete guide for obtaining a student visa for your studies abroad.",
            "url": "/blog/student-visa-guide",
            "image": "/static/img/blog/blog-02.jpg"
        },
        {
            "title": "Work Visa Requirements: Navigating Global Employment",
            "description": "Understand the requirements for securing a work visa in various countries.",
            "url": "/blog/work-visa-requirements",
            "image": "/static/img/blog/blog-03.jpg"
        },
    ]

    return render(request, "blogs.html", {"blog_pages": blog_pages})


def search(request: HttpRequest):
    query = request.GET.get("s", "").lower().strip()
    results = []
    visa_countries_config = load_visa_services_countries()

    if query:
        # Search through countries
        for country in visa_countries_config.countries:
            if query in country.name.lower() or query in country.slug.lower():
                results.append({
                    "title": f"{country.name} Tourist Visa",
                    "description": f"Get your {country.name} tourist visa. {country.title}",
                    "url": f"/tourist-visa/{country.slug}/"
                })

        # Search through services
        services_list = [
            {"name": "Tourist Visa", "desc": "Explore the world with our tourist visa services", "url": "/service-details/tourist-visa"},
            {"name": "Student Visa", "desc": "Pursue your education abroad with our student visa assistance", "url": "/services"},
            {"name": "Business Visa", "desc": "Expand your business globally with our business visa services", "url": "/services"},
            {"name": "Family Visa", "desc": "Reunite with your loved ones through our family visa services", "url": "/services"},
            {"name": "Job Seeker Visa", "desc": "Find employment opportunities abroad with our job seeker visa assistance", "url": "/services"},
            {"name": "Migrate Visa", "desc": "Start a new life abroad with our immigration visa services", "url": "/services"},
        ]

        for service in services_list:
            if query in service["name"].lower() or query in service["desc"].lower():
                results.append({
                    "title": service["name"],
                    "description": service["desc"],
                    "url": service["url"]
                })

        # Search through pages
        pages = [
            {"name": "About Us", "desc": "Learn more about VortexEase and our services", "url": "/about"},
            {"name": "FAQ", "desc": "Frequently asked questions about visas and immigration", "url": "/faq"},
            {"name": "Contact", "desc": "Get in touch with our team for visa assistance", "url": "/contact"},
            {"name": "Tourist Visa Tips", "desc": "Essential tips and guide for tourist visa applications", "url": "/blog/tourist-visa-tips"},
            {"name": "Student Visa Guide", "desc": "Complete guide to student visa applications and requirements", "url": "/blog/student-visa-guide"},
            {"name": "Work Visa Requirements", "desc": "Work visa requirements and application process explained", "url": "/blog/work-visa-requirements"},
        ]

        for page in pages:
            if query in page["name"].lower() or query in page["desc"].lower():
                results.append({
                    "title": page["name"],
                    "description": page["desc"],
                    "url": page["url"]
                })

    return render(request, "search.html", {"query": query, "results": results})
