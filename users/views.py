from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegisterForm

User = get_user_model()

def login_view(request):
    # redirect if already logged in — no point showing login page
    if request.user.is_authenticated:
        return redirect('dashboard') # dashboard is first page after login

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
            next_url = request.GET.get('next', 'dashboard')
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
        return redirect('dashboard')

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
        return redirect('dashboard')

    return render(request, 'users/register.html', {'form': form})