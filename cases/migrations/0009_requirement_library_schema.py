# cases/migrations/0009_requirement_library_schema.py
#
# Phase 1 — Schema Migration: Requirement Library System
#
# What this migration does (in order):
#   1. Create RequirementSection  — the named "question banks"
#   2. Add Requirement.section FK — links requirements to a section
#   3. Add new Requirement types  — 'select', 'boolean', 'info_text'
#   4. Rename auto_field_form → profile_mapping  — clarifies its purpose
#   5. Make Requirement.category nullable  — so new library items don't need a category
#   6. Create RequirementChoice  — options for 'select'-type requirements
#   7. Create CategoryRequirement  — the M2M bridge replacing Requirement.category FK
#   8. Add CaseAnswer.answer_choice FK  — stores the chosen RequirementChoice
#
# IMPORTANT: Requirement.category FK is NOT removed here.
# It becomes nullable so new requirements can exist without a category.
# Migration 0010 (data migration) will read it to create CategoryRequirement rows.
# Migration 0011 will remove it after the data is safely migrated.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0008_category_slug_service_slug'),
    ]

    operations = [

        # ── Step 1: Create RequirementSection ─────────────────────────
        # New model: named groups for the requirement library.
        # Default sections are populated in migration 0010 (data migration).
        migrations.CreateModel(
            name='RequirementSection',
            fields=[
                ('id',          models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',        models.CharField(max_length=100, unique=True)),
                ('slug',        models.SlugField(blank=True, max_length=120, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('order',       models.PositiveIntegerField(default=0)),
                ('is_active',   models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['order', 'name'],
            },
        ),

        # ── Step 2: Add Requirement.section FK ────────────────────────
        # null=True so existing requirements can be migrated gradually.
        # Requirements without a section appear as "Uncategorized" in the library.
        migrations.AddField(
            model_name='requirement',
            name='section',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requirements',
                to='cases.requirementsection',
            ),
        ),

        # ── Step 3: Add new Requirement types ─────────────────────────
        # AlterField replaces the entire type field definition.
        # Existing values ('document', 'question', 'text', 'number', 'date') are unchanged.
        # New values added: 'select', 'boolean', 'info_text'
        migrations.AlterField(
            model_name='requirement',
            name='type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('text',      'Text Field'),
                    ('question',  'Question'),
                    ('number',    'Number'),
                    ('date',      'Date'),
                    ('document',  'Document Upload'),
                    ('select',    'Select / Dropdown'),
                    ('boolean',   'Yes / No'),
                    ('info_text', 'Information Block'),
                ],
            ),
        ),

        # ── Step 4: Rename auto_field_form → profile_mapping ──────────
        # Same column, clearer name. Stores dot-path to a profile field.
        # Example: "profile.date_of_birth"
        # Phase 2 will implement the auto-fill logic that reads this.
        migrations.RenameField(
            model_name='requirement',
            old_name='auto_field_form',
            new_name='profile_mapping',
        ),

        # ── Step 5: Make Requirement.category nullable ────────────────
        # New library requirements won't have a category FK — they're standalone.
        # Existing requirements keep their category_id value until migration 0010 moves it.
        migrations.AlterField(
            model_name='requirement',
            name='category',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requirements',
                to='cases.category',
            ),
        ),

        # ── Step 6: Create RequirementChoice ──────────────────────────
        # Stores the dropdown options for 'select'-type requirements.
        # Example: Requirement "Gender" → choices: [Male, Female, Non-binary, ...]
        migrations.CreateModel(
            name='RequirementChoice',
            fields=[
                ('id',          models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('label',       models.CharField(max_length=100)),
                ('value',       models.CharField(max_length=100)),
                ('order',       models.PositiveIntegerField(default=0)),
                ('requirement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='choices',
                    to='cases.requirement',
                )),
            ],
            options={
                'ordering': ['order', 'label'],
            },
        ),

        # ── Step 7: Create CategoryRequirement ────────────────────────
        # The M2M bridge: one row = "this category uses this requirement".
        # Replaces the old direct FK (Requirement.category).
        # One Requirement can appear in many categories — many CategoryRequirement rows.
        migrations.CreateModel(
            name='CategoryRequirement',
            fields=[
                ('id',                   models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('order',                models.PositiveIntegerField(default=0)),
                ('is_required_override', models.BooleanField(blank=True, null=True, default=None)),
                ('category',             models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='category_requirements',
                    to='cases.category',
                )),
                ('requirement',          models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='category_requirements',
                    to='cases.requirement',
                )),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='categoryrequirement',
            unique_together={('category', 'requirement')},
        ),

        # ── Step 8: Add CaseAnswer.answer_choice FK ───────────────────
        # Stores which RequirementChoice the user selected for 'select'-type answers.
        # SET_NULL: if a choice is deleted later, the answer row survives with null.
        migrations.AddField(
            model_name='caseanswer',
            name='answer_choice',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='case_answers',
                to='cases.requirementchoice',
            ),
        ),
    ]
