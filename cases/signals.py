from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Case, CaseAnswer

@receiver(post_save, sender=Case)
def create_case_answers(sender, instance, created, **kwargs):
    if created:  # only when NEW case is created
        # get all requirements from the assigned category
        requirements = instance.category.requirements.filter(is_active=True)
        
        for requirement in requirements:
            CaseAnswer.objects.create(
                case=instance,
                requirement=requirement,
                is_auto_filled=False
            )