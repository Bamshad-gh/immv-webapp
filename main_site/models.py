# main_site/models.py
# ─────────────────────────────────────────────────────────────
# 1. SiteSettings — singleton: one row holds all editable site content.
#                   Admin edits this via admin panel → Content → Site Settings.
# 2. BlogPost     — SEO articles managed from admin panel.
# 3. ContactMessage — messages submitted via the public contact form.
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# ── 1. SITE SETTINGS ─────────────────────────────────────────
# Singleton — only one row ever exists (pk=1 always).
# Use SiteSettings.get() everywhere — never .filter() directly.
# The context processor injects `site_settings` into all templates automatically.
#
# EXPAND: add primary_color CharField for CSS variable theming.
# EXPAND: add favicon ImageField.

class SiteSettings(models.Model):

    # Company identity
    company_name = models.CharField(max_length=100, default='CaseFlow')
    tagline      = models.CharField(max_length=200, blank=True,
                                    default='Professional Immigration Services')
    logo         = models.ImageField(upload_to='site/', blank=True, null=True)

    # Contact info (shown in footer and contact page)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    address       = models.TextField(blank=True)

    # Social links — leave blank to hide the icon in the footer
    linkedin_url  = models.CharField(max_length=200, blank=True)
    instagram_url = models.CharField(max_length=200, blank=True)

    # Home page content
    hero_title    = models.CharField(max_length=200,
                                     default='Immigration Made Simple')
    hero_subtitle = models.TextField(
        blank=True,
        default='Expert guidance every step of the way. '
                'From visa applications to permanent residency, '
                'we handle the complexity so you can focus on your future.'
    )
    hero_cta_text = models.CharField(max_length=60, default='Get Started')

    # About page content
    about_title = models.CharField(max_length=200, default='About Us')
    about_body  = models.TextField(
        blank=True,
        default='We are a team of dedicated immigration professionals committed to '
                'helping individuals and families navigate the immigration process with confidence.'
    )

    # ── Brand Colors ──────────────────────────────────────────
    # Each maps directly to a CSS variable. Leave blank to keep the built-in default.
    # Applied to ALL portals: public site, user portal, admin panel.
    #
    # CSS variable mapping:
    #   color_primary      → --navy        (dark bg, text, nav)     default #0f1923
    #   color_accent       → --amber       (buttons, links, badges) default #c8820a
    #   color_accent_light → --amber-light (soft highlight bg)      default #f5e6c8
    #   color_background   → --cream       (page background)        default #f7f5f0
    #
    # EXPAND: add color_danger, color_success for status color control.
    color_primary      = models.CharField(max_length=7, blank=True, default='')
    color_accent       = models.CharField(max_length=7, blank=True, default='')
    color_accent_light = models.CharField(max_length=7, blank=True, default='')
    color_background   = models.CharField(max_length=7, blank=True, default='')

    class Meta:
        verbose_name = 'Site Settings'

    def __str__(self):
        return f'Site Settings — {self.company_name}'

    @classmethod
    def get(cls):
        """
        Returns the single SiteSettings row, creating it with defaults if none
        exists yet. Always use this instead of SiteSettings.objects.get(pk=1).
        The context processor calls this automatically for every request.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── 2. BLOG POST ──────────────────────────────────────────────
# SEO-focused news/articles. Only is_published=True posts are shown publicly.
# Slug auto-generates from title on first save. Duplicate slugs get -2, -3 …
#
# EXPAND: swap `body` TextField for a rich-text field (e.g. django-ckeditor)
#         — just replace the field definition, nothing else changes.
# EXPAND: add `author` FK → User for multi-author blogs.

class BlogPost(models.Model):

    title            = models.CharField(max_length=200)
    slug             = models.SlugField(max_length=220, unique=True, blank=True)
    body             = models.TextField()
    meta_description = models.CharField(
        max_length=160, blank=True,
        help_text='Shown in Google search results. Keep under 160 characters.'
    )
    thumbnail    = models.ImageField(upload_to='blog/', blank=True, null=True)
    published_at = models.DateField(default=timezone.now)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base    = slugify(self.title)[:200]
            slug    = base
            counter = 2
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# ── 3. CONTACT MESSAGE ────────────────────────────────────────
# Stores messages submitted via the public contact form.
# Admin reads them at admin panel → Content → Contact Messages.
# is_read tracks which messages have been actioned.
#
# EXPAND: add `replied_at` DateTimeField to track response time.
# EXPAND: trigger email notification to admin on new submission.

class ContactMessage(models.Model):

    name    = models.CharField(max_length=100)
    email   = models.EmailField()
    phone   = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject}'
