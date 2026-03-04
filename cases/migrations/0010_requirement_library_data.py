# cases/migrations/0010_requirement_library_data.py
#
# Phase 1 — Data Migration: Populate CategoryRequirement + default sections
#
# What this migration does:
#   1. Create the 6 default RequirementSection rows (Personal Info, Travel, etc.)
#   2. For every existing Requirement that has a category_id:
#      → Create a CategoryRequirement row linking them
#      → Assign it to the "Other" section (admin can reassign later)
#      This preserves all existing service/category/requirement relationships.
#
# This migration READS Requirement.category_id (which still exists at this point).
# After this migration runs, migration 0011 can safely remove the category FK.
#
# Why use apps.get_model() instead of importing directly?
#   Django's data migrations must use the historical version of models
#   (the state at migration time), not the current live model class.
#   apps.get_model('cases', 'Requirement') returns the right version.

from django.db import migrations
from django.utils.text import slugify


# ── Default sections to create ────────────────────────────────
# These are the standard question banks for an immigration case management system.
# Admin can add more sections via the builder UI after deployment.
# 'order' controls display order in the library browser (lower = shown first).

DEFAULT_SECTIONS = [
    {'name': 'Personal Information', 'order': 1,
     'description': 'Basic personal details: name, date of birth, gender, nationality, etc.'},
    {'name': 'Family Information',   'order': 2,
     'description': 'Marital status, dependents, spouse/partner details, family members.'},
    {'name': 'Travel History',       'order': 3,
     'description': 'Entry dates, departure dates, visas held, countries visited.'},
    {'name': 'Education & Career',   'order': 4,
     'description': 'Educational background, work experience, job offers, credentials.'},
    {'name': 'Documents',            'order': 5,
     'description': 'Passports, identity documents, certificates, forms to upload.'},
    {'name': 'Other',                'order': 6,
     'description': 'Miscellaneous questions and information not in the above sections.'},
]


def create_sections_and_migrate(apps, schema_editor):
    """
    Forward migration:
    1. Create default RequirementSection rows.
    2. Migrate existing Requirement.category → CategoryRequirement rows.
    3. Assign existing requirements to the "Other" section.
    """
    RequirementSection  = apps.get_model('cases', 'RequirementSection')
    CategoryRequirement = apps.get_model('cases', 'CategoryRequirement')
    Requirement         = apps.get_model('cases', 'Requirement')

    # ── Step 1: Create default sections ───────────────────────────────
    section_map = {}   # name → RequirementSection instance (for use in Step 3)

    for data in DEFAULT_SECTIONS:
        # Generate a unique slug from the name
        base    = slugify(data['name'])[:100]
        slug    = base
        counter = 2
        while RequirementSection.objects.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1

        section = RequirementSection.objects.create(
            name        = data['name'],
            slug        = slug,
            description = data['description'],
            order       = data['order'],
            is_active   = True,
        )
        section_map[data['name']] = section

    other_section = section_map['Other']
    # 'Other' section is the fallback for existing requirements that aren't yet
    # organized. Admin can drag them into the correct section in the builder UI.

    # ── Step 2: Create CategoryRequirement rows ────────────────────────
    # For each existing Requirement that has a category_id, create a bridge row.
    # We use select_related to avoid N+1 queries on category.
    # Note: requirement.category_id is still accessible here (field removed in 0011).
    for requirement in Requirement.objects.filter(category__isnull=False):
        # Check if a CategoryRequirement already exists (shouldn't, but be safe).
        already_exists = CategoryRequirement.objects.filter(
            category_id  = requirement.category_id,
            requirement  = requirement,
        ).exists()

        if not already_exists:
            CategoryRequirement.objects.create(
                category_id          = requirement.category_id,
                requirement          = requirement,
                order                = 0,                # admin can reorder in builder
                is_required_override = None,             # None = use requirement.is_required
            )

    # ── Step 3: Assign existing requirements to "Other" section ───────
    # They'll appear under "Other" in the library browser.
    # Admin can use the builder to drag them to the correct section.
    Requirement.objects.filter(section__isnull=True).update(section=other_section)


def reverse_migration(apps, schema_editor):
    """
    Reverse migration: delete all RequirementSection and CategoryRequirement rows.
    RequirementSection deletion will cascade and clear Requirement.section FKs
    (because it's SET_NULL). CategoryRequirement rows are deleted explicitly.
    """
    RequirementSection  = apps.get_model('cases', 'RequirementSection')
    CategoryRequirement = apps.get_model('cases', 'CategoryRequirement')

    CategoryRequirement.objects.all().delete()
    RequirementSection.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0009_requirement_library_schema'),
    ]

    operations = [
        migrations.RunPython(
            create_sections_and_migrate,    # forward: create sections + migrate FKs
            reverse_migration,              # backward: delete sections + bridge rows
        ),
    ]
