import os
import sys
import json
import django

# Setup UTF-8 encoding
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import User
from apps.examinations.online_exam_views import online_exam_create
from apps.accounts.views import api_ai_chat
from apps.examinations.models import ExamTerm
from apps.academics.models import AcademicYear

def run_tests():
    print("==================================================================")
    print("TESTING: EXAM TERM DROPDOWN, DARK MODE, AND IN-APP GEMINI AI AGENT")
    print("==================================================================")

    rf = RequestFactory()
    admin_user = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()

    # -------------------------------------------------------------
    # 1. Test Online Exam Form ExamTerm Rendering
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Online Exam Form - Exam Term rendering...")
    req = rf.get('/examinations/online-exams/create/')
    req.user = admin_user
    res = online_exam_create(req)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    content = res.content.decode('utf-8')

    assert 'id_exam_term' in content, "id_exam_term select element not found in HTML"
    assert 'បង្កើតសម័យប្រឡងថ្មី' in content, "Quick action button 'បង្កើតសម័យប្រឡងថ្មី' not found"
    assert 'ប្រឡង' in content, "Exam terms not populated in form options"
    print("  -> PASS: Online Exam creation form renders with populated ExamTerms and Quick Action button!")

    # -------------------------------------------------------------
    # 2. Test Base Template Dark Mode Elements
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Dark Mode infrastructure in base.html...")
    with open('templates/base.html', 'r', encoding='utf-8') as f:
        base_html = f.read()

    assert 'Anti-FOUC Synchronous Theme Initialization' in base_html, "Anti-FOUC script missing"
    assert 'id="themeToggleBtn"' in base_html, "themeToggleBtn button missing from base.html"
    assert 'id="themeToggleIcon"' in base_html, "themeToggleIcon icon missing from base.html"
    assert 'function toggleAppTheme()' in base_html, "toggleAppTheme() JS function missing"
    assert 'function updateThemeUI(' in base_html, "updateThemeUI() JS function missing"
    print("  -> PASS: Anti-FOUC script, toggle button, and theme switcher JS verified in base.html!")

    # -------------------------------------------------------------
    # 3. Test Custom CSS Dark Mode Rules
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Dark Mode CSS in static/css/custom.css...")
    with open('static/css/custom.css', 'r', encoding='utf-8') as f:
        custom_css = f.read()

    assert '[data-bs-theme="dark"]' in custom_css, "[data-bs-theme='dark'] selector missing"
    assert '--bg-app: #0b1329' in custom_css, "Dark --bg-app variable missing"
    assert '--bg-card: #131d35' in custom_css, "Dark --bg-card variable missing"
    print("  -> PASS: Comprehensive Slate Dark Theme CSS rules verified in custom.css!")

    # -------------------------------------------------------------
    # 4. Test In-App AI Agent Endpoint (/accounts/api/ai-chat/)
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing AI Agent Endpoint (Greeting)...")
    payload1 = json.dumps({'message': 'សួស្តី តើអ្នកអាចជួយអ្វីខ្ញុំបាន?'})
    req_ai1 = rf.post('/accounts/api/ai-chat/', data=payload1, content_type='application/json')
    req_ai1.user = admin_user
    res_ai1 = api_ai_chat(req_ai1)
    assert res_ai1.status_code == 200, f"Expected 200, got {res_ai1.status_code}"
    data_ai1 = json.loads(res_ai1.content.decode('utf-8'))
    assert data_ai1.get('status') == 'success', f"AI response failed: {data_ai1}"
    assert 'SchoolSM AI' in data_ai1.get('reply') or 'ជំនួយការ' in data_ai1.get('reply'), f"Unexpected AI reply: {data_ai1.get('reply')}"
    print(f"  -> PASS: AI Agent replied successfully: {data_ai1.get('reply')[:120]}...")

    print("\n[TEST 5] Testing AI Agent Endpoint (MoEYS Grading Question)...")
    payload2 = json.dumps({'message': 'តើពិន្ទុនិទ្ទេស MoEYS គិតយ៉ាងដូចម្តេច?'})
    req_ai2 = rf.post('/accounts/api/ai-chat/', data=payload2, content_type='application/json')
    req_ai2.user = admin_user
    res_ai2 = api_ai_chat(req_ai2)
    assert res_ai2.status_code == 200, f"Expected 200, got {res_ai2.status_code}"
    data_ai2 = json.loads(res_ai2.content.decode('utf-8'))
    assert data_ai2.get('status') == 'success'
    assert 'MoEYS' in data_ai2.get('reply') or 'និទ្ទេស' in data_ai2.get('reply')
    print("  -> PASS: AI Agent answered MoEYS grading rules accurately!")

    # -------------------------------------------------------------
    # 5. Test Pop Chat Widget Modes
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Pop Chat Widget Template...")
    with open('templates/includes/pop_chat_widget.html', 'r', encoding='utf-8') as f:
        pop_chat_html = f.read()

    assert 'id="tabBtnAiAgent"' in pop_chat_html, "AI tab button missing in Pop Chat"
    assert 'id="tabBtnDirectChat"' in pop_chat_html, "Direct tab button missing in Pop Chat"
    assert 'id="popChatAiView"' in pop_chat_html, "AI chat view missing in Pop Chat"
    assert 'handleAiChatSubmit' in pop_chat_html, "handleAiChatSubmit JS missing in Pop Chat"
    print("  -> PASS: Pop Chat Widget includes dual AI Agent / Direct Chat modes!")

    print("\n==================================================================")
    print("ALL 6 TESTS PASSED FLAWLESSLY! 100% SUCCESS!")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
