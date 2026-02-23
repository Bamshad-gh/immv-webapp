from django.shortcuts import render
from .models import Case, CaseAnswer
from django.contrib.auth.decorators import login_required

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
    
    picked_cases_detail = CaseAnswer.objects.filter(case__id=case_id, case__user=request.user)
    # go to database → get cases belonging to logged in user
    
    return render(request, 'cases/user_pickedCases_detail.html', {'cases': picked_cases_detail})
#               ↑              ↑                          ↑
#               renders        which HTML file to use      data to pass to HTML
#               HTML page                                  cases = list of user's cases
#                                                      access in HTML as {{ cases }}
