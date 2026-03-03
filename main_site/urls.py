# main_site/urls.py
# Public marketing site URL patterns.
# All routes registered at '/' in config/urls.py.
#
# EXPAND: add new public pages here — just add a path() and a matching view.

from django.urls import path
from . import views

app_name = 'main_site'

urlpatterns = [
    path('',                      views.home,           name='home'),
    path('services/',             views.services_list,  name='services'),
    path('services/<slug:slug>/', views.service_detail, name='service_detail'),
    path('about/',                views.about,          name='about'),
    path('contact/',              views.contact,        name='contact'),
    path('blog/',                 views.blog_list,      name='blog'),
    path('blog/<slug:slug>/',     views.blog_detail,    name='blog_detail'),
    path('robots.txt',            views.robots_txt,     name='robots_txt'),
]
