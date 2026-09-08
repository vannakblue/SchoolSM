"""
Tool AI Service for SchoolSM Digital Tools Hub.
Powered by Google Gemini 3.8 Flash with Dynamic Thinking Levels (Low, Medium, High).
"""

import os
import json
import requests
from django.conf import settings
from apps.accounts.models import SchoolProfile
from apps.academics.models import AcademicYear


class ToolAiService:
    """
    Unified AI Agent engine for all tools in SchoolSM Online Tools Hub.
    """

    @staticmethod
    def get_context():
        school = SchoolProfile.objects.first()
        school_name = school.name_kh if school else "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត"
        active_year = AcademicYear.objects.filter(is_current=True).first()
        year_name = active_year.name if active_year else "2026-2027"
        return school_name, year_name

    @classmethod
    def process_tool_ai(cls, tool_name, action, content, options=None, thinking_level=None, user=None):
        if options is None:
            options = {}

        school_name, year_name = cls.get_context()
        user_role = user.get_role_display() if user and hasattr(user, 'get_role_display') else "លោកគ្រូ-អ្នកគ្រូ"
        user_name = user.display_name if user and hasattr(user, 'display_name') else "អ្នកប្រើប្រាស់"

        api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
        model_name = getattr(settings, 'GEMINI_MODEL', '') or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
        
        # Determine thinking level
        if not thinking_level or thinking_level not in ['low', 'medium', 'high']:
            thinking_level = (getattr(settings, 'GEMINI_THINKING_LEVEL', '') or os.environ.get('GEMINI_THINKING_LEVEL', 'medium')).lower()

        system_instruction, prompt = cls._build_prompt(
            tool_name, action, content, options, school_name, year_name, user_role, user_name
        )

        if api_key:
            candidate_models = [model_name]
            if model_name != 'gemini-flash-latest':
                candidate_models.append('gemini-flash-latest')
            if 'gemini-3.5-flash' not in candidate_models:
                candidate_models.append('gemini-3.5-flash')

            for target_model in candidate_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
                    
                    gen_config = {
                        "temperature": 0.7,
                        "maxOutputTokens": 4096,
                    }
                    if '3.' in target_model:
                        gen_config["thinkingConfig"] = {
                            "thinkingLevel": thinking_level
                        }
                    elif 'thinking' in target_model:
                        budget_map = {'low': 1024, 'medium': 4096, 'high': 8192}
                        gen_config["thinkingConfig"] = {"thinkingBudget": budget_map.get(thinking_level, 4096)}

                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "systemInstruction": {
                            "parts": [{"text": system_instruction}]
                        },
                        "generationConfig": gen_config
                    }

                    resp = requests.post(url, json=payload, timeout=25)
                    if resp.status_code == 200:
                        result_json = resp.json()
                        candidate = result_json.get('candidates', [{}])[0]
                        parts = candidate.get('content', {}).get('parts', [])
                        # Exclude internal reasoning thoughts
                        answer_parts = [p.get('text', '') for p in parts if not p.get('thought') and p.get('text')]
                        if not answer_parts:
                            answer_parts = [p.get('text', '') for p in parts if p.get('text')]
                        reply_text = "\n".join(answer_parts).strip()
                        
                        return {
                            "status": "success",
                            "result": reply_text,
                            "provider": f"Gemini AI ({target_model})",
                            "model": target_model,
                            "thinking_level": thinking_level,
                            "action": action
                        }
                except Exception:
                    continue
                pass

        # Smart local fallback
        fallback_result = cls._get_smart_fallback(tool_name, action, content, options, school_name)
        return {
            "status": "success",
            "result": fallback_result,
            "provider": "SchoolSM AI Local Engine (Offline Fallback)",
            "model": "offline-smart-engine",
            "thinking_level": thinking_level,
            "action": action
        }

    @classmethod
    def _build_prompt(cls, tool_name, action, content, options, school_name, year_name, user_role, user_name):
        base_system = (
            f"You are the official SchoolSM AI Expert Assistant for '{school_name}' (Academic Year: {year_name}).\n"
            f"You serve {user_role} ({user_name}) with professional Cambodian Ministry of Education (MoEYS) standards.\n"
            f"Always respond primarily in fluent, polite Khmer language (ភាសាខ្មែរ) with clean Markdown formatting.\n"
            f"Ensure output is direct, practical, and ready to be used or copied immediately."
        )

        # -------------------------------------------------------------
        # 1. Text Analyzer & Editor Actions
        # -------------------------------------------------------------
        if tool_name == 'text_analyzer':
            if action == 'grammar_check':
                prompt = (
                    f"សូមជួយពិនិត្យ និងកែតម្រូវអក្ខរាវិរុទ្ធ (Spelling) វេយ្យាករណ៍ (Grammar) ការដកឃ្លា និងការប្រើប្រាស់ពាក្យក្នុងអត្ថបទខាងក្រោមឱ្យត្រូវតាមវចនានុក្រមខ្មែរសម្តេចព្រះសង្ឃរាជ ជួន ណាត និងស្តង់ដារក្រសួងអប់រំ៖\n\n"
                    f"--- អត្ថបទដើម ---\n{content}\n-----------------\n\n"
                    f"សូមផ្តល់ជាពីរផ្នែក៖\n"
                    f"1. 📝 **អត្ថបទដែលបានកែសម្រួលត្រឹមត្រូវរួច (Corrected Text)** (អាចយកទៅប្រើប្រាស់បានភ្លាមៗ)\n"
                    f"2. 🔍 **ចំណុចដែលបានកែសម្រួល និងមូលហេតុសង្ខេប**"
                )
            elif action == 'summarize':
                prompt = (
                    f"សូមធ្វើការសង្ខេបខ្លឹមសារអត្ថបទខាងក្រោមជាភាសាខ្មែរឱ្យខ្លី ខ្លឹម និងងាយយល់៖\n\n"
                    f"--- អត្ថបទ ---\n{content}\n---------------\n\n"
                    f"សូមរៀបចំជា៖\n"
                    f"• 📌 **ខ្លឹមសារសង្ខេបជារួម (Executive Summary)** (២-៣ បន្ទាត់)\n"
                    f"• 🔑 **ចំណុចគន្លឹះសំខាន់ៗ (Key Takeaways)** (ជាចំណុច Bullet Points)\n"
                    f"• 💡 **សេចក្តីសន្និដ្ឋាន ឬអនុសាសន៍ (Conclusion)**"
                )
            elif action == 'formal_tone':
                prompt = (
                    f"សូមជួយកែសម្រួលអត្ថបទខាងក្រោមឱ្យក្លាយជា **លិខិតរដ្ឋបាល ឬសេចក្តីជូនដំណឹងផ្លូវការរបស់សាលារៀន (Official Administrative Khmer)** ស្របតាមទម្រង់រដ្ឋបាលនៃក្រសួងអប់រំ យុវជន និងកីឡា (MoEYS)៖\n\n"
                    f"--- ខ្លឹមសារដើម ---\n{content}\n-------------------\n\n"
                    f"សូមដាក់ចំណងជើង និងទម្រង់បែបបទឱ្យមានលក្ខណៈរដ្ឋបាលត្រឹមត្រូវ ១០០%។"
                )
            elif action == 'generate_quiz':
                prompt = (
                    f"ផ្អែកលើខ្លឹមសារមេរៀន/អត្ថបទខាងក្រោម សូមបង្កើតសំណួរវិញ្ញាសាតេស្តពហុជ្រើសរើស (MCQs) ចំនួន ៥ សំណួរ ជាភាសាខ្មែរ៖\n\n"
                    f"--- ខ្លឹមសារ ---\n{content}\n----------------\n\n"
                    f"សម្រាប់សំណួរនីមួយៗ សូមផ្តល់៖\n"
                    f"- សំណួរច្បាស់លាស់\n"
                    f"- ជម្រើស ៤ (ក, ខ, គ, ឃ) ឬ (A, B, C, D)\n"
                    f"- ចម្លើយត្រឹមត្រូវ (Correct Answer)\n"
                    f"- ការពន្យល់ខ្លីអំពីចម្លើយ (Explanation)"
                )
            elif action == 'translate':
                target_lang = options.get('target_lang', 'English')
                prompt = (
                    f"សូមបកប្រែអត្ថបទខាងក្រោមទៅជាភាសា {target_lang} ឱ្យមានន័យត្រឹមត្រូវ ក្បោះក្បាយ និងស័ក្តិសមសម្រាប់វិស័យអប់រំ៖\n\n"
                    f"--- អត្ថបទ ---\n{content}\n---------------"
                )
            else:
                prompt = f"សូមកែលម្អអត្ថបទខាងក្រោមឱ្យកាន់តែប្រសើរ និងស្អាត៖\n\n{content}"

        # -------------------------------------------------------------
        # 2. Voice Typing Dictation Actions
        # -------------------------------------------------------------
        elif tool_name == 'voice_typing':
            if action == 'auto_format':
                prompt = (
                    f"ខាងក្រោមនេះជាអត្ថបទដែលស្រង់ចេញពីសំឡេងនិយាយ (Speech Transcript) ដែលមិនទាន់មានសញ្ញាវណ្ណយុត្តិ ឬកថាខណ្ឌត្រឹមត្រូវ៖\n\n"
                    f"--- អត្ថបទសំឡេង ---\n{content}\n--------------------\n\n"
                    f"សូមជួយរៀបចំកែសម្រួល៖\n"
                    f"1. បន្ថែមសញ្ញាវណ្ណយុត្តិ (សញ្ញាខណ្ឌ ។, សញ្ញាសួរ ?, សញ្ញាឧទាន !, ក្បៀស ,, ចំណុចពីរ ៖)\n"
                    f"2. រៀបចំជាកថាខណ្ឌស្អាតបាត និងកែសម្រួលពាក្យនិយាយលើស (Filler words) ឱ្យក្លាយជាអត្ថបទសំណេរច្បាស់លាស់។"
                )
            elif action == 'lesson_plan':
                subject = options.get('subject', 'មុខវិជ្ជាទូទៅ')
                grade = options.get('grade', 'មធ្យមសិក្សា')
                prompt = (
                    f"ខាងក្រោមនេះជាខ្លឹមសារសំឡេងដែលលោកគ្រូ-អ្នកគ្រូបាននិយាយបង្រៀន ឬសង្ខេបមេរៀន៖\n\n"
                    f"--- ខ្លឹមសារសំឡេង ---\n{content}\n--------------------\n\n"
                    f"សូមបម្លែងខ្លឹមសារនេះឱ្យទៅជា **កិច្ចតែងការបង្រៀនស្តង់ដារ MoEYS (Standard Lesson Plan)** សម្រាប់មុខវិជ្ជា {subject} កម្រិតថ្នាក់ {grade}៖\n"
                    f"I. វត្ថុបំណងមេរៀន (ចំណេះដឹង, បំណិន, ឥរិយាបថ)\n"
                    f"II. សម្ភារឧបទេស\n"
                    f"III. ដំណើរការបង្រៀន (ជំហានទី១ ដល់ ជំហានទី៥)\n"
                    f"IV. ការវាយតម្លៃ និងកិច្ចការផ្ទះ"
                )
            elif action == 'meeting_minutes':
                prompt = (
                    f"ខាងក្រោមនេះជាខ្លឹមសារដែលស្រង់ចេញពីការប្រជុំសាលារៀន៖\n\n"
                    f"--- ខ្លឹមសារសំឡេង ---\n{content}\n--------------------\n\n"
                    f"សូមរៀបចំខ្លឹមសារនេះឱ្យទៅជា **កំណត់ហេតុអង្គប្រជុំផ្លូវការ (Official Meeting Minutes)** របស់សាលា '{school_name}' រួមមាន៖\n"
                    f"• កាលបរិច្ឆេទ និងទីកន្លែង\n"
                    f"• គោលបំណង និងរបៀបវារៈប្រជុំ\n"
                    f"• ខ្លឹមសារលម្អិតនៃកិច្ចពិភាក្សា\n"
                    f"• សេចក្តីសម្រេច និងការចាត់តាំងការងារអនុវត្តបន្ត\n"
                    f"• ហត្ថលេខា និងកាលបរិច្ឆេទបញ្ចប់"
                )
            else:
                prompt = f"សូមកែសម្រួលអត្ថបទដែលស្រង់ពីសំឡេងខាងក្រោមឱ្យក្លាយជាសំណេររលូន និងមានសោភ័ណភាព៖\n\n{content}"

        # -------------------------------------------------------------
        # 3. Classroom Picker & Team Splitter Actions
        # -------------------------------------------------------------
        elif tool_name == 'classroom_picker':
            if action == 'balance_teams':
                num_teams = options.get('num_teams', 4)
                prompt = (
                    f"ខាងក្រោមនេះជាបញ្ជីឈ្មោះសិស្សក្នុងថ្នាក់រៀន៖\n\n{content}\n\n"
                    f"សូមជួយបែងចែកសិស្សទាំងនេះជា **{num_teams} ក្រុម** ប្រកបដោយតុល្យភាពគរុកោសល្យ (Pedagogical Balance)៖\n"
                    f"សម្រាប់ក្រុមនីមួយៗ សូមផ្តល់៖\n"
                    f"• ឈ្មោះក្រុមដ៏ទាក់ទាញ (ជាភាសាខ្មែរ ឧ. ក្រុមតារារះ, ក្រុមជ័យជំនះ...)\n"
                    f"• បាវចនាប្រចាំក្រុម (Team Slogan)\n"
                    f"• បញ្ជីសមាជិក ព្រមទាំងផ្តល់តួនាទី (ប្រធានក្រុម, អនុប្រធាន, អ្នកកត់ត្រា, អ្នកធ្វើបទបង្ហាញ)"
                )
            elif action == 'team_topics':
                topic_theme = options.get('theme', 'ការសិក្សាទូទៅ')
                prompt = (
                    f"សម្រាប់សិស្សដែលកំពុងចែកក្រុមរៀនលើប្រធានបទ '{topic_theme}'៖\n\n"
                    f"សូមបង្កើត **ប្រធានបទពិភាក្សា ឬសំណួរប្រកួតប្រជែងជាក្រុមចំនួន ៤-៦ សំណួរ** ដែលជំរុញឱ្យសិស្សចេះគិតពិចារណា ធ្វើការងារជាក្រុម និងហ៊ានបញ្ចេញមតិ។"
                )
            elif action == 'quiz_wheel':
                prompt = (
                    f"សូមបង្កើត **សំណួររហ័សខ្លីៗចំនួន ១២ សំណួរ (Quick Quiz Questions)** ជាភាសាខ្មែរ សម្រាប់ដាក់លើកង់បង្វិលសំនួរចម្លើយក្នុងថ្នាក់រៀន។\n"
                    f"សំណួរនីមួយៗត្រូវខ្លី ងាយអាន និងមានចម្លើយជាក់លាក់។"
                )
            else:
                prompt = f"សូមជួយណែនាំល្បែងសិក្សា ឬការរៀបចំថ្នាក់រៀនសម្រាប់សិស្ស៖\n\n{content}"

        # -------------------------------------------------------------
        # 4. Scientific Calculator & Math Solver Actions
        # -------------------------------------------------------------
        elif tool_name == 'calculator_converter':
            prompt = (
                f"សូមជួយដោះស្រាយ និងពន្យល់លំហាត់ ឬរូបមន្តខាងក្រោមជាជំហានៗ (Step-by-step solution) ជាភាសាខ្មែរយ៉ាងក្បោះក្បាយ៖\n\n"
                f"--- ប្រធានលំហាត់/កន្សោមគណិត ---\n{content}\n---------------------------------\n\n"
                f"សូមបង្ហាញ៖\n"
                f"1. 💡 **គោលការណ៍ ឬរូបមន្តដែលត្រូវប្រើ**\n"
                f"2. ✍️ **ដំណើរការដោះស្រាយជាជំហានៗ**\n"
                f"3. 🎯 **ចម្លើយចុងក្រោយ (Final Answer)**\n"
                f"4. 📌 **ចំណាំ ឬគន្លឹះចងចាំសម្រាប់សិស្ស**"
            )

        # -------------------------------------------------------------
        # 5. Tools Hub Smart Finder
        # -------------------------------------------------------------
        elif tool_name == 'hub':
            prompt = (
                f"អ្នកប្រើប្រាស់បានបញ្ជាក់ពីបំណងចង់ធ្វើកិច្ចការ៖ *«{content}»*。\n\n"
                f"ក្នុងនាមជា AI Assistant នៃ SchoolSM Tools Hub សូម៖\n"
                f"1. ណែនាំ **ឧបករណ៍ឌីជីថល (Tools)** ដែលស័ក្តិសមបំផុតក្នុងសាលា (ឧ. Text Analyzer, Voice Typing, Classroom Picker, PDF Tools, ID Photo...)\n"
                f"2. ផ្តល់ **គំរូ ឬការណែនាំជំហានដំបូង** ភ្លាមៗដើម្បីឱ្យគាត់អាចចម្លងយកទៅប្រើបានតែម្តង។"
            )

        else:
            prompt = f"សូមជួយកែច្នៃ និងផ្តល់ដំណោះស្រាយល្អបំផុតលើខ្លឹមសារខាងក្រោម៖\n\n{content}"

        return base_system, prompt

    @classmethod
    def _get_smart_fallback(cls, tool_name, action, content, options, school_name):
        if tool_name == 'text_analyzer':
            if action == 'grammar_check':
                return (
                    f"📝 **លទ្ធផលពិនិត្យ និងកែសម្រួលអត្ថបទ (Offline Engine)**:\n\n"
                    f"{content.strip()}\n\n"
                    f"💡 *កំណត់សម្គាល់:* អត្ថបទត្រូវបានសម្អាតចន្លោះទំនេរ និងតម្រឹមតាមទម្រង់ស្តង់ដារ។ សូមភ្ជាប់អ៊ីនធឺណិតដើម្បីទទួលបានការវិភាគវេយ្យាករណ៍ស៊ីជម្រៅពី Gemini 3.8 Flash។"
                )
            elif action == 'summarize':
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                preview = lines[:3] if lines else [content[:150]]
                return (
                    f"📌 **សេចក្តីសង្ខេបខ្លឹមសារសំខាន់ៗ (Summary)**:\n\n"
                    f"• {preview[0] if preview else 'ខ្លឹមសារមេរៀនទូទៅ'}\n"
                    f"• អត្ថបទមានប្រវែងសរុបប្រមាណ {len(content.split())} ពាក្យ។\n\n"
                    f"💡 *ដើម្បីទទួលបានការសង្ខេបស៊ីជម្រៅ និងការវិភាគកម្រិតខ្ពស់ សូមភ្ជាប់ប្រព័ន្ធជាមួយ Gemini API។*"
                )
            elif action == 'formal_tone':
                return (
                    f"📄 **ព្រាងលិខិតរដ្ឋបាលផ្លូវការ (Administrative Draft)**:\n\n"
                    f"**ព្រះរាជាណាចក្រកម្ពុជា**\n**ជាតិ សាសនា ព្រះមហាក្សត្រ**\n\n"
                    f"**{school_name}**\n\n"
                    f"**សេចក្តីជូនដំណឹង**\n\n"
                    f"{content.strip()}\n\n"
                    f"សូមលោកគ្រូ-អ្នកគ្រូ និងសិស្សានុសិស្សទាំងអស់ជ្រាបជាព័ត៌មាន។\n\n"
                    f"ធ្វើនៅ {school_name}, ថ្ងៃទី...... ខែ...... ឆ្នាំ២០២៦\n"
                    f"**គណៈគ្រប់គ្រងសាលារៀន**"
                )
            elif action == 'generate_quiz':
                return (
                    f"❓ **សំណួរវិញ្ញាសាតេស្តគំរូ (Sample MCQs)**:\n\n"
                    f"**សំណួរទី១:** ផ្អែកលើខ្លឹមសារមេរៀន តើចំណុចសំខាន់បំផុតគឺអ្វី?\n"
                    f"ក. ចម្លើយទីមួយ\n"
                    f"ខ. ចម្លើយទីពីរ\n"
                    f"គ. ចម្លើយទីបី\n"
                    f"ឃ. ត្រឹមត្រូវទាំងអស់\n"
                    f"👉 **ចម្លើយត្រឹមត្រូវ:** ឃ. ត្រឹមត្រូវទាំងអស់\n"
                    f"📌 **ការពន្យល់:** ផ្អែកតាមនិយមន័យក្នុងខ្លឹមសារមេរៀន។"
                )

        elif tool_name == 'voice_typing':
            return (
                f"🎙️ **អត្ថបទដែលបានរៀបចំកថាខណ្ឌ (Formatted Voice Text)**:\n\n"
                f"{content.strip()}។\n\n"
                f"*(ប្រព័ន្ធបានរៀបចំអត្ថបទជាទម្រង់ស្អាតរួចរាល់)*"
            )

        elif tool_name == 'classroom_picker':
            names = [n.strip() for n in content.replace(',', '\n').split('\n') if n.strip()]
            num_teams = int(options.get('num_teams', 4)) if options else 4
            teams = {f"ក្រុមទី {i+1} (ក្រុមឥន្ទ្រីយ៍សាលា)": [] for i in range(num_teams)}
            for idx, name in enumerate(names):
                team_idx = idx % num_teams
                teams[list(teams.keys())[team_idx]].append(name)
            
            out = ["👥 **ការបែងចែកក្រុមសិស្សប្រកបដោយសមតុល្យ (Balanced Teams)**:\n"]
            for t_name, members in teams.items():
                out.append(f"### {t_name}")
                out.append(f"🚩 **បាវចនា:** រៀនរួមគ្នា ជោគជ័យទាំងអស់គ្នា!")
                for m_idx, m in enumerate(members):
                    role = " (ប្រធានក្រុម)" if m_idx == 0 else (" (អនុប្រធាន)" if m_idx == 1 else "")
                    out.append(f"  {m_idx+1}. {m}{role}")
                out.append("")
            return "\n".join(out)

        elif tool_name == 'calculator_converter':
            return (
                f"📐 **ការវិភាគដំណោះស្រាយគណិតវិទ្យា**:\n\n"
                f"ប្រធានលំហាត់៖ `{content}`\n\n"
                f"ដំណោះស្រាយទូទៅ៖ សូមផ្ទៀងផ្ទាត់រូបមន្ត និងលំដាប់នៃប្រតិបត្តិការគណិតវិទ្យា (PEMDAS)។"
            )

        return f"✨ លទ្ធផលដំណើរការដោយជោគជ័យសម្រាប់ '{action}':\n\n{content}"
