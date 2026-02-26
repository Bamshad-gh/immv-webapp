"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


# We will add more URL patterns here later, but for now we only have the admin panel URLs.
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
# Django's built-in admin — raw DB access for superusers
path('admin/', admin.site.urls),
# Auth — login, logout, register
# users/urls.py has: login/, logout/, register/
path('users/', include('users.urls')),

# Cases — user's case dashboard and detail
# cases/urls.py has: '', <case_id>/
path('cases/', include('cases.urls', namespace='cases')),

# Groups — group dashboard and management
# groups/urls.py has: '', create/, <group_id>/, etc.
path('groups/', include('groups.urls', namespace='groups')),

# Admin panel — completely separate from /admin/
# admin_panel/urls.py has: login/, dashboard/, cases/, users/, etc.
path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),

# EXPAND: add new app includes here
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)