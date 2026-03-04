# cases/migrations/0011_remove_requirement_category_fk.py
#
# Phase 1 — Cleanup: Remove the legacy Requirement.category FK
#
# This is safe to run ONLY after migration 0010, which has already:
#   - Created CategoryRequirement rows for every existing Requirement.category_id
#   - Preserved all existing category relationships
#
# After this migration, the only way to link a Requirement to a Category is via CategoryRequirement.
# Any code that uses `requirement.category` or `category.requirements.all()` will break
# and must be updated to use `category.category_requirements.all()` instead.
#
# Files updated alongside this migration:
#   - admin_panel/views.py  — create_case(), _create_case() helpers
#   - groups/views.py       — fill_case_for_managed()

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0010_requirement_library_data'),
    ]

    operations = [
        # Remove the legacy Requirement.category FK.
        # The CategoryRequirement model is now the only link between Requirement and Category.
        migrations.RemoveField(
            model_name='requirement',
            name='category',
        ),
    ]
