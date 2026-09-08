"""
Seeds standard MoEYS enrollment options across GradeLevels (7, 8, 9, 10, 11, 12).
Admin can edit, reorder, customize, or delete these options from grade_options_manager.
"""

from django.core.management.base import BaseCommand
from apps.academics.models import GradeLevel, GradeEnrollmentOption

class Command(BaseCommand):
    help = "Seeds default MoEYS grade enrollment options across grade levels"

    def handle(self, *args, **options):
        self.stdout.write("Seeding standard MoEYS grade enrollment options...")

        grade_levels = GradeLevel.objects.all().order_by('grade_number')
        if not grade_levels.exists():
            self.stderr.write("No GradeLevels found in database. Please setup grade levels first.")
            return

        total_seeded = 0

        for gl in grade_levels:
            gn = gl.grade_number
            existing_names = set(gl.enrollment_options.values_list('field_name', flat=True))

            # 1. Section Header: ព័ត៌មានសិក្សាដើម & គន្លង
            if 'sec_academic_origin' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="ព័ត៌មានសិក្សាពីមុន & គន្លងអប់រំ",
                    field_name="sec_academic_origin",
                    field_type=GradeEnrollmentOption.FieldType.SECTION,
                    col_width=12,
                    order=1
                )
                total_seeded += 1

            # 2. Previous school
            if gn in [7, 8, 9]:
                if 'primary_school' not in existing_names:
                    GradeEnrollmentOption.objects.create(
                        grade_level=gl,
                        label="មកពីសាលាបឋមសិក្សា (Primary School Origin)",
                        field_name="primary_school",
                        field_type=GradeEnrollmentOption.FieldType.TEXT,
                        col_width=6,
                        placeholder="ឧ. បឋមសិក្សា ហ៊ុន សែន...",
                        order=2
                    )
                    total_seeded += 1
            else:
                if 'secondary_school' not in existing_names:
                    GradeEnrollmentOption.objects.create(
                        grade_level=gl,
                        label="មកពីគ្រឹះស្ថានមធ្យមសិក្សា (Secondary School Origin)",
                        field_name="secondary_school",
                        field_type=GradeEnrollmentOption.FieldType.TEXT,
                        col_width=6,
                        placeholder="ឧ. អនុវិទ្យាល័យ / វិទ្យាល័យ...",
                        order=2
                    )
                    total_seeded += 1

            # 3. Track (for Grade 11 & 12)
            if gn in [11, 12]:
                if 'track' not in existing_names:
                    GradeEnrollmentOption.objects.create(
                        grade_level=gl,
                        label="គន្លងអប់រំ (Educational Track)",
                        field_name="track",
                        field_type=GradeEnrollmentOption.FieldType.RADIO,
                        col_width=6,
                        choices="គន្លងវិទ្យាសាស្ត្រ, គន្លងវិទ្យាសាស្ត្រសង្គម, គន្លងវិជ្ជាជីវៈ",
                        is_required=True,
                        order=3
                    )
                    total_seeded += 1

            # 4. Section Header: សមធម៌ & ស្ថានភាពសង្គម
            if 'sec_equity' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="ព័ត៌មានសមធម៌ សុខភាព & ស្ថានភាពសង្គម",
                    field_name="sec_equity",
                    field_type=GradeEnrollmentOption.FieldType.SECTION,
                    col_width=12,
                    order=10
                )
                total_seeded += 1

            # 5. Equity Card
            if 'equity_card' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="បណ្ណសមធម៌ (IDPoor Card)",
                    field_name="equity_card",
                    field_type=GradeEnrollmentOption.FieldType.SELECT,
                    col_width=6,
                    choices="មិនមាន, ប្រភេទ១ (ក្រ១), ប្រភេទ២ (ក្រ២)",
                    order=11
                )
                total_seeded += 1

            # 6. Risk Card
            if 'risk_card' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="បណ្ណហានិភ័យ (At-Risk Card)",
                    field_name="risk_card",
                    field_type=GradeEnrollmentOption.FieldType.SELECT,
                    col_width=6,
                    choices="មិនមាន, មានបណ្ណហានិភ័យ",
                    order=12
                )
                total_seeded += 1

            # 7. Orphan status
            if 'orphan_status' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="ស្ថានភាពកំព្រា (Orphan Status)",
                    field_name="orphan_status",
                    field_type=GradeEnrollmentOption.FieldType.SELECT,
                    col_width=6,
                    choices="មិនកំព្រា, កំព្រាឪពុក, កំព្រាម្តាយ, កំព្រាទាំងពីរ",
                    order=13
                )
                total_seeded += 1

            # 8. Disability
            if 'disability_type' not in existing_names:
                GradeEnrollmentOption.objects.create(
                    grade_level=gl,
                    label="ស្ថានភាពសុខភាព / ពិការភាព (Disability Status)",
                    field_name="disability_type",
                    field_type=GradeEnrollmentOption.FieldType.SELECT,
                    col_width=6,
                    choices="ធម្មតា, បាត់បង់សប្បទា, ខ្សោយគំឃើញ, ខ្សោយស្ដាប់",
                    order=14
                )
                total_seeded += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {total_seeded} MoEYS grade enrollment options!"))
