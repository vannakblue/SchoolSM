import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from decimal import Decimal
from django.test import Client
from django.contrib.auth import get_user_model
from apps.finance.models import FeeCategory, Invoice
from apps.students.models import Student
from apps.academics.models import Classroom, AcademicYear, GradeLevel

User = get_user_model()

def run_tests():
    print("=================================================================")
    print("🚀 RUNNING FEE CATEGORY & EXPENDITURE PURPOSE CRUD TEST SUITE")
    print("=================================================================")

    # 1. Setup Admin User & Academic Environment
    admin_user, _ = User.objects.get_or_create(
        username='admin_test_finance',
        defaults={
            'role': 'ADMIN',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    admin_user.set_password('AdminTest123!')
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    logged_in = client.login(username='admin_test_finance', password='AdminTest123!')
    assert logged_in, "Admin user must successfully log in"
    print("✅ Admin user authenticated successfully.")

    academic_year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'is_active': True}
    )
    classroom = Classroom.objects.filter(academic_year=academic_year).first()
    if not classroom:
        classroom = Classroom.objects.create(
            name='ថ្នាក់ទី ៧A',
            code='7A',
            academic_year=academic_year,
            grade_level=7
        )
    student, _ = Student.objects.get_or_create(
        student_id='STU-CRUD-999',
        defaults={
            'khmer_name': 'សុខ ពិសិដ្ឋ',
            'latin_name': 'Sok Piseth',
            'gender': 'M',
            'date_of_birth': '2012-05-15',
            'classroom': classroom
        }
    )
    student.classroom = classroom
    student.save()

    # 2. Test Admin Creating Fee Categories (បន្ថែមអត្ថន័យចំណាយ)
    # A. Early Year Enrollment Fee (ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ)
    cat_enrollment = FeeCategory.objects.create(
        name='ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ ២០២៦-២០២៧',
        category_type=FeeCategory.CategoryType.ENROLLMENT,
        default_amount=Decimal('25.00'),
        applicable_grade_note='សម្រាប់សិស្សចុះឈ្មោះថ្មីថ្នាក់ទី ៧',
        description='សេវាចុះឈ្មោះ សៀវភៅតាមដាន កាតសិស្ស និងឯកសាររដ្ឋបាល',
        is_active=True
    )
    print(f"✅ Created Fee Category: '{cat_enrollment.name}' with Type: '{cat_enrollment.category_type}'")

    # B. School Contribution (វិភាគទានសាលារៀន)
    cat_contribution = FeeCategory.objects.create(
        name='វិភាគទានសាលារៀនប្រចាំឆ្នាំ',
        category_type=FeeCategory.CategoryType.CONTRIBUTION,
        default_amount=Decimal('15.00'),
        applicable_grade_note='គ្រប់កម្រិតថ្នាក់',
        description='មូលនិធិគាំទ្រកែលម្អថ្នាក់រៀន បណ្ណាល័យ និងបរិស្ថានសិក្សា',
        is_active=True
    )
    print(f"✅ Created Fee Category: '{cat_contribution.name}' with Type: '{cat_contribution.category_type}'")

    # 3. Test Clarified Purpose on Student Invoices
    import datetime
    inv1 = Invoice.objects.create(
        student=student,
        fee_category=cat_enrollment,
        academic_year=academic_year,
        original_amount=Decimal('25.00'),
        due_date=datetime.date(2026, 10, 1)
    )
    purpose1 = inv1.get_clarified_purpose()
    print(f"📄 Invoice 1 Clarified Purpose: {purpose1}")
    assert 'ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ' in purpose1
    assert 'សេវាចុះឈ្មោះ សៀវភៅតាមដាន កាតសិស្ស' in purpose1
    assert '7A' in purpose1 or 'ថ្នាក់' in purpose1

    inv2 = Invoice.objects.create(
        student=student,
        fee_category=cat_contribution,
        academic_year=academic_year,
        original_amount=Decimal('15.00'),
        due_date=datetime.date(2026, 10, 1)
    )
    purpose2 = inv2.get_clarified_purpose()
    print(f"📄 Invoice 2 Clarified Purpose: {purpose2}")
    assert 'វិភាគទានសាលារៀន' in purpose2
    assert 'មូលនិធិគាំទ្រកែលម្អថ្នាក់រៀន' in purpose2

    # 4. Test Admin Editing Fee Category Purpose (កែប្រែអត្ថន័យចំណាយ)
    # Admin modifies description and default amount
    cat_contribution.description = 'មូលនិធិអភិវឌ្ឍន៍បច្ចេកវិទ្យា កុំព្យូទ័រ និងបណ្ណាល័យឌីជីថល'
    cat_contribution.default_amount = Decimal('20.00')
    cat_contribution.save()

    inv2.refresh_from_db()
    updated_purpose2 = inv2.get_clarified_purpose()
    print(f"✏️ Updated Invoice 2 Clarified Purpose: {updated_purpose2}")
    assert 'បច្ចេកវិទ្យា កុំព្យូទ័រ និងបណ្ណាល័យឌីជីថល' in updated_purpose2
    print("✅ Admin edit successfully reflected dynamically across invoices!")

    # 5. Test Admin Toggling Active / Inactive (បើក / ផ្អាក)
    cat_temp = FeeCategory.objects.create(
        name='កម្រៃបណ្តោះអាសន្ន',
        category_type=FeeCategory.CategoryType.OTHER,
        default_amount=Decimal('5.00'),
        is_active=True
    )
    assert cat_temp.is_active is True
    # Toggle to Inactive via view
    response_toggle = client.get(f'/finance/fee-categories/{cat_temp.pk}/toggle-active/')
    assert response_toggle.status_code == 302
    cat_temp.refresh_from_db()
    assert cat_temp.is_active is False
    print("✅ Toggle Active -> Inactive verified.")

    # Toggle back to Active
    client.get(f'/finance/fee-categories/{cat_temp.pk}/toggle-active/')
    cat_temp.refresh_from_db()
    assert cat_temp.is_active is True
    print("✅ Toggle Inactive -> Active verified.")

    # 6. Test Admin Delete Authority (លុបអត្ថន័យចំណាយ)
    # A. Delete category WITHOUT invoices -> Hard delete
    cat_temp_id = cat_temp.pk
    response_del = client.post(f'/finance/fee-categories/{cat_temp_id}/delete/')
    assert response_del.status_code == 302
    assert not FeeCategory.objects.filter(pk=cat_temp_id).exists()
    print("✅ Deletion of unlinked fee category succeeded completely.")

    # B. Delete category WITH invoices -> Safe Deactivation
    cat_enrollment_id = cat_enrollment.pk
    assert cat_enrollment.invoice_count > 0
    response_safe_del = client.post(f'/finance/fee-categories/{cat_enrollment_id}/delete/')
    assert response_safe_del.status_code == 302
    cat_enrollment.refresh_from_db()
    assert cat_enrollment.is_active is False
    assert FeeCategory.objects.filter(pk=cat_enrollment_id).exists()
    print("✅ Safe deactivation of fee category with attached invoices verified (Accounting ledger preserved).")

    # 7. Test Web UI Endpoints
    # GET list
    resp_list = client.get('/finance/fee-categories/')
    assert resp_list.status_code == 200
    assert 'វិភាគទានសាលារៀន' in resp_list.content.decode('utf-8')
    print("✅ Fee Category List Web UI rendered with HTTP 200.")

    # POST Create from Web UI
    resp_create = client.post('/finance/fee-categories/', {
        'name': 'ថ្លៃឯកសណ្ឋាន និងកាតសិស្សថ្មី',
        'category_type': 'UNIFORM',
        'default_amount': '18.50',
        'applicable_grade_note': 'សិស្សថ្មីទាំងអស់',
        'description': 'ឯកសណ្ឋាន ២ កំប្លេ រួមទាំងស្លាកឈ្មោះ',
        'is_active': 'on'
    })
    assert resp_create.status_code == 302
    created_uniform = FeeCategory.objects.filter(name='ថ្លៃឯកសណ្ឋាន និងកាតសិស្សថ្មី').first()
    assert created_uniform is not None
    assert created_uniform.default_amount == Decimal('18.50')
    print("✅ Web UI Category Creation verified.")

    # POST Edit from Web UI
    resp_edit = client.post(f'/finance/fee-categories/{created_uniform.pk}/edit/', {
        'name': 'ថ្លៃឯកសណ្ឋានផ្លូវការ និងកាតសិស្សថ្មី',
        'category_type': 'UNIFORM',
        'default_amount': '19.00',
        'applicable_grade_note': 'សិស្សថ្មីទាំងអស់',
        'description': 'ឯកសណ្ឋាន ២ កំប្លេ រួមទាំងស្លាកឈ្មោះ និងកាតស្កេនវត្តមាន',
        'is_active': 'on'
    })
    assert resp_edit.status_code == 302
    created_uniform.refresh_from_db()
    assert created_uniform.name == 'ថ្លៃឯកសណ្ឋានផ្លូវការ និងកាតសិស្សថ្មី'
    assert created_uniform.default_amount == Decimal('19.00')
    print("✅ Web UI Category Edit verified.")

    # Clean up test artifacts
    inv1.delete()
    inv2.delete()
    cat_enrollment.delete()
    cat_contribution.delete()
    created_uniform.delete()
    student.delete()
    admin_user.delete()

    print("=================================================================")
    print("🎉 ALL TESTS PASSED! ADMIN FEE CATEGORY CRUD FULLY OPERATIONAL!")
    print("=================================================================")

if __name__ == '__main__':
    run_tests()
