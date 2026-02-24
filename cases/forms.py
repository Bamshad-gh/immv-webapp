from django import forms

class RequirementForm(forms.BaseForm):
    """
    A dynamic form that builds its fields from database Requirement objects.

    USAGE:
        form = RequirementForm(requirements, data=request.POST, files=request.FILES, initial=initial)

    EXTEND:
        To add a new requirement type → add one line to field_map in _field_for_type()
        Nothing else needs to change.

    REUSE:
        Drop this class into any project that has a Requirement model with a 'type' field.
        Change the type names in field_map to match your model's choices.
    """

    def __init__(self, requirements, *args, **kwargs):
        # build fields BEFORE calling super().__init__()
        # because BaseForm reads base_fields during __init__
        self.base_fields = self._build_fields(requirements)
        super().__init__(*args, **kwargs)

    def _build_fields(self, requirements):
        """
        Loops through requirements and creates a Django field for each one.
        Returns a dict: {'req_5': Field, 'req_12': Field, ...}

        field name pattern: 'req_{requirement.id}'
        This name must match what the view uses to read/save answers.
        """
        fields = {}
        for req in requirements:
            field_name        = f'req_{req.id}'       # unique name per requirement
            fields[field_name] = self._field_for_type(req)
        return fields

    def _field_for_type(self, req):
        """
        Maps a requirement type string to a Django form field.

        TO ADD A NEW TYPE:
            Add one line to field_map:
            'your_type': lambda: forms.YourField(...)
            Done. Nothing else changes.

        field_map uses lambda so fields are created fresh each time
        (not shared between instances)
        """
        field_map = {
            'text': lambda: forms.CharField(
                widget=forms.Textarea(attrs={'rows': 4, 'placeholder': f'Enter {req.name}...'}),
                required=False,
                label=req.name,
                help_text=req.description or ''
            ),
            'question': lambda: forms.CharField(
                widget=forms.Textarea(attrs={'rows': 4, 'placeholder': f'Answer {req.name}...'}),
                required=False,
                label=req.name,
                help_text=req.description or ''
            ),
            'number': lambda: forms.DecimalField(
                required=False,
                label=req.name,
                help_text=req.description or '',
                widget=forms.NumberInput(attrs={'placeholder': '0.00'})
            ),
            'date': lambda: forms.DateField(
                required=False,
                label=req.name,
                help_text=req.description or '',
                widget=forms.DateInput(attrs={'type': 'date'})
                # type='date' = browser shows date picker automatically
            ),
            'document': lambda: forms.FileField(
                required=False,
                label=req.name,
                help_text=req.description or ''
            ),
        }

        # get builder for this type, fall back to CharField if unknown type
        builder = field_map.get(
            req.type,
            lambda: forms.CharField(required=False, label=req.name)
            # fallback = if someone adds a new type to the model but forgets
            # to add it here, it still works as a text field instead of crashing
        )
        return builder()  # call the lambda to create the field instance

def build_initial(existing_answers):
    """
    Builds the initial dict for prefilling the form with existing answers.

    USAGE:
        initial = build_initial(existing_answers)
        form = RequirementForm(requirements, initial=initial)

    Returns dict: {'req_5': 'existing answer', 'req_12': datetime.date(...)}
    Django uses initial= to prefill form fields automatically.
    """
    initial = {}

    # map each requirement type to the correct answer field on CaseAnswer model
    type_to_field = {
        'document': 'answer_file',
        'number':   'answer_number',
        'date':     'answer_date',
        'text':     'answer_text',
        'question': 'answer_text',
    }

    for answer in existing_answers:
        field_name    = f'req_{answer.requirement.id}'
        answer_field  = type_to_field.get(answer.requirement.type, 'answer_text')
        # getattr(obj, 'field_name') = same as obj.field_name but dynamic
        initial[field_name] = getattr(answer, answer_field)

    return initial

def save_answers(form, case, requirements):
    """
    Saves or updates CaseAnswer rows from cleaned form data.

    USAGE:
        if form.is_valid():
            save_answers(form, case, requirements)

    Separated from the view so it can be reused or tested independently.
    """
    from .models import CaseAnswer

    # map requirement type to correct CaseAnswer field
    type_to_field = {
        'document': 'answer_file',
        'number':   'answer_number',
        'date':     'answer_date',
        'text':     'answer_text',
        'question': 'answer_text',
    }

    for requirement in requirements:
        field_name = f'req_{requirement.id}'
        answer     = form.cleaned_data.get(field_name)

        if answer:  # only save if user provided a value
            answer_field = type_to_field.get(requirement.type, 'answer_text')

            CaseAnswer.objects.update_or_create(
                case=case,
                requirement=requirement,
                defaults={answer_field: answer}
                # update_or_create:
                # → row exists with case+requirement → UPDATE defaults
                # → row doesn't exist → CREATE new row
            )
