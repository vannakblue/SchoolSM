import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.menu_registry import sync_system_menus_to_db
from apps.website.models import NewsArticle, GalleryAlbum, GalleryPhoto, WebsiteBanner, ContactMessage
from apps.extras.models import Announcement
from apps.accounts.models import User, SchoolProfile

print("Syncing system menus to database...")
sync_system_menus_to_db()
print("Menus synced successfully!")

# Ensure SchoolProfile exists
school = SchoolProfile.get_settings()
print(f"School Profile: {school.name_kh} | Code: {school.school_code}")

admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role='ADMIN').first()

# Create sample public announcements if none exist
if not Announcement.objects.filter(target_audience='ALL').exists():
    Announcement.objects.create(
        title="សេចក្តីជូនដំណឹងស្តីពីការបើកបវេសនកាលឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧",
        category=Announcement.Category.GENERAL,
        target_audience=Announcement.TargetAudience.ALL,
        priority=Announcement.Priority.IMPORTANT,
        content="គណៈគ្រប់គ្រងសាលារៀនសូមជម្រាបជូនដំណឹងដល់មាតាបិតា អាណាព្យាបាល និងសិស្សានុសិស្សទាំងអស់ឱ្យបានជ្រាបថា ការបើកបវេសនកាលឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧ នឹងប្រព្រឹត្តទៅនៅថ្ងៃទី០១ ខែវិច្ឆិកា ឆ្នាំ២០២៦ ខាងមុខនេះ។ សូមមាតាបិតារៀបចំឯកសារ និងចុះឈ្មោះបុត្រធីតាឱ្យបានទាន់ពេលវេលា។",
        is_published=True,
        created_by=admin_user
    )
    Announcement.objects.create(
        title="កាលវិភាគប្រឡងឆមាសលើកទី១ និងការរៀបចំវិញ្ញាសា",
        category=Announcement.Category.EXAM_SCHEDULE,
        target_audience=Announcement.TargetAudience.ALL,
        priority=Announcement.Priority.URGENT,
        content="សាលារៀនសូមប្រកាសកាលវិភាគប្រឡងឆមាសទី១ សម្រាប់សិស្សានុសិស្សគ្រប់កម្រិតថ្នាក់។ ការប្រឡងនឹងចាប់ផ្តើមពីថ្ងៃច័ន្ទ ដល់ថ្ងៃសុក្រ។ សូមប្អូនៗសិស្សានុសិស្សខិតខំរំលឹកមេរៀន និងយកចិត្តទុកដាក់ខ្ពស់។",
        is_published=True,
        created_by=admin_user
    )
    print("Created sample public announcements.")

# Create sample news articles if none exist
if not NewsArticle.objects.exists():
    NewsArticle.objects.create(
        title="ពិធីអបអរសាទរទិវាគ្រូបង្រៀន និងការលើកទឹកចិត្តដល់លោកគ្រូ-អ្នកគ្រូឆ្នើមប្រចាំឆ្នាំ",
        category=NewsArticle.Category.EVENT,
        excerpt="សាលារៀនបានរៀបចំពិធីអបអរសាទរទិវាគ្រូបង្រៀនយ៉ាងអធិកអធម ដោយមានការចូលរួមពីគណៈគ្រប់គ្រង លោកគ្រូ-អ្នកគ្រូ និងសិស្សានុសិស្សរាប់រយនាក់។",
        content="""នៅព្រឹកថ្ងៃនេះ សាលារៀនបានរៀបចំកម្មវិធីទិវាគ្រូបង្រៀនពិភពលោក ដើម្បីសម្តែងនូវការដឹងគុណយ៉ាងជ្រាលជ្រៅចំពោះការលះបង់ និងការខិតខំប្រឹងប្រែងរបស់លោកគ្រូ-អ្នកគ្រូទាំងអស់។

នៅក្នុងឱកាសនោះដែរ លោកនាយកសាលាបានថ្លែងសុន្ទរកថាគន្លឹះស្តីពី 'តួនាទីរបស់គ្រូបង្រៀនក្នុងយុគសម័យឌីជីថល' ព្រមទាំងបានប្រគល់ប័ណ្ណសរសើរ និងរង្វាន់លើកទឹកចិត្តដល់លោកគ្រូ-អ្នកគ្រូឆ្នើមចំនួន ១៥ រូប ដែលមានស្នាដៃលេចធ្លោក្នុងការបង្រៀន។

កម្មវិធីនេះបានបញ្ចប់ទៅដោយក្តីសប្បាយរីករាយ និងអនុស្សាវរីយ៍ដ៏កក់ក្តៅរវាងសិស្សានុសិស្ស និងលោកគ្រូ-អ្នកគ្រូ។""",
        author=admin_user,
        views_count=128,
        is_featured=True,
        is_published=True
    )

    NewsArticle.objects.create(
        title="សិស្សានុសិស្សសាលាយើងទទួលបានមេដាយមាសក្នុងការប្រកួតគណិតវិទ្យា និង STEM ថ្នាក់ជាតិ",
        category=NewsArticle.Category.ACHIEVEMENT,
        excerpt="មោទនភាពជាទីបំផុត! ក្រុមសិស្សតំណាងសាលារៀនយើងបានដណ្តើមបានមេដាយមាស និងប្រាក់ក្នុងការប្រកួតប្រជែងជំនាញ STEM និងមនុស្សយន្តថ្នាក់ជាតិ។",
        content="""យើងខ្ញុំសូមចូលរួមអបអរសាទរយ៉ាងកក់ក្តៅចំពោះប្អូនៗសិស្សានុសិស្សដែលបានខិតខំប្រឹងប្រែងហ្វឹកហាត់ និងចូលរួមប្រកួតរហូតទទួលបានជ័យលាភីលេខ១ មេដាយមាសថ្នាក់ជាតិ។

សមិទ្ធផលនេះបានសបញ្ជាក់ពីគុណភាពនៃការអប់រំ និងការយកចិត្តទុកដាក់ខ្ពស់របស់សាលារៀនលើការបណ្តុះបណ្តាលជំនាញបច្ចេកវិទ្យា STEM, Coding និងការគិតបែបវិទ្យាសាស្ត្រ។""",
        author=admin_user,
        views_count=95,
        is_featured=False,
        is_published=True
    )

    NewsArticle.objects.create(
        title="ការដាក់ឱ្យដំណើរការបន្ទប់ពិសោធន៍កុំព្យូទ័រ និងបច្ចេកវិទ្យា AI ជំនាន់ថ្មី",
        category=NewsArticle.Category.ACADEMICS,
        excerpt="ដើម្បីឆ្លើយតបទៅនឹងការវិវត្តនៃបច្ចេកវិទ្យាសកល សាលារៀនបានសម្ពោធបន្ទប់កុំព្យូទ័រទំនើបបំពាក់ដោយប្រព័ន្ធអ៊ីនធឺណិតល្បឿនលឿន និងឧបករណ៍សិក្សា AI។",
        content="""សាលារៀនមានសេចក្តីសោមនស្សរីករាយក្នុងការប្រកាសបើកដំណើរការបន្ទប់ពិសោធន៍ឌីជីថលថ្មី ដែលមានបំពាក់កុំព្យូទ័រទំនើបចំនួន ៥០ គ្រឿង ផ្ទាំង Smart Board និងកម្មវិធីសិក្សា AI សម្រាប់ការបង្រៀន។

បន្ទប់នេះនឹងជួយឱ្យសិស្សានុសិស្សទទួលបានបទពិសោធន៍ផ្ទាល់ក្នុងការសរសេរកូដ និងការស្រាវជ្រាវតាមប្រព័ន្ធអ៊ីនធឺណិតប្រកបដោយប្រសិទ្ធភាព។""",
        author=admin_user,
        views_count=64,
        is_featured=False,
        is_published=True
    )
    print("Created sample news articles.")

# Create sample photo album if none exists
if not GalleryAlbum.objects.exists():
    album = GalleryAlbum.objects.create(
        title="ពិធីបើកបវេសនកាល និងទិវាវប្បធម៌សាលារៀន",
        description="កម្រងរូបភាពសកម្មភាពដ៏រស់រវើកក្នុងពិធីបើកបវេសនកាល និងការសម្តែងសិល្បៈវប្បធម៌របស់សិស្សានុសិស្សគ្រប់កម្រិតថ្នាក់។",
        is_published=True
    )
    print(f"Created sample gallery album: {album.title}")

print("All database sync and initial data completed successfully!")
