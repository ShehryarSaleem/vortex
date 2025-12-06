from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class Banner(BaseModel):
    title: str
    image: HttpUrl


class DescriptionItem(BaseModel):
    description_text: str
    description_benefits: Optional[List[str]] = None


class Section(BaseModel):
    title: str
    description: str
    description_image: str = None
    description_benefits: Optional[List[str]] = None


class ChecklistCTA(BaseModel):
    cta_title: str
    cta_link: HttpUrl


class ExpensesSection(BaseModel):
    title: str
    expenses: List[str]


class LandingConfig(BaseModel):
    main_banner: Banner
    heading: str
    description: str
    images: List[str]
    sections: List[Section]
    checklist_cta: ChecklistCTA
    expenses_sections: ExpensesSection


class Reviews(BaseModel):
    text: str
    name: str
    country_flag: str
    country_name: str
    image: str


class Countries(BaseModel):
    name: str
    image: str
    slug: str
    title: str


class Testimonial(BaseModel):
    title: str
    heading: str
    reviews: List[Reviews]


class VisaServiceCountries(BaseModel):
    countries: List[Countries]
