from django.urls import path
from . import views
from systemapp import inventorystock

from .user_creation import *
from .inventorystock import (
    inventory_stock,
    export_inventory_excel,
    import_inventory_excel
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
    "notesheet/<int:pk>/delete/",
    views.delete_notesheet,
    name="delete_notesheet",
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

    # path(
    #     'chairman-quotation-approve/<int:pk>/',
    #     views.chairman_quotation_approve,
    #     name='chairman_quotation_approve'
    # ),

#     path(
#     'quotation-revert/<int:pk>/',
#     views.chairman_quotation_revert,
#     name='chairman_quotation_revert'
# ),


# path(
#     'send-quotation-chairman/<int:pk>/',
#     views.send_quotation_to_chairman,
#     name='send_quotation_to_chairman'
# ),



    path(
    'add-quotation/<int:pk>/',
    views.add_quotation,
    name='add_quotation'
),


    path('select-vendor-winner/<int:vendor_id>/',
         views.select_vendor_winner,
         name='select_vendor_winner'),

    
path(
    'quotation-details/<int:pk>/',
    views.quotation_details,
    name='quotation_details'
),




path(
    'generate-po/<int:pk>/',
    views.generate_po,
    name='generate_po'
),
path(
    'inventory-received/<int:pk>/',
    views.inventory_received,
    name='inventory_received'
),


# path(
#     'finance-send-chairman/<int:pk>/',
#     views.finance_send_to_chairman,
#     name='finance_send_to_chairman'
# ),

path(
    'chairman_billing_approve/<int:pk>/',
    views.chairman_billing_approve,
    name='chairman_billing_approve'
),

path(
    'finance-final-approve/<int:pk>/',
    views.finance_final_approve,
    name='finance_final_approve'
),




path(
    'inventory-stock/',
    inventorystock.inventory_stock,
    name='inventory_stock'
),

path(
    'export-inventory-excel/',
    inventorystock.export_inventory_excel,
    name='export_inventory_excel'
),

path(
    'import-inventory-excel/',
    inventorystock.import_inventory_excel,
    name='import_inventory_excel'
),

path(
    'dashboard-view/',
    views.dashboard_view,
    name='dashboard_view'
),




 path(
        'users/',
        user_list,
        name='user_list'
    ),

    path(
        'users/add/',
        user_save,
        name='user_add'
    ),

    path(
        'users/edit/<int:pk>/',
        user_save,
        name='user_edit'
    ),

    path(
        'users/delete/<int:pk>/',
        user_delete,
        name='user_delete'
    ),




]