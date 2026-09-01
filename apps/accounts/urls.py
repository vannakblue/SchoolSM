from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('demo-login/<str:role>/', views.demo_login_view, name='demo_login'),
    path('init-admin/', views.init_admin_view, name='init_admin'),
    path('logout/', views.logout_view, name='logout'),
    path('set-language/', views.set_language_preference_view, name='set_language_preference'),
    path('redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/request-change/', views.teacher_request_profile_change, name='teacher_request_profile_change'),
    path('api/change-password/', views.api_change_password, name='api_change_password'),
    path('settings/school/', views.school_profile_settings_view, name='school_profile_settings'),
    path('settings/telegram/', views.telegram_settings_view, name='telegram_settings'),
    path('settings/menu-permissions/', views.menu_permissions_view, name='menu_permissions'),
    path('users/', views.user_management_view, name='user_management'),
    path('api/users/create/', views.api_create_user, name='api_create_user'),
    path('api/users/<int:user_id>/edit/', views.api_edit_user, name='api_edit_user'),
    path('api/users/<int:user_id>/reset-password/', views.api_reset_password, name='api_reset_password'),
    path('api/users/<int:user_id>/toggle-active/', views.api_toggle_user_active, name='api_toggle_user_active'),
    path('api/users/<int:user_id>/delete/', views.api_delete_user, name='api_delete_user'),
    path('api/menu-permissions/toggle/', views.api_toggle_menu_permission, name='api_toggle_menu_permission'),
    path('api/menu-permissions/bulk/', views.api_bulk_menu_permission, name='api_bulk_menu_permission'),
    path('api/menu-items/create/', views.api_create_menu_item, name='api_create_menu_item'),
    path('api/menu-items/<int:item_id>/edit/', views.api_edit_menu_item, name='api_edit_menu_item'),
    path('api/menu-items/<int:item_id>/delete/', views.api_delete_menu_item, name='api_delete_menu_item'),
    path('api/global-search/', views.api_global_search, name='api_global_search'),
    path('api/pop-chat/send/', views.api_pop_chat_send, name='api_pop_chat_send'),
    path('api/pop-chat/history/', views.api_pop_chat_history, name='api_pop_chat_history'),
    path('api/pop-chat/threads/', views.api_pop_chat_threads, name='api_pop_chat_threads'),
    path('api/telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]

