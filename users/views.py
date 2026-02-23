from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout 
from .forms import LoginForm, RegisterForm

 
def login_view(request):
    form = LoginForm(request.POST or None)
    # GET request → request.POST is empty → None → blank form
    # POST request → request.POST has data → form gets data
 
    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email']
        password = form.cleaned_data['password']
 
        user = authenticate(request, email=email, password=password)
        # Returns User object if credentials valid, None if not
 
        if user:
            login(request, user)         # create session
            return redirect('dashboard') # redirect by URL name — ALWAYS after POST
        else:
            form.add_error(None, 'Invalid email or password')
            # add_error(None, ...) = form-wide error (not field-specific)
            
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')  # send back to login page

def register_view(request):
    form = RegisterForm(request.POST or None)
 
    if request.method == 'POST' and form.is_valid():
        from .models import User
        user = User.objects.create_user(
            email      = form.cleaned_data['email'],
            password   = form.cleaned_data['password1'],
            first_name = form.cleaned_data['first_name'],
            last_name  = form.cleaned_data['last_name'],
        )
        login(request, user)         # log them in automatically
        return redirect('dashboard')
 
    return render(request, 'users/register.html', {'form': form})

