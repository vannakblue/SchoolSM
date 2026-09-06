from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from apps.accounts.decorators import role_required
from apps.accounts.models import SchoolProfile
from apps.extras.models import Announcement
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.academics.models import Classroom, AcademicYear
from .models import NewsArticle, GalleryAlbum, GalleryPhoto, WebsiteBanner, ContactMessage
from .forms import NewsArticleForm, GalleryAlbumForm, GalleryPhotosUploadForm, WebsiteBannerForm, ContactMessageForm


# ==============================================================================
# PUBLIC WEBSITE VIEWS (ACCESSIBLE TO ALL VISITORS WITHOUT LOGIN)
# ==============================================================================

def website_home(request):
    """
    Public School Homepage / Landing Page.
    Accessible to everyone.
    Displays school identity, announcements, news, gallery, statistics, and contact info.
    """
    school_profile = SchoolProfile.get_settings()
    
    # Homepage Banners
    banners = WebsiteBanner.objects.filter(is_active=True).order_by('order')
    
    # Urgent/Public Announcements
    announcements = Announcement.objects.filter(is_published=True, target_audience__in=['ALL', 'STUDENTS_PARENTS']).order_by('-created_at')[:5]
    
    # Featured & Latest News
    featured_news = NewsArticle.objects.filter(is_published=True, is_featured=True).first()
    latest_news = NewsArticle.objects.filter(is_published=True)
    if featured_news:
        latest_news = latest_news.exclude(pk=featured_news.pk)
    latest_news = latest_news[:6]
    
    # Photo Gallery Albums
    gallery_albums = GalleryAlbum.objects.filter(is_published=True).prefetch_related('photos')[:6]
    
    # Dynamic School Stats
    stats = {
        'students_count': Student.objects.filter(status='ACTIVE').count() or 1250,
        'teachers_count': Teacher.objects.filter(status='ACTIVE').count() or 68,
        'classrooms_count': Classroom.objects.count() or 36,
        'programs_count': 4, # Primary, Secondary, High School, Bilingual/STEM
    }

    # Contact Form for homepage footer/section
    contact_form = ContactMessageForm()

    return render(request, 'website/index.html', {
        'school_profile': school_profile,
        'banners': banners,
        'announcements': announcements,
        'featured_news': featured_news,
        'latest_news': latest_news,
        'gallery_albums': gallery_albums,
        'stats': stats,
        'contact_form': contact_form,
        'active_nav': 'home',
    })


def website_news_list(request):
    """
    Public News & Articles directory with category filter and search.
    """
    school_profile = SchoolProfile.get_settings()
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    articles = NewsArticle.objects.filter(is_published=True)

    if category:
        articles = articles.filter(category=category)
    if query:
        articles = articles.filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(content__icontains=query))

    return render(request, 'website/news_list.html', {
        'school_profile': school_profile,
        'articles': articles,
        'categories': NewsArticle.Category.choices,
        'selected_category': category,
        'query': query,
        'active_nav': 'news',
    })


def website_news_detail(request, pk):
    """
    Detailed reader view for a school news article.
    Increments view count upon each visit.
    """
    school_profile = SchoolProfile.get_settings()
    article = get_object_or_404(NewsArticle, pk=pk, is_published=True)
    
    # Increment view count
    article.views_count += 1
    article.save(update_fields=['views_count'])

    # Related articles in same category
    related_articles = NewsArticle.objects.filter(
        is_published=True,
        category=article.category
    ).exclude(pk=article.pk)[:3]

    return render(request, 'website/news_detail.html', {
        'school_profile': school_profile,
        'article': article,
        'related_articles': related_articles,
        'active_nav': 'news',
    })


def website_announcement_list(request):
    """
    Public Announcements & Notice Board.
    """
    school_profile = SchoolProfile.get_settings()
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    announcements = Announcement.objects.filter(is_published=True, target_audience__in=['ALL', 'STUDENTS_PARENTS'])

    if category:
        announcements = announcements.filter(category=category)
    if query:
        announcements = announcements.filter(Q(title__icontains=query) | Q(content__icontains=query))

    return render(request, 'website/announcement_list.html', {
        'school_profile': school_profile,
        'announcements': announcements,
        'categories': Announcement.Category.choices,
        'selected_category': category,
        'query': query,
        'active_nav': 'announcements',
    })


def website_announcement_detail(request, pk):
    """
    Detailed view of a public announcement.
    """
    school_profile = SchoolProfile.get_settings()
    announcement = get_object_or_404(Announcement, pk=pk, is_published=True)
    return render(request, 'website/announcement_detail.html', {
        'school_profile': school_profile,
        'announcement': announcement,
        'active_nav': 'announcements',
    })


def website_gallery_list(request):
    """
    Public Photo Gallery Albums list.
    """
    school_profile = SchoolProfile.get_settings()
    albums = GalleryAlbum.objects.filter(is_published=True).prefetch_related('photos')
    return render(request, 'website/gallery_list.html', {
        'school_profile': school_profile,
        'albums': albums,
        'active_nav': 'gallery',
    })


def website_album_detail(request, pk):
    """
    Detailed album photos view with interactive lightbox modal.
    """
    school_profile = SchoolProfile.get_settings()
    album = get_object_or_404(GalleryAlbum, pk=pk, is_published=True)
    photos = album.photos.all().order_by('order', 'id')
    return render(request, 'website/album_detail.html', {
        'school_profile': school_profile,
        'album': album,
        'photos': photos,
        'active_nav': 'gallery',
    })


def website_contact(request):
    """
    Contact Us page with Google Maps, school address, phone, email and inquiry form.
    """
    school_profile = SchoolProfile.get_settings()
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "សាររបស់លោកអ្នកត្រូវបានផ្ញើជូនគណៈគ្រប់គ្រងសាលារៀនដោយជោគជ័យ! យើងខ្ញុំនឹងឆ្លើយតបឆាប់ៗនេះ។")
            return redirect('website_contact')
    else:
        form = ContactMessageForm()

    return render(request, 'website/contact.html', {
        'school_profile': school_profile,
        'form': form,
        'active_nav': 'contact',
    })


def website_contact_submit(request):
    """
    Handle contact form submission from homepage or contact modal.
    """
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            msg = form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'ok', 'message': 'សារត្រូវបានផ្ញើជោគជ័យ!'})
            messages.success(request, f"អរគុណលោក/លោកស្រី {msg.name}! សាររបស់លោកអ្នកត្រូវបានផ្ញើជោគជ័យ។")
        else:
            messages.error(request, "សូមពិនិត្យព័ត៌មានដែលបានបំពេញក្នុងទម្រង់ម្តងទៀត!")
    return redirect('website_home')


# ==============================================================================
# ADMIN CMS VIEWS (ACCESSIBLE TO ADMIN / AUTHORIZED USERS IN THE WEB APP PORTAL)
# ==============================================================================

@login_required
@role_required(['ADMIN'])
def cms_news_manager(request):
    """
    Admin Management Dashboard for School News and Articles.
    """
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    articles = NewsArticle.objects.all()

    if category:
        articles = articles.filter(category=category)
    if query:
        articles = articles.filter(Q(title__icontains=query) | Q(content__icontains=query))

    return render(request, 'website/cms/news_manager.html', {
        'articles': articles,
        'categories': NewsArticle.Category.choices,
        'selected_category': category,
        'query': query,
    })


@login_required
@role_required(['ADMIN'])
def cms_news_create(request):
    """
    Create a new news article.
    """
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            messages.success(request, f"បានបង្កើតអត្ថបទព័ត៌មាន '{article.title}' ជោគជ័យ!")
            return redirect('website_news_manager')
    else:
        form = NewsArticleForm()

    return render(request, 'website/cms/news_form.html', {
        'form': form,
        'title': 'សរសេរអត្ថបទព័ត៌មានសាលាថ្មី / Create School News',
        'is_edit': False,
    })


@login_required
@role_required(['ADMIN'])
def cms_news_edit(request, pk):
    """
    Edit an existing news article.
    """
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែព័ត៌មាន '{article.title}' ជោគជ័យ!")
            return redirect('website_news_manager')
    else:
        form = NewsArticleForm(instance=article)

    return render(request, 'website/cms/news_form.html', {
        'form': form,
        'article': article,
        'title': f'កែសម្រួលព័ត៌មាន៖ {article.title}',
        'is_edit': True,
    })


@login_required
@role_required(['ADMIN'])
def cms_news_delete(request, pk):
    """
    Delete a news article.
    """
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f"បានលុបព័ត៌មាន '{title}' ដោយជោគជ័យ!")
    return redirect('website_news_manager')


@login_required
@role_required(['ADMIN'])
def cms_news_toggle_publish(request, pk):
    """
    Quickly toggle published status of an article.
    """
    article = get_object_or_404(NewsArticle, pk=pk)
    article.is_published = not article.is_published
    article.save(update_fields=['is_published'])
    status_str = "ផ្សព្វផ្សាយ" if article.is_published else "ផ្អាកការផ្សាយ"
    messages.info(request, f"បានកំណត់ '{article.title}' ទៅជា {status_str}!")
    return redirect('website_news_manager')


@login_required
@role_required(['ADMIN'])
def cms_gallery_manager(request):
    """
    Admin Management for Photo Albums and Galleries.
    """
    albums = GalleryAlbum.objects.prefetch_related('photos').all()
    upload_form = GalleryPhotosUploadForm()
    album_form = GalleryAlbumForm()

    return render(request, 'website/cms/gallery_manager.html', {
        'albums': albums,
        'upload_form': upload_form,
        'album_form': album_form,
    })


@login_required
@role_required(['ADMIN'])
def cms_gallery_create(request):
    """
    Create a new photo album.
    """
    if request.method == 'POST':
        form = GalleryAlbumForm(request.POST, request.FILES)
        if form.is_valid():
            album = form.save()
            messages.success(request, f"បានបង្កើតអាល់ប៊ុម '{album.title}' ជោគជ័យ! ឥឡូវលោកអ្នកអាចបង្ហោះរូបភាពបន្ថែម។")
            return redirect('website_gallery_manager')
    return redirect('website_gallery_manager')


@login_required
@role_required(['ADMIN'])
def cms_gallery_upload(request, pk):
    """
    Upload multiple photos to a specific album.
    """
    album = get_object_or_404(GalleryAlbum, pk=pk)
    if request.method == 'POST':
        form = GalleryPhotosUploadForm(request.POST, request.FILES)
        if form.is_valid():
            photos_list = request.FILES.getlist('photos')
            caption = form.cleaned_data.get('caption', '')
            count = 0
            for f in photos_list:
                GalleryPhoto.objects.create(album=album, image=f, caption=caption)
                count += 1
            # If album has no cover, set the first uploaded photo as cover
            if not album.cover_image and album.photos.exists():
                first_photo = album.photos.first()
                album.cover_image = first_photo.image
                album.save(update_fields=['cover_image'])
            messages.success(request, f"បានបញ្ចូលរូបភាពចំនួន {count} សន្លឹកទៅកាន់អាល់ប៊ុម '{album.title}' ជោគជ័យ!")
        else:
            messages.error(request, "ការបញ្ចូលរូបភាពបរាជ័យ សូមពិនិត្យឯកសារដែលបានជ្រើសរើស!")
    return redirect('website_gallery_manager')


@login_required
@role_required(['ADMIN'])
def cms_gallery_photo_delete(request, pk):
    """
    Delete a specific photo from an album.
    """
    photo = get_object_or_404(GalleryPhoto, pk=pk)
    album_id = photo.album_id
    if request.method == 'POST':
        photo.delete()
        messages.success(request, "បានលុបរូបភាពចេញពីអាល់ប៊ុមជោគជ័យ!")
    return redirect('website_gallery_manager')


@login_required
@role_required(['ADMIN'])
def cms_gallery_album_delete(request, pk):
    """
    Delete an entire album and its photos.
    """
    album = get_object_or_404(GalleryAlbum, pk=pk)
    if request.method == 'POST':
        title = album.title
        album.delete()
        messages.success(request, f"បានលុបអាល់ប៊ុម '{title}' និងរូបភាពទាំងអស់រួចរាល់!")
    return redirect('website_gallery_manager')


@login_required
@role_required(['ADMIN'])
def cms_messages_inbox(request):
    """
    Admin Inbox for inquiries and contact messages sent via website.
    """
    inbox_messages = ContactMessage.objects.all()
    unread_count = ContactMessage.objects.filter(is_read=False).count()

    return render(request, 'website/cms/messages_inbox.html', {
        'inbox_messages': inbox_messages,
        'unread_count': unread_count,
    })


@login_required
@role_required(['ADMIN'])
def cms_message_toggle_read(request, pk):
    """
    Toggle is_read status for a contact message.
    """
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.is_read = not msg.is_read
    msg.save(update_fields=['is_read'])
    status = "បានអាន" if msg.is_read else "មិនទាន់អាន"
    messages.info(request, f"បានកំណត់សាររបស់ {msg.name} ទៅជា '{status}'!")
    return redirect('website_messages_inbox')


@login_required
@role_required(['ADMIN'])
def cms_message_delete(request, pk):
    """
    Delete a contact message.
    """
    msg = get_object_or_404(ContactMessage, pk=pk)
    if request.method == 'POST':
        name = msg.name
        msg.delete()
        messages.success(request, f"បានលុបសាររបស់ {name} ជោគជ័យ!")
    return redirect('website_messages_inbox')
