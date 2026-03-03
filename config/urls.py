"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from main_site.sitemaps import StaticViewSitemap, BlogSitemap, ServiceSitemap

sitemaps = {
    'static':   StaticViewSitemap,
    'blog':     BlogSitemap,
    'services': ServiceSitemap,
}

urlpatterns = [
    # Django's built-in admin — raw DB access for superusers
    path('admin/', admin.site.urls),

    # Auth — login, logout, register
    path('users/', include('users.urls')),

    # Cases — user's case dashboard and details
    path('cases/', include('cases.urls', namespace='cases')),

    # Groups — group dashboard and management
    path('groups/', include('groups.urls', namespace='groups')),

    # Admin panel — completely separate from /admin/
    path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),

    # Payments — user-facing invoice list and detail
    path('invoices/', include('payments.urls', namespace='payments')),

    # SEO — /sitemap.xml
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),

    # Public marketing site — MUST be last (catches '/' and all public slugs)
    # EXPAND: add new app includes above this line
    path('', include('main_site.urls', namespace='main_site')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
