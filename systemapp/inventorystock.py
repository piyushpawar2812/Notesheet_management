
from .models import *
from .views import *
from .models import InventoryItem


from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook

import pandas as pd


# =========================================
# INVENTORY LIST
# =========================================

def inventory_stock(request):

    search = request.GET.get('search', '')

    data = InventoryItem.objects.select_related(
            'notesheet'
        ).all().order_by('-id')

    if search:

        data = data.filter(
            item_name__icontains=search
        )

    paginator = Paginator(data, 10)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search
    }

    return render(
        request,
        'services/inventory_stock.html',
        context
    )


# =========================================
# ADD INVENTORY
# =========================================

def add_inventory_stock(request):

    if request.method == 'POST':

        InventoryItem.objects.create(

            category=request.POST.get('category'),

            item_name=request.POST.get('item_name'),

            quantity=request.POST.get('quantity'),

            price=request.POST.get('price'),

            description=request.POST.get('description'),

            supplier_name=request.POST.get('supplier_name'),

            added_date=request.POST.get('added_date')
        )

        messages.success(
            request,
            'Inventory added successfully.'
        )

        return redirect('inventory_stock')

    return redirect('inventory_stock')


# =========================================
# EXPORT EXCEL
# =========================================

def export_inventory_excel(request):

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = 'Inventory'

    headers = [
        'Category',
        'Item Name',
        'Quantity',
        'Price',
        'Supplier',
        'Received Date'
    ]

    sheet.append(headers)

    data = InventoryItem.objects.all()

    for item in data:

        sheet.append([
            item.category,
            item.item_name,
            item.quantity,
            item.price,
            item.supplier_name,
            str(item.added_date)
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    response['Content-Disposition'] = (
        'attachment; filename=inventory_stock.xlsx'
    )

    workbook.save(response)

    return response


# =========================================
# IMPORT EXCEL
# =========================================

def import_inventory_excel(request):

    if request.method == 'POST':

        excel_file = request.FILES.get('excel_file')

        if not excel_file:

            messages.error(
                request,
                'Please upload excel file.'
            )

            return redirect('inventory_stock')

        workbook = load_workbook(excel_file)

        sheet = workbook.active

        for row in sheet.iter_rows(min_row=2, values_only=True):

            InventoryItem.objects.create(

                category=row[0],

                item_name=row[1],

                quantity=row[2],

                price=row[3],

                supplier_name=row[4],

                added_date=row[5]
            )

        messages.success(
            request,
            'Excel imported successfully.'
        )

    return redirect('inventory_stock')
