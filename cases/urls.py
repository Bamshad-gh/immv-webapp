from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.user_pickedCases_dashboard, name='dashboard'),
    path('dashboard/<int:case_id>/', views.user_pickedCases_detail, name='case-detail'),
]