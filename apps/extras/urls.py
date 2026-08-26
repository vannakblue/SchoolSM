from django.urls import path
from . import views

urlpatterns = [
    # Library
    path('library/', views.book_list, name='book_list'),
    path('library/borrow/', views.book_borrow_list, name='book_borrow_list'),
    path('library/return/<int:pk>/', views.book_return, name='book_return'),

    # Inventory
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/transaction/', views.inventory_transaction_create, name='inventory_transaction_create'),

    # Announcements
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/create/', views.announcement_create, name='announcement_create'),
    path('announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
]
