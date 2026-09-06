from django.urls import path
from . import views

urlpatterns = [
    # ------------------ Public Website Routes ------------------
    path('', views.website_home, name='website_home'),
    path('news/', views.website_news_list, name='website_news_list'),
    path('news/<int:pk>/', views.website_news_detail, name='website_news_detail'),
    path('notices/', views.website_announcement_list, name='website_announcement_list'),
    path('notices/<int:pk>/', views.website_announcement_detail, name='website_announcement_detail'),
    path('gallery/', views.website_gallery_list, name='website_gallery_list'),
    path('gallery/<int:pk>/', views.website_album_detail, name='website_album_detail'),
    path('contact/', views.website_contact, name='website_contact'),
    path('contact/submit/', views.website_contact_submit, name='website_contact_submit'),

    # ------------------ Admin CMS Management Routes ------------------
    # News & Articles
    path('portal/cms/news/', views.cms_news_manager, name='website_news_manager'),
    path('portal/cms/news/create/', views.cms_news_create, name='website_news_create'),
    path('portal/cms/news/edit/<int:pk>/', views.cms_news_edit, name='website_news_edit'),
    path('portal/cms/news/delete/<int:pk>/', views.cms_news_delete, name='website_news_delete'),
    path('portal/cms/news/toggle/<int:pk>/', views.cms_news_toggle_publish, name='website_news_toggle_publish'),

    # Photo Gallery & Albums
    path('portal/cms/gallery/', views.cms_gallery_manager, name='website_gallery_manager'),
    path('portal/cms/gallery/create/', views.cms_gallery_create, name='website_gallery_create'),
    path('portal/cms/gallery/<int:pk>/upload/', views.cms_gallery_upload, name='website_gallery_upload'),
    path('portal/cms/gallery/photo/delete/<int:pk>/', views.cms_gallery_photo_delete, name='website_gallery_photo_delete'),
    path('portal/cms/gallery/album/delete/<int:pk>/', views.cms_gallery_album_delete, name='website_gallery_album_delete'),

    # Contact Inquiries Inbox
    path('portal/cms/messages/', views.cms_messages_inbox, name='website_messages_inbox'),
    path('portal/cms/messages/toggle/<int:pk>/', views.cms_message_toggle_read, name='website_message_toggle_read'),
    path('portal/cms/messages/delete/<int:pk>/', views.cms_message_delete, name='website_message_delete'),

    # Two-Way Google Sheets Sync for Website Portal
    path('portal/cms/google-sheets/', views.cms_google_sheets_dashboard, name='website_google_sheets_dashboard'),
    path('portal/cms/google-sheets/push/', views.cms_google_sheets_push, name='website_google_sheets_push'),
    path('portal/cms/google-sheets/pull/', views.cms_google_sheets_pull, name='website_google_sheets_pull'),
]
