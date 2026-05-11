from django.urls import path
from . import views
from .views_purchase import (
    chairman_approve_view,
    add_quotation_view,
    add_vendor_view,
    final_approve_view,
    finance_approve_view,
    stock_entry_view,
)

urlpatterns = [

    path('create/', views.create_notesheet, name='create_notesheet'),

    path('your-notes/', views.your_notesheets, name='your_notesheets'),

    path('edit/<int:pk>/', views.edit_notesheet, name='edit_notesheet'),

    # ADD THIS
    path(
    'note-file/<int:pk>/',
    views.edit_notesheet,
    name='note_file'
),

    path('inbox/', views.inbox, name='inbox'),

    path('action/<int:pk>/', views.note_action, name='note_action'),

    path('sent/', views.sent_notes, name='sent_notes'),

    path('search/', views.notesheet_search, name='notesheet_search'),

    path('detail/<int:pk>/', views.detail_note, name='detail_note'),

    path(
        'open_sent_file/<int:pk>/',
        views.open_sent_file,
        name='open_sent_file'
    ),

    path(
        'movement-history/<int:pk>/',
        views.movement_history,
        name='movement_history'
    ),

    # Chairman Approval

    path(
        'chairman-purchase-approve/<int:pk>/',
        views.chairman_purchase_approve,
        name='chairman_purchase_approve'
    ),

    path(
        'chairman-quotation-approve/<int:pk>/',
        views.chairman_quotation_approve,
        name='chairman_quotation_approve'
    ),

    path(
        'chairman-final-approve/<int:pk>/',
        views.chairman_final_approve,
        name='chairman_final_approve'
    ),

    path(
        'finance-payment-approve/<int:pk>/',
        views.finance_payment_approve,
        name='finance_payment_approve'
    ),

    path(
        'close-inventory/<int:pk>/',
        views.close_inventory,
        name='close_inventory'
    ),

    path(
    'add-quotation/<int:pk>/',
    views.add_quotation,
    name='add_quotation'
),

path(
    'add-vendor/<int:pk>/',
    views.add_vendor,
    name='add_vendor'
),
]