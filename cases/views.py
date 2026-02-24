from pyexpat.errors import messages
from .forms import RequirementForm, build_initial, save_answers
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
    # ── GET DATA ──────────────────────────────────────────────
    case             = get_object_or_404(Case, id=case_id, user=request.user)
    requirements     = case.category.requirements.all()
    existing_answers = CaseAnswer.objects.filter(case=case)
    initial          = build_initial(existing_answers)  # prefill dict

    # ── POST — validate and save ──────────────────────────────
    if request.method == 'POST':
        form = RequirementForm(
            requirements,
            data=request.POST,
            files=request.FILES,
            initial=initial
        )
        if form.is_valid():
            save_answers(form, case, requirements)  # all save logic in forms.py
            messages.success(request, 'Answers saved successfully!')
            return redirect('case-detail', case_id=case_id)

    # ── GET — show prefilled form ─────────────────────────────
    else:
        form = RequirementForm(requirements, initial=initial)

    return render(request, 'cases/user_pickedCases_detail.html', {
        'case': case,
        'form': form,
    })