from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegisterForm
from tasks.models import Notification

from django.http import JsonResponse

User = get_user_model()

def login_view(request):
    # redirect if already logged in — no point showing login page
    if request.user.is_authenticated:
        return redirect('cases:dashboard') # dashboard is first page after login

    form = LoginForm(request.POST or None)
    # POST → form gets data → can validate
    # GET  → None → blank form

    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email']
        password = form.cleaned_data['password']

        user = authenticate(request, email=email, password=password)
        # authenticate → checks credentials → returns User or None

        if user:
            login(request, user)    # create session
            # redirect to 'next' param if exists (from @login_required redirect)
            # otherwise go to dashboard
            next_url = request.GET.get('next', 'cases:dashboard')
            return redirect(next_url)
        else:
            form.add_error(None, 'Invalid email or password')
            # add_error(None, msg) = form-wide error, not field-specific

    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)     # destroy session
    return redirect('login')

def register_view(request):
    # redirect if already logged in
    if request.user.is_authenticated:
        return redirect('cases:dashboard')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(
            email      = form.cleaned_data['email'],
            password   = form.cleaned_data['password1'],
            first_name = form.cleaned_data['first_name'],
            last_name  = form.cleaned_data['last_name'],
        )
        login(request, user)    # log in automatically after register
        messages.success(request, f'Welcome, {user.first_name}!')
        return redirect('cases:dashboard')

    return render(request, 'users/register.html', {'form': form})

# ══════════════════════════════════════════════════════════════
# NOTIFICATION VIEWS (User-facing — add to users app or main views)
# ══════════════════════════════════════════════════════════════
@login_required
def notifications_list(request):
    """
    User sees all their notifications — most recent first.
    Marks all as read when this page is visited.

    Add to: users/views.py or main app views.py
    URL: /notifications/
    """
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    # Mark all as read when user opens notification page
    notifications.filter(is_read=False).update(is_read=True)

    return render(request, 'users/notifications_list.html', {
        'notifications': notifications,
    })


@login_required
def notifications_count(request):
    """
    AJAX endpoint — returns unread notification count.
    Called by the navbar badge every 30 seconds to keep the badge fresh.

    URL:     /users/notifications/count/
    Returns: { count: 5 }
    """
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    return JsonResponse({'count': count})


@login_required
def notifications_preview(request):
    """
    AJAX endpoint — returns the 5 most recent notifications as JSON.
    Called when the user clicks the bell icon to open the dropdown.

    We use select_related('task') to fetch the linked task in the same
    DB query instead of making a separate query for each notification
    (avoids the "N+1 query" performance problem).

    URL:     /users/notifications/preview/
    Returns: {
        unread_count: int,
        notifications: [
            { id, message, is_read, created_at, task_id }, ...
        ]
    }
    """
    # Get the 5 most recent notifications for this user
    recent = Notification.objects.filter(
        user=request.user
    ).select_related('task').order_by('-created_at')[:5]

    # Separate query for the total unread count (badge sync)
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id':         n.id,
                'message':    n.message,
                'is_read':    n.is_read,
                # Format: "Mar 02" — concise enough for the dropdown
                'created_at': n.created_at.strftime('%b %d'),
                # task_id is None when the notification is not task-linked
                # (e.g. invoice notifications) — JS handles null safely
                'task_id':    n.task_id,
            }
            for n in recent
        ],
    }
    return JsonResponse(data)
