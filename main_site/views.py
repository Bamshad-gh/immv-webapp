# main_site/views.py
# ─────────────────────────────────────────────────────────────
# Public-facing marketing site views.
#
# Views (in order):
#   1. home            — landing page (hero, services grid, blog preview)
#   2. services_list   — all active services as cards
#   3. service_detail  — one service with its active categories
#   4. about           — content from SiteSettings.about_body
#   5. contact         — GET: form  |  POST: save ContactMessage + redirect
#   6. blog_list       — published posts, newest first
#   7. blog_detail     — single post with SEO meta
#   8. robots_txt      — /robots.txt as plain text
#
# No login required — all views are fully public.
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from cases.models import Service, Category
from .models import BlogPost, ContactMessage


# ── 1. HOME ───────────────────────────────────────────────────
def home(request):
    """
    Landing page.
    Shows: hero (from SiteSettings), active services grid, 3 latest published posts.
    EXPAND: add testimonials queryset here.
    """
    services   = Service.objects.filter(is_active=True)
    blog_posts = BlogPost.objects.filter(is_published=True)[:3]   # preview only

    return render(request, 'main_site/home.html', {
        'services':   services,
        'blog_posts': blog_posts,
    })


# ── 2. SERVICES LIST ──────────────────────────────────────────
def services_list(request):
    """All active services displayed as cards."""
    services = Service.objects.filter(is_active=True)
    return render(request, 'main_site/services.html', {
        'services': services,
    })


# ── 3. SERVICE DETAIL ─────────────────────────────────────────
def service_detail(request, slug):
    """
    One service and its top-level active categories.
    URL: /services/<slug>/
    """
    service    = get_object_or_404(Service, slug=slug, is_active=True)
    categories = Category.objects.filter(
        service=service,
        parent=None,        # top-level only
        is_active=True,
    )
    return render(request, 'main_site/service_detail.html', {
        'service':    service,
        'categories': categories,
    })


# ── 4. ABOUT ──────────────────────────────────────────────────
def about(request):
    """About page — content from SiteSettings.about_title / about_body."""
    return render(request, 'main_site/about.html')


# ── 5. CONTACT ────────────────────────────────────────────────
@require_http_methods(['GET', 'POST'])
def contact(request):
    """
    GET  — display the contact form.
    POST — save ContactMessage, redirect with success message.

    EXPAND: replace with a Django ModelForm for richer validation/error display.
    """
    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and subject and message:
            ContactMessage.objects.create(
                name=name,
                email=email,
                phone=phone,
                subject=subject,
                message=message,
            )
            messages.success(
                request,
                "Thank you for reaching out! We'll get back to you soon."
            )
            return redirect('main_site:contact')

        messages.error(request, 'Please fill in all required fields.')

    return render(request, 'main_site/contact.html')


# ── 6. BLOG LIST ──────────────────────────────────────────────
def blog_list(request):
    """All published posts, newest first."""
    posts = BlogPost.objects.filter(is_published=True)
    return render(request, 'main_site/blog_list.html', {'posts': posts})


# ── 7. BLOG DETAIL ────────────────────────────────────────────
def blog_detail(request, slug):
    """Single published blog post. Template sets <title> and <meta description>."""
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    return render(request, 'main_site/blog_detail.html', {'post': post})


# ── 8. ROBOTS.TXT ─────────────────────────────────────────────
def robots_txt(request):
    """Serves /robots.txt as plain text."""
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /admin-panel/',
        'Disallow: /users/',
        '',
        f'Sitemap: {request.build_absolute_uri("/sitemap.xml")}',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')
