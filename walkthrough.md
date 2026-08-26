# របាយការណ៍សង្ខេប៖ ប្រព័ន្ធគ្រប់គ្រងសិស្សប្រឡង លើកលែងតាមខែ (ពិន្ទុ ០) & ផ្អាកបិទផ្សាយដោយសារវិន័យ

ប្រព័ន្ធត្រូវបានបង្កើត និងពង្រឹងយ៉ាងពេញលេញស្របតាមបទដ្ឋានសាលារៀន និងលក្ខខណ្ឌតម្រូវទាំងអស់៖

---

## ១. សេចក្តីសង្ខេបនៃលក្ខខណ្ឌ និងមុខងារដែលបានអនុវត្ត (Key Rules & Implemented Features)

### ក. លក្ខខណ្ឌទី១៖ យកតែសិស្សរៀនធម្មតា (`ACTIVE`) ចូលប្រឡងតេស្ត
- **ការទាញឈ្មោះស្វ័យប្រវត្តិ (`exam_pull_candidates`)**: ច្រោះយកតែសិស្សដែលមាន `status == 'ACTIVE'` តែប៉ុណ្ណោះ។ សិស្សដែល `DROPPED` (ឈប់រៀន), `SUSPENDED` (ផ្អាកការសិក្សា), `TRANSFERRED`, ឬ `GRADUATED` គឺ**មិនត្រូវបានបញ្ចូលក្នុងបញ្ជីបេក្ខជនឡើយ**។
- ពិនិត្យបញ្ជីលើកលែងសិស្ស (`ExamStudentExclusion`) មុនពេលទាញបញ្ចូល ដើម្បីកុំឱ្យមានឈ្មោះសិស្សដែលត្រូវបានកំណត់លើកលែង។

### ខ. លក្ខខណ្ឌទី២៖ ការកំណត់លើកលែងសិស្សមិនឱ្យប្រឡងតាមខែ (`ExamStudentExclusion`)
- បង្កើតទម្រង់ទិន្នន័យ `ExamStudentExclusion` សម្រាប់ Admin ឬបុគ្គលិកទទួលបន្ទុកក្នុងការជ្រើសរើសសិស្សដែលឈប់រៀន ផ្អាក ឬមានបញ្ហា មិនឱ្យមានឈ្មោះប្រឡងសម្រាប់ខែ ឬសម័យប្រឡងណាមួយ។
- ផ្ទាំងគ្រប់គ្រងលើកលែងសិស្ស **[exclusions_manage.html](file:///e:/SchoolSM/templates/examinations/exclusions_manage.html)**៖
  - ច្រោះតាម ឆ្នាំសិក្សា, សម័យប្រឡង, ខែប្រឡង, ថ្នាក់រៀន, និងមូលហេតុ។
  - Modal បង្កើតការលើកលែងថ្មី ដោយទាញទិន្នន័យសិស្សក្នុងថ្នាក់ស្វ័យប្រវត្តិតាមរយៈ AJAX។
  - ប៊ូតុងប្តូរស្ថានភាពរហ័ស (Toggle on/off) ពេលសិស្សចូលរៀនឡើងវិញ។

### គ. លក្ខខណ្ឌទី៣៖ ពិន្ទុ ០.០០ ស្វ័យប្រវត្តិ & សិទ្ធិកែប្រែពិន្ទុសម្រាប់តែ Admin
- សិស្សដែលមិនបានប្រឡង ឬត្រូវបានលើកលែង ទទួលបាន **ពិន្ទុ ០.០០ (និទ្ទេស F) ដោយស្វ័យប្រវត្តិ**។
- នៅក្នុងតារាងបញ្ចូលពិន្ទុថ្នាក់រៀន (`grade_entry_matrix`)៖
  - **គ្រូបង្រៀន (Teacher)** មិនអាចកែប្រែ ឬបញ្ចូលពិន្ទុវិជ្ជមានសម្រាប់សិស្សដែលត្រូវបានលើកលែងបានទេ (ប្រព័ន្ធចាក់សោរ `readonly/disabled`)។
  - **Admin តែម្នាក់គត់** ដែលមានសិទ្ធិកែប្រែ ឬកំណត់ពិន្ទុឡើងវិញ (Admin Override) តាមខែនីមួយៗ។
  - **ពេលសិស្សចូលរៀនវិញ**៖ ស្ថានភាពសិស្សប្រែមកជា `ACTIVE` ធម្មតា គាត់នឹងមានឈ្មោះប្រឡងនៅខែបន្ទាប់ៗជាធម្មតា ខណៈខែដែលមិនបានប្រឡងកន្លងមកនៅតែរក្សាពិន្ទុ ០.០០។

### ឃ. លក្ខខណ្ឌទី៤៖ ការផ្អាកបិទផ្សាយ & ផ្អាកចុះហត្ថលេខាដោយសារវិន័យ (Disciplinary Hold)
- បន្ថែម `is_disciplinary_blocked`, `disciplinary_reason`, `disciplinary_blocked_by`, `disciplinary_blocked_at` លើ `ExamCandidate`។
- **ផ្ទាំងគ្រប់គ្រងសម័យប្រឡង ([exam_manage.html](file:///e:/SchoolSM/templates/examinations/standardized/exam_manage.html))**៖
  - មានជួរឈរ **«ស្ថានភាពវិន័យ/កិច្ចសន្យា»** អមដោយប៊ូតុង Tick / Untick ភ្លាមៗ (AJAX) មិនបាច់ Refresh ទំព័រ។
  - របារឧបករណ៍ជ្រើសរើសច្រើននាក់ (Batch Action) ដើម្បី ដាក់វិន័យ / ដោះវិន័យ ក្នុងពេលតែមួយ។
- **បញ្ជីបិទផ្សាយតាមបន្ទប់ ([room_postings_print.html](file:///e:/SchoolSM/templates/examinations/standardized/room_postings_print.html))**៖
  - ពេលសិស្សជាប់វិន័យ (`is_disciplinary_blocked=True`)៖ ឈ្មោះ ឈ្មោះឡាតាំង ភេទ ថ្ងៃខែឆ្នាំកំណើត និងថ្នាក់ដើម ត្រូវបានលាក់ និងជំនួសដោយ៖
    > `⚠️ [ ផ្អាកបណ្តោះអាសន្ន - សូមទាក់ទងការិយាល័យវិន័យ/រដ្ឋបាល ដើម្បីធ្វើកិច្ចសន្យាមុនចូលប្រឡង ]`
- **បញ្ជីចុះហត្ថលេខាបេក្ខជន ([attendance_sheets_print.html](file:///e:/SchoolSM/templates/examinations/standardized/attendance_sheets_print.html))**៖
  - ពេលសិស្សជាប់វិន័យ (`is_disciplinary_blocked=True`)៖ ឈ្មោះបេក្ខជនបង្ហាញ `⚠️ [ ជាប់កិច្ចសន្យាវិន័យ - ផ្អាកការចុះហត្ថលេខា ]` ហើយប្រអប់ចុះហត្ថលេខាត្រូវបានចាក់សោរ `🔒 សូមទាក់ទងគណៈកម្មការ/រដ្ឋបាល`។
- **ពេលសិស្សមកធ្វើកិច្ចសន្យារួចរាល់**៖ Admin ឬបុគ្គលិកគ្រាន់តែចុច **ដោះ Tick ចេញ (Untick)** នោះឈ្មោះ និងព័ត៌មានពេញលេញរបស់សិស្សនឹងត្រូវបង្ហាញក្នុងបញ្ជីទាំងពីរវិញភ្លាមៗ អាចចូលប្រឡងបានធម្មតា។

---

## ២. បណ្តាឯកសារដែលបានបង្កើត និងកែប្រែ (Modified & Created Files)

1. [apps/examinations/models.py](file:///e:/SchoolSM/apps/examinations/models.py)
   - បន្ថែម `is_disciplinary_blocked`, `disciplinary_reason`, `disciplinary_blocked_by`, `disciplinary_blocked_at` ក្នុង `ExamCandidate`
   - បង្កើត Model `ExamStudentExclusion`
2. [apps/examinations/admin.py](file:///e:/SchoolSM/apps/examinations/admin.py)
   - ចុះឈ្មោះ `ExamStudentExclusion` និងបន្ថែម Disciplinary filters លើ `ExamCandidateAdmin`
3. [apps/examinations/views.py](file:///e:/SchoolSM/apps/examinations/views.py)
   - អាប់ដេត `grade_entry_matrix` (ពិនិត្យការលើកលែង, ពិន្ទុ ០, Admin-only override)
   - អាប់ដេត `exam_pull_candidates` (ច្រោះតែ Active & Non-excluded)
   - បន្ថែម `exam_exclusions_manage` (គ្រប់គ្រងការលើកលែងសិស្សតាមខែ)
   - បន្ថែម `api_toggle_candidate_disciplinary_hold` & `api_batch_toggle_disciplinary_hold` (Tick/Untick វិន័យ)
   - បន្ថែម `api_toggle_exam_exclusion` & `api_get_students_by_classroom`
4. [apps/examinations/urls.py](file:///e:/SchoolSM/apps/examinations/urls.py)
   - ចុះឈ្មោះផ្លូវ URL សម្រាប់ Exclusions & Disciplinary Hold APIs
5. [apps/accounts/menu_registry.py](file:///e:/SchoolSM/apps/accounts/menu_registry.py)
   - បន្ថែម MenuItem `exam_exclusions_manage` ក្នុង Menu វត្តមាន & ការប្រឡង
6. [templates/examinations/exclusions_manage.html](file:///e:/SchoolSM/templates/examinations/exclusions_manage.html)
   - ទំព័រគ្រប់គ្រងសិស្សលើកលែងមិនឱ្យប្រឡងប្រកបដោយសោភ័ណភាព និងមុខងារពេញលេញ
7. [templates/examinations/standardized/room_postings_print.html](file:///e:/SchoolSM/templates/examinations/standardized/room_postings_print.html)
   - លាក់ព័ត៌មានបេក្ខជនពេលជាប់វិន័យ
8. [templates/examinations/standardized/attendance_sheets_print.html](file:///e:/SchoolSM/templates/examinations/standardized/attendance_sheets_print.html)
   - លាក់ឈ្មោះ និងចាក់សោរប្រអប់ចុះហត្ថលេខាពេលជាប់វិន័យ
9. [templates/examinations/standardized/exam_manage.html](file:///e:/SchoolSM/templates/examinations/standardized/exam_manage.html)
   - បន្ថែមជួរឈរវិន័យ, ប៊ូតុង Toggle AJAX និង Batch Actions
10. [templates/examinations/grade_matrix.html](file:///e:/SchoolSM/templates/examinations/grade_matrix.html)
    - បង្ហាញ Badge សិស្សលើកលែង, ចាក់សោរសម្រាប់គ្រូ, និងអនុញ្ញាត Admin Override

---

## ៣. លទ្ធផលនៃការធ្វើតេស្តស្វ័យប្រវត្តិ (Automated Verification Results)

```text
🚀 Starting Automated Test for Exam Student Restrictions, Monthly Exclusions & Disciplinary Hold...
Candidate IDs pulled: [997, 993]
✅ Requirement 1 & 2 Passed: ONLY Active and Non-Excluded students are pulled into exams!
✅ Ticked disciplinary hold on «កែវ ពិសី (Discipline)» (is_disciplinary_blocked=True)
✅ Room Notice Posting List: Disciplinary student info is correctly masked/hidden!
✅ Attendance & Signature Sheet: Candidate signature is blocked!
✅ Unticked disciplinary hold on «កែវ ពិសី (Discipline)» (is_disciplinary_blocked=False)
✅ Restored Candidate: Full name and signature line are completely restored in both lists!
✅ Teacher Score Restriction Passed: Teacher cannot submit positive scores for excluded student!
✅ Admin Override Passed: Admin successfully overridden score for student!
✅ Re-enrollment Workflow Passed: Student returning to school can take new monthly exams normally!
✅ GET /examinations/exclusions/ -> 200 OK
✅ AJAX Toggle Exclusion API passed!

🎉 ALL TESTS PASSED! Active student restrictions, monthly exclusions (0-score + Admin edit), and disciplinary hold masking are 100% OPERATIONAL & VERIFIED!
```
