# main_site/sitemaps.py
# ─────────────────────────────────────────────────────────────
# Three sitemap classes registered at /sitemap.xml in config/urls.py.
#
#   StaticViewSitemap  — home, services list, about, contact, blog list
#   BlogSitemap        — one entry per published BlogPost
#   ServiceSitemap     — one entry per active Service
#
# EXPAND: add CategorySitemap for individual category pages.
# ─────────────────────────────────────────────────────────────

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from cases.models import Service
from .models import BlogPost


class StaticViewSitemap(Sitemap):
    """Static pages that always exist."""
    priority   = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['main_site:home', 'main_site:services', 'main_site:about',
                'main_site:contact', 'main_site:blog']

    def location(self, item):
        return reverse(item)


class BlogSitemap(Sitemap):
    """One sitemap entry per published blog post."""
    changefreq = 'never'     # posts don't change after publish
    priority   = 0.6

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('main_site:blog_detail', args=[obj.slug])


class ServiceSitemap(Sitemap):
    """One sitemap entry per active service."""
    changefreq = 'monthly'
    priority   = 0.7

    def items(self):
        return Service.objects.filter(is_active=True)

    def location(self, obj):
        return reverse('main_site:service_detail', args=[obj.slug])
