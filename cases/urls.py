from django.urls import path
from . import views

app_name = 'cases'
urlpatterns = [
# Dashboard — lists personal, group, and managed cases
path(
'',
views.user_pickedCases_dashboard,
name='dashboard'
),
# Single case — fill requirements
path(
    '<int:case_id>/',
    views.user_pickedCases_detail,
    name='case-detail'
),

# EXPAND: add new URL patterns here as new case views are added
]