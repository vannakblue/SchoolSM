from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timedelta
from apps.accounts.decorators import role_required
from apps.accounts.utils import send_telegram_notification
from .models import Book, BookBorrowing, InventoryItem, InventoryTransaction, Announcement
from .forms import BookForm, BookBorrowingForm, InventoryItemForm, InventoryTransactionForm, AnnouncementForm

# ----------------- LIBRARY MODULE -----------------

@login_required
def book_list(request):
    query = request.GET.get('q', '').strip()
    books = Book.objects.all()

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query) |
            Q(category__icontains=query)
        )

    if request.method == 'POST' and (request.user.is_superuser or request.user.role == 'ADMIN'):
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.available_quantity = book.quantity
            book.save()
            messages.success(request, f"បានបន្ថែមសៀវភៅ {book.title} ជោគជ័យ!")
            return redirect('book_list')
    else:
        form = BookForm()

    return render(request, 'extras/book_list.html', {
        'books': books,
        'form': form,
        'query': query,
    })


@login_required
def book_borrow_list(request):
    borrowings = BookBorrowing.objects.select_related('book', 'student', 'teacher').all()
    status_filter = request.GET.get('status', '')

    if status_filter:
        borrowings = borrowings.filter(status=status_filter)

    if request.method == 'POST' and (request.user.is_superuser or request.user.role in ['ADMIN', 'TEACHER']):
        form = BookBorrowingForm(request.POST)
        if form.is_valid():
            borrow = form.save(commit=False)
            if borrow.book.available_quantity <= 0:
                messages.error(request, "សៀវភៅនេះត្រូវបានខ្ចីអស់ហើយ មិនមានសល់ក្នុងស្តុកទេ!")
                return redirect('book_borrow_list')
            borrow.save()
            messages.success(request, f"បានកត់ត្រាការខ្ចីសៀវភៅ {borrow.book.title} ជោគជ័យ!")
            return redirect('book_borrow_list')
    else:
        due_default = (datetime.now() + timedelta(days=14)).date()
        form = BookBorrowingForm(initial={'due_date': due_default})

    return render(request, 'extras/book_borrow_list.html', {
        'borrowings': borrowings,
        'form': form,
        'statuses': BookBorrowing.Status.choices,
        'status_filter': status_filter,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def book_return(request, pk):
    borrow = get_object_or_404(BookBorrowing, pk=pk)
    borrow.status = BookBorrowing.Status.RETURNED
    borrow.return_date = datetime.now().date()
    borrow.save()
    messages.success(request, f"បានទទួលសៀវភៅ {borrow.book.title} មកវិញរួចរាល់!")
    return redirect('book_borrow_list')


# ----------------- INVENTORY MODULE -----------------

@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def inventory_list(request):
    items = InventoryItem.objects.all()
    category_filter = request.GET.get('category', '')
    query = request.GET.get('q', '').strip()

    if category_filter:
        items = items.filter(category=category_filter)
    if query:
        items = items.filter(Q(name__icontains=query) | Q(item_code__icontains=query))

    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"បានបន្ថែមសម្ភារៈ {item.name} ជោគជ័យ!")
            return redirect('inventory_list')
    else:
        form = InventoryItemForm()

    return render(request, 'extras/inventory_list.html', {
        'items': items,
        'form': form,
        'categories': InventoryItem.Category.choices,
        'selected_category': category_filter,
        'query': query,
    })


@login_required
@role_required(['ADMIN', 'ACCOUNTANT'])
def inventory_transaction_create(request):
    if request.method == 'POST':
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            trans = form.save()
            messages.success(request, f"បានកត់ត្រាប្រតិបត្តិការ {trans.get_transaction_type_display()} ចំនួន {trans.quantity} {trans.item.name} ជោគជ័យ!")
            return redirect('inventory_list')
    else:
        item_id = request.GET.get('item')
        initial = {'item': item_id} if item_id else {}
        form = InventoryTransactionForm(initial=initial)

    return render(request, 'extras/inventory_transaction_form.html', {'form': form, 'title': 'កត់ត្រាប្រតិបត្តិការស្តុក / Inventory Stock Transaction'})


# ----------------- ANNOUNCEMENTS MODULE -----------------

@login_required
def announcement_list(request):
    user = request.user
    announcements = Announcement.objects.filter(is_published=True)

    if user.role == 'TEACHER':
        announcements = announcements.filter(target_audience__in=['ALL', 'TEACHERS'])
    elif user.role == 'STUDENT':
        announcements = announcements.filter(target_audience__in=['ALL', 'STUDENTS_PARENTS', 'PARENTS_ONLY'])

    category_filter = request.GET.get('category', '')
    if category_filter:
        announcements = announcements.filter(category=category_filter)

    return render(request, 'extras/announcement_list.html', {
        'announcements': announcements,
        'categories': Announcement.Category.choices,
        'selected_category': category_filter,
        'is_admin': user.is_superuser or user.role == 'ADMIN',
    })


@login_required
@role_required(['ADMIN'])
def announcement_create(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.created_by = request.user
            ann.save()

            if form.cleaned_data.get('broadcast_telegram'):
                telegram_text = f"📢 *{ann.title}*\n\n{ann.content[:300]}..."
                send_telegram_notification(
                    title=f"📢 សេចក្តីជូនដំណឹងសាលា: {ann.title}",
                    message=telegram_text,
                    recipient_name=ann.get_target_audience_display(),
                    recipient_type="Broadcast"
                )

            messages.success(request, f"✅ បានបង្កើត និងផ្សព្វផ្សាយសេចក្តីជូនដំណឹង '{ann.title}' ជោគជ័យ!")
            return redirect('announcement_list')
    else:
        form = AnnouncementForm()

    return render(request, 'extras/announcement_form.html', {'form': form, 'title': 'បង្កើតសេចក្តីជូនដំណឹងសាលារៀនថ្មី'})


@login_required
def announcement_detail(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    return render(request, 'extras/announcement_detail.html', {'announcement': ann})
