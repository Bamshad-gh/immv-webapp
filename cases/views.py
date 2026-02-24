from pyexpat.errors import messages

from django.shortcuts import get_object_or_404, render , redirect
from .models import Case, CaseAnswer , Requirement , Category
from django.contrib.auth.decorators import login_required 
from django.contrib import messages  

@login_required
def user_pickedCases_dashboard(request):
    # request = the browser asking for this page
    
    picked_cases = Case.objects.filter(user=request.user)
    # go to database → get cases belonging to logged in user
    
    return render(request, 'cases/user_pickedCases_dashboard.html', {'cases': picked_cases})
#               ↑              ↑                          ↑
#               renders        which HTML file to use      data to pass to HTML
#               HTML page                                  cases = list of user's cases
#                                                      access in HTML as {{ cases }}
@login_required
def user_pickedCases_detail(request, case_id):
    # request = the browser asking for this page
    case= get_object_or_404(Case, id=case_id, user=request.user)
    requirements = case.category.requirements.all()
    
    existing_answers = CaseAnswer.objects.filter(case=case)
    answers_dict = {a.requirement.id: a for a in existing_answers}
    answers_lookup = {a.requirement.id: a for a in existing_answers}
    for req in requirements:
        req.existing_answer = answers_lookup.get(req.id)
   
    if request.method == 'POST':
    # loop through every requirement for this case's category
        for requirement in requirements:
        
            # build the key that matches the input name in the template
            # name="req_5" for requirement id=5
            key = f'req_{requirement.id}'
        
            # ── DOCUMENT — comes from request.FILES not request.POST ──
            if requirement.type == 'document':
                answer_file = request.FILES.get(key)
                # only save if user actually uploaded something
                if answer_file:
                    CaseAnswer.objects.update_or_create(
                        case=case,                        # find by case + requirement
                        requirement=requirement,          # together they identify one answer
                        defaults={'answer_file': answer_file}  # create or update this field
                    )
            
            # ── NUMBER — save to answer_number field ──────────────────
            elif requirement.type == 'number':
                answer = request.POST.get(key)
                if answer:                                # only save if not empty
                    CaseAnswer.objects.update_or_create(
                        case=case,
                        requirement=requirement,
                        defaults={'answer_number': answer}
                    )
            
            # ── DATE — save to answer_date field ──────────────────────
            elif requirement.type == 'date':
                answer = request.POST.get(key)
                if answer:
                    CaseAnswer.objects.update_or_create(
                        case=case,
                        requirement=requirement,
                        defaults={'answer_date': answer}
                    )
            
            # ── TEXT / QUESTION — save to answer_text field ───────────
            else:
                answer = request.POST.get(key)
                if answer:
                    CaseAnswer.objects.update_or_create(
                        case=case,
                        requirement=requirement,
                        defaults={'answer_text': answer}
                    )
        # massage for showing it success message after saving
        messages.success(request, 'Answers saved successfully!')
        # after saving all answers → redirect back to same page
        # POST → redirect pattern: prevents form resubmission on refresh
        return redirect('case-detail', case_id=case_id)

    return render(request, 'cases/user_pickedCases_detail.html', {
        'case':         case,
        'requirements': requirements,
        'answers_dict': answers_dict,
    })