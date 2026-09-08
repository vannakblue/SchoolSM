"""
Test suite for Digital Tools Hub Gemini 3.8 Flash AI Integration in SchoolSM.
"""

import os
import sys
import json
import django

# Reconfigure stdout for UTF-8 in Windows console
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import User
from apps.tools.views import api_tool_ai_assist, text_analyzer_view, voice_typing_view, classroom_picker_view, calculator_converter_view, tools_hub
from apps.tools.ai_service import ToolAiService


def run_tests():
    print("==================================================================")
    print("TESTING: DIGITAL TOOLS HUB GEMINI 3.8 FLASH AI INTEGRATION")
    print("==================================================================")

    rf = RequestFactory()
    admin_user = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()

    # -------------------------------------------------------------
    # 1. Test Static JS Library
    # -------------------------------------------------------------
    print("\n[TEST 1] Verifying static/js/tool_ai_assistant.js...")
    assert os.path.exists('static/js/tool_ai_assistant.js'), "tool_ai_assistant.js does not exist"
    with open('static/js/tool_ai_assistant.js', 'r', encoding='utf-8') as f:
        js_content = f.read()
    assert 'ToolAiAssistant' in js_content, "ToolAiAssistant missing in JS"
    assert 'toolAiResultModal' in js_content, "toolAiResultModal missing in JS"
    print("  -> PASS: tool_ai_assistant.js verified with modal and runner logic!")

    # -------------------------------------------------------------
    # 2. Test ToolAiService Logic
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing ToolAiService (Text Analyzer Summarize)...")
    res1 = ToolAiService.process_tool_ai(
        tool_name='text_analyzer',
        action='summarize',
        content='ក្រសួងអប់រំ យុវជន និងកីឡា បានដាក់ចេញនូវវិធានការពង្រឹងគុណភាពអប់រំនៅតាមសាលារៀនជំនាន់ថ្មី។',
        user=admin_user
    )
    assert res1.get('status') == 'success', f"Service failed: {res1}"
    assert len(res1.get('result', '')) > 20, "Result too short"
    print(f"  -> PASS: ToolAiService responded successfully: {res1.get('result')[:120]}...")

    print("\n[TEST 3] Testing ToolAiService (Classroom Picker Balance Teams)...")
    res2 = ToolAiService.process_tool_ai(
        tool_name='classroom_picker',
        action='balance_teams',
        content='សុខ ពិសិដ្ឋ\nចាន់ ថាវី\nកែវ សុផល\nលឹម ហុង\nសៅ សុភាព\nម៉ៅ វណ្ណា',
        options={'num_teams': 2},
        user=admin_user
    )
    assert res2.get('status') == 'success'
    assert 'ក្រុម' in res2.get('result', '')
    print("  -> PASS: Pedagogical team balancing completed successfully!")

    print("\n[TEST 4] Testing ToolAiService (Math Solver)...")
    res3 = ToolAiService.process_tool_ai(
        tool_name='calculator_converter',
        action='step_by_step_solve',
        content='2x^2 + 5x - 3 = 0',
        thinking_level='high',
        user=admin_user
    )
    assert res3.get('status') == 'success'
    print(f"  -> PASS: Step-by-step Math solver executed successfully: {res3.get('result')[:100]}...")

    # -------------------------------------------------------------
    # 3. Test API Endpoint (/tools/api/ai-assist/)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Backend API Endpoint (/tools/api/ai-assist/)...")
    payload = json.dumps({
        'tool': 'voice_typing',
        'action': 'auto_format',
        'content': 'សួស្តីលោកគ្រូអ្នកគ្រូ ថ្ងៃនេះយើងប្រជុំអំពីកាលវិភាគប្រឡងឆមាសទីមួយ',
        'thinking_level': 'medium'
    })
    req = rf.post('/tools/api/ai-assist/', data=payload, content_type='application/json')
    req.user = admin_user
    res_api = api_tool_ai_assist(req)
    assert res_api.status_code == 200, f"Expected 200, got {res_api.status_code}"
    data_api = json.loads(res_api.content.decode('utf-8'))
    assert data_api.get('status') == 'success'
    print(f"  -> PASS: API Endpoint returned status=success: {data_api.get('result')[:100]}...")

    # -------------------------------------------------------------
    # 4. Test Template Renderings with AI Elements
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Template Renderings...")
    
    # Text Analyzer
    req_ta = rf.get('/tools/text-analyzer/')
    req_ta.user = admin_user
    res_ta = text_analyzer_view(req_ta)
    assert res_ta.status_code == 200
    content_ta = res_ta.content.decode('utf-8')
    assert 'runAiTextAction' in content_ta, "runAiTextAction missing in text_analyzer.html"
    assert 'Gemini 3.8 Flash AI' in content_ta
    print("  -> PASS: Text Analyzer template renders with AI Panel!")

    # Voice Typing
    req_vt = rf.get('/tools/voice-typing/')
    req_vt.user = admin_user
    res_vt = voice_typing_view(req_vt)
    assert res_vt.status_code == 200
    content_vt = res_vt.content.decode('utf-8')
    assert 'runAiVoiceAction' in content_vt, "runAiVoiceAction missing in voice_typing.html"
    assert 'បម្លែងជាកិច្ចតែងការបង្រៀន' in content_vt
    print("  -> PASS: Voice Typing template renders with AI Actions!")

    # Classroom Picker
    req_cp = rf.get('/tools/classroom-picker/')
    req_cp.user = admin_user
    res_cp = classroom_picker_view(req_cp)
    assert res_cp.status_code == 200
    content_cp = res_cp.content.decode('utf-8')
    assert 'runAiPedagogicalGrouping' in content_cp, "runAiPedagogicalGrouping missing"
    assert 'runAiWheelQuiz' in content_cp, "runAiWheelQuiz missing"
    print("  -> PASS: Classroom Picker template renders with AI Grouping & Quiz generator!")

    # Calculator Converter
    req_calc = rf.get('/tools/calculator-converter/')
    req_calc.user = admin_user
    res_calc = calculator_converter_view(req_calc)
    assert res_calc.status_code == 200
    content_calc = res_calc.content.decode('utf-8')
    assert 'tab-ai-solver' in content_calc, "tab-ai-solver missing in calculator_converter.html"
    assert 'solveMathWithAi' in content_calc, "solveMathWithAi missing"
    print("  -> PASS: Calculator & Converter template renders with AI Step-by-step Math Solver!")

    # Tools Hub
    req_hub = rf.get('/tools/')
    req_hub.user = admin_user
    res_hub = tools_hub(req_hub)
    assert res_hub.status_code == 200
    content_hub = res_hub.content.decode('utf-8')
    assert 'askAiToolFinder' in content_hub, "askAiToolFinder missing in hub.html"
    assert 'AI Powered' in content_hub or 'AI Solver' in content_hub
    print("  -> PASS: Tools Hub template renders with AI Smart Tool Finder & AI Badges!")

    print("\n==================================================================")
    print("ALL 6 TEST PHASES PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == '__main__':
    run_tests()
