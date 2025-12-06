from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("tourist-visa/<slug:slug>/", views.visa_detail_page, name="visa_detail_page"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    path("service-details/tourist-visa/", views.tourist_visa_service_details, name="tourist_visa_service_details"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
    path("team/", views.team, name="team"),
    path("terms-and-conditions/", views.terms_and_conditions, name="terms_and_conditions"),
    path("blog/tourist-visa-tips/", views.blog_tourist_visa_tips, name="blog_tourist_visa_tips"),
    path("blog/student-visa-guide/", views.blog_student_visa_guide, name="blog_student_visa_guide"),
    path("blog/work-visa-requirements/", views.blog_work_visa_requirements, name="blog_work_visa_requirements"),
    path("blogs/", views.blogs, name="blogs"),
    path("search/", views.search, name="search"),
]
