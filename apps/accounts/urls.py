from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('demo-login/<str:role>/', views.demo_login_view, name='demo_login'),
    path('logout/', views.logout_view, name='logout'),
    path('redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/school/', views.school_profile_settings_view, name='school_profile_settings'),
    path('settings/telegram/', views.telegram_settings_view, name='telegram_settings'),
    path('settings/menu-permissions/', views.menu_permissions_view, name='menu_permissions'),
    path('api/menu-permissions/toggle/', views.api_toggle_menu_permission, name='api_toggle_menu_permission'),
    path('api/menu-permissions/bulk/', views.api_bulk_menu_permission, name='api_bulk_menu_permission'),
    path('api/menu-items/create/', views.api_create_menu_item, name='api_create_menu_item'),
    path('api/menu-items/<int:item_id>/edit/', views.api_edit_menu_item, name='api_edit_menu_item'),
    path('api/menu-items/<int:item_id>/delete/', views.api_delete_menu_item, name='api_delete_menu_item'),
    path('api/global-search/', views.api_global_search, name='api_global_search'),
    path('api/telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]

