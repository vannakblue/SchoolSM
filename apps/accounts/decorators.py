from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .menu_registry import is_menu_allowed

def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Super admin has global access to everything
            if request.user.is_superuser or request.user.role == 'ADMIN':
                return view_func(request, *args, **kwargs)
                
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
                
            messages.error(request, "លោកអ្នកមិនមានសិទ្ធិចូលមើលទំព័រនេះទេ! (Access Denied)")
            return redirect('dashboard_redirect')
        return _wrapped_view
    return decorator


def menu_permission_required(menu_key: str):
    """
    Decorator to enforce that the current user's role has permission to access the given menu_key.
    Super admin always has access.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if is_menu_allowed(request.user, menu_key):
                return view_func(request, *args, **kwargs)
                
            messages.error(request, "លោកអ្នកមិនមានសិទ្ធិចូលប្រើប្រាស់មុខងារនេះទេ! (Permission Denied)")
            return redirect('dashboard_redirect')
        return _wrapped_view
    return decorator
