"""
AI Agent Translation Service for SchoolSM.
Translates Khmer text (from Web Browser or Google Sheets) into English automatically
using Google Gemini AI with key rotation and intelligent offline fallback.
"""

import os
import json
import logging
import re
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Common Cambodian educational / institutional dictionary for accurate local fallback
OFFLINE_DICTIONARY = {
    "វិទ្យាល័យ": "High School",
    "អនុវិទ្យាល័យ": "Secondary School",
    "បឋមសិក្សា": "Primary School",
    "សាលារៀន": "School",
    "ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌": "Knowledge, Discipline, Morality, Virtue",
    "ចំណេះដឹង": "Knowledge",
    "វិន័យ": "Discipline",
    "សីលធម៌": "Morality",
    "គុណធម៌": "Virtue",
    "ក្រសួងអប់រំ យុវជន និងកីឡា": "Ministry of Education, Youth and Sport",
    "មន្ទីរអប់រំ យុវជន និងកីឡា": "Department of Education, Youth and Sport",
    "ការិយាល័យអប់រំ យុវជន និងកីឡា": "Office of Education, Youth and Sport",
    "នាយកសាលា": "Principal",
    "នាយិកាសាលា": "Principal",
    "លោកគ្រូ": "Teacher",
    "អ្នកគ្រូ": "Teacher",
    "លោកគ្រូ-អ្នកគ្រូ": "Teachers & Staff",
    "សិស្ស": "Student",
    "សិស្សានុសិស្ស": "Students",
    "សិស្សានុសិស្សសរុប": "Total Students",
    "មាតាបិតា": "Parents",
    "អាណាព្យាបាល": "Guardians",
    "បន្ទប់រៀន": "Classroom",
    "កាលវិភាគ": "Timetable",
    "វត្តមាន": "Attendance",
    "ពិន្ទុ": "Scores & Grades",
    "ការប្រឡង": "Examinations",
    "សេចក្តីជូនដំណឹង": "Announcement",
    "ព័ត៌មានថ្មីៗ": "Latest News",
    "ព្រឹត្តិការណ៍": "Event",
    "វិចិត្រសាល": "Gallery",
    "ទំនាក់ទំនង": "Contact",
    "ទំព័រដើម": "Home",
    "អំពីសាលា": "About School",
    "កម្មវិធីសិក្សា": "Academics",
    "ស្វែងយល់បន្ថែម": "Learn More",
    "ឈ្វេងយល់បន្ថែម": "Learn More",
    "ឈ្វេងយល់": "Learn More",
    "ចូលប្រព័ន្ធ": "Portal Login",
    "ផ្ទាំងគ្រប់គ្រង": "Dashboard",
    "ប្រព័ន្ធគ្រប់គ្រងសាលា": "School Management System",
    "រាជធានីភ្នំពេញ": "Phnom Penh",
    "ខេត្តកណ្ដាល": "Kandal Province",
    "ស្រុកកណ្ដាលស្ទឹង": "Kandal Stueng District",
    "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត": "Hun Sen Kampong Kantuot High School",
    "វិ. ហ៊ុន សែន កំពង់កន្ទួត": "Hun Sen Kampong Kantuot HS",
    "វិ. ហស កំពង់កន្ទួត": "Hun Sen Kampong Kantuot HS",
    "លោក ថេង រិទ្ធីយ៉ា": "Mr. Theng Rithya",
    "ថេង រិទ្ធីយ៉ា": "Theng Rithya",
    "ផ្លូវលេខ១០៥ ភូមិស្វាយមីង ឃុំបារគូ ស្រុកកណ្តាលស្ទឹង ខេត្តកណ្តាល": "Street 105, Svay Ming Village, Barkou, Kandal Stueng, Kandal Province",
    "ផ្លូវលេខ១០៥": "Street 105",
    "ភូមិស្វាយមីង": "Svay Ming Village",
    "ឃុំបារគូ": "Barkou Commune",
    "ស្រុកកណ្តាលស្ទឹង": "Kandal Stueng District",
    "ខេត្តកណ្តាល": "Kandal Province",
    "ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកកណ្តាលស្ទឹង": "Kandal Stueng District Office of Education",
    "ការិយាល័យអប់រំ យុវជន និងកីឡា ខណ្ឌដូនពេញ": "Daun Penh District Office of Education",
    "ការិយាល័យអប់រំ យុវជន និងកីឡា": "District Office of Education, Youth and Sport",
    "ការិយាល័យអប់រំ": "District Office of Education",
    "មន្ទីរអប់រំ យុវជន និងកីឡា រាជធានីភ្នំពេញ": "Phnom Penh Municipal Department of Education",
    "មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តកណ្តាល": "Kandal Provincial Department of Education",
    "មន្ទីរអប់រំ យុវជន និងកីឡា": "Provincial Department of Education, Youth and Sport",
    "មន្ទីរអប់រំ": "Provincial Department of Education",
    "ក្រសួងអប់រំ យុវជន និងកីឡា": "Ministry of Education, Youth and Sport",
    "អនុវិទ្យាល័យ, វិទ្យាល័យ": "Secondary & High School",
    "មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ": "Kindergarten, Primary, Secondary & High School",
    "មត្តេយ្យ, បឋម, អនុវិទ្យាល័យ, វិទ្យាល័យ": "Kindergarten, Primary, Secondary & High School",
    "អនុវិទ្យាល័យ": "Secondary School",
    "វិទ្យាល័យ": "High School",
    "បឋមសិក្សា": "Primary School",
    "មត្តេយ្យ": "Kindergarten",
    "យើងខ្ញុំបណ្តុះបណ្តាលសិស្សឱ្យមានទាំងចំណេះដឹងទូទៅ ជំនាញបច្ចេកវិទ្យា វិន័យ សីលធម៌ល្អ និងស្មារតីទទួលខុសត្រូវខ្ពស់។": "We educate students with comprehensive knowledge, technology skills, strong discipline, good morality, and a high sense of responsibility.",
    "ពិធីបើកបវេសនកាលឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧": "Opening Ceremony of the New Academic Year 2026-2027",
    "ពិធីបើកបវេសនកាលឆ្នាំសិក្សាថ្មី": "Opening Ceremony of the New Academic Year",
    "ពិធីបើកបវេសនកាល": "School Opening Ceremony",
    "បវេសនកាល": "New Academic Year Commencement",
    "ឆ្នាំសិក្សាថ្មី": "New Academic Year",
    "គណៈគ្រប់គ្រងសាលា": "School Management Board",
    "ទិវាគ្រូបង្រៀន": "Teachers' Day",
    "ពិធីអបអរសាទរទិវាគ្រូបង្រៀន": "Teachers' Day Celebration",
    "ពិធីអបអរសាទរ": "Celebration Ceremony",
    "ការលើកទឹកចិត្ត": "Recognition and Appreciation",
    "លោកគ្រូ-អ្នកគ្រូឆ្នើម": "Outstanding Teachers",
    "ប្រចាំឆ្នាំ": "Annual",
    "វិទ្យាល័យចំណេះទូទៅ": "General High School",
    "កម្មវិធី MoEYS & ទ្វេភាសា": "MoEYS & Bilingual Curriculum",
    "បន្ទប់ពិសោធន៍ STEM & IT": "STEM & IT Science Labs",
    "សុវត្ថិភាព & វិន័យខ្ពស់": "High Discipline & Safety",
    "ការប្រកួតកីឡាបាល់ទាត់ និងបាល់ទះប្រចាំឆ្នាំ": "Annual Football and Volleyball Tournament",
    "ការប្រកួតកីឡាបាល់ទាត់ប្រចាំឆ្នាំ": "Annual Football Tournament",
    "ការប្រកួតកីឡាបាល់ទះប្រចាំឆ្នាំ": "Annual Volleyball Tournament",
    "ការប្រកួតកីឡា": "Sports Tournament",
    "បាល់ទាត់": "Football",
    "បាល់ទះ": "Volleyball",
    "ពិធីបើកបវេសនកាល និងទិវាវប្បធម៌សាលារៀន": "Opening Ceremony and School Culture Day",
    "ពិធីបើកបវេសនកាល និងទិវាវប្បធម៌សាលា": "Opening Ceremony and School Culture Day",
    "ទិវាវប្បធម៌សាលារៀន": "School Culture Day",
    "ទិវាវប្បធម៌សាលា": "School Culture Day",
    "ទិវាវប្បធម៌": "Culture Day",
    "សកម្មភាពកីឡាដើម្បីសុខភាព និងមិត្តភាពរវាងថ្នាក់រៀនទាំងអស់។": "Sports activities for health, fitness, and friendship among all classes.",
    "កម្រងរូបភាពសកម្មភាពដ៏រស់រវើកក្នុងពិធីបើកបវេសនកាល និងការសម្តែងសិល្បៈវប្បធម៌របស់សិស្សានុសិស្សគ្រប់កម្រិតថ្នាក់។": "Vibrant photo collection of the academic opening ceremony and cultural art performances by students across all grade levels.",
    "សកម្មភាពសិស្ស": "Student Activities",
    "ពិធីចែកសញ្ញាបត្រ": "Graduation Ceremony",
    "ទស្សនកិច្ចសិក្សា": "Study Tour",
    "ការងារស្ម័គ្រចិត្ត": "Volunteer Work",
    "បណ្ណាល័យសាលា": "School Library",
    "បន្ទប់កុំព្យូទ័រ": "Computer Lab",
    "រូបភាពសកម្មភាព": "Activity Photos",
    "រូបថតអនុស្សាវរីយ៍": "Memorial Photos",
    "គ្មានការពិពណ៌នា": "No description available",
}


class AiTranslationService:
    """
    Autonomous AI Translation Engine for SchoolSM.
    Automatically translates Khmer inputs into fluent, professional English.
    """

    @classmethod
    def translate_khmer_to_english(cls, text: str, context: str = "general") -> str:
        """
        Translates a single Khmer text into English.
        """
        if not text or not str(text).strip():
            return ""

        cleaned = str(text).strip()

        # If text has no Khmer characters and is purely ASCII/Latin, return as is
        if not re.search(r'[\u1780-\u17FF]', cleaned):
            return cleaned

        # Fast exact match in dictionary first
        if cleaned in OFFLINE_DICTIONARY:
            return OFFLINE_DICTIONARY[cleaned]

        # Try Gemini AI Agent
        ai_result = cls._translate_with_gemini(cleaned, context=context)
        if ai_result:
            return ai_result

        # Fallback to smart offline dictionary/rule-based engine
        return cls._offline_fallback_translate(cleaned)

    @classmethod
    def batch_translate_fields(cls, fields_dict: dict, context: str = "general") -> dict:
        """
        Translates multiple fields at once in a single AI prompt.
        Input: {'title': '...', 'content': '...'}
        Output: {'title': '...', 'content': '...'}
        """
        if not fields_dict:
            return {}

        to_translate = {}
        result = {}

        for k, val in fields_dict.items():
            if val and str(val).strip():
                clean_val = str(val).strip()
                if re.search(r'[\u1780-\u17FF]', clean_val):
                    if clean_val in OFFLINE_DICTIONARY:
                        result[k] = OFFLINE_DICTIONARY[clean_val]
                    else:
                        to_translate[k] = clean_val
                else:
                    result[k] = clean_val
            else:
                result[k] = ""

        if not to_translate:
            return result

        # Try batch Gemini call
        batch_ai = cls._batch_translate_with_gemini(to_translate, context=context)
        if batch_ai:
            result.update(batch_ai)
            return result

        # Fallback individually
        for k, text in to_translate.items():
            result[k] = cls.translate_khmer_to_english(text, context=context)

        return result

    @classmethod
    def _translate_with_gemini(cls, text: str, context: str = "general") -> str:
        """
        Calls Gemini API using the system key rotator.
        """
        try:
            from apps.tools.gemini_rotator import gemini_rotator
            api_key = gemini_rotator.get_available_key() or getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
            if not api_key:
                return ""

            model_name = getattr(settings, 'GEMINI_MODEL', '') or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
            candidate_models = [model_name]
            if model_name != 'gemini-flash-latest':
                candidate_models.append('gemini-flash-latest')
            if 'gemini-3.5-flash' not in candidate_models:
                candidate_models.append('gemini-3.5-flash')

            system_instruction = (
                "You are an expert bilingual Khmer-English translator for Cambodian educational institutions "
                "(Ministry of Education, Youth and Sport - MoEYS). "
                "Translate the provided Khmer text into natural, professional, and grammatically accurate English. "
                "Preserve proper nouns, dates, numbers, and official formatting. "
                "Output ONLY the translated English text with NO commentary, NO quotes, NO explanation."
            )

            prompt = f"Context: {context}\nKhmer text to translate:\n{text}\n\nEnglish Translation:"

            for target_model in candidate_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2048,
                        }
                    }
                    resp = requests.post(url, json=payload, timeout=3.0)
                    if resp.status_code == 200:
                        gemini_rotator.mark_success(api_key)
                        res_json = resp.json()
                        parts = res_json.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                        text_parts = [p.get('text', '') for p in parts if not p.get('thought') and p.get('text')]
                        if not text_parts:
                            text_parts = [p.get('text', '') for p in parts if p.get('text')]
                        translated = "\n".join(text_parts).strip()
                        # Remove enclosing quotes if any
                        if (translated.startswith('"') and translated.endswith('"')) or (translated.startswith("'") and translated.endswith("'")):
                            translated = translated[1:-1].strip()
                        if translated:
                            return translated
                    elif resp.status_code == 429:
                        gemini_rotator.mark_rate_limited(api_key)
                        break
                    elif resp.status_code in [401, 403]:
                        gemini_rotator.mark_invalid(api_key)
                        break
                except requests.exceptions.RequestException as rex:
                    logger.debug(f"Gemini network error: {rex}")
                    break
                except Exception as ex:
                    logger.debug(f"Gemini translation exception on {target_model}: {ex}")
                    continue
        except Exception as e:
            logger.error(f"Error calling Gemini translation: {e}")

        return ""

    @classmethod
    def _batch_translate_with_gemini(cls, fields_dict: dict, context: str = "general") -> dict:
        """
        Translates a dictionary of fields in a single Gemini JSON call.
        """
        try:
            from apps.tools.gemini_rotator import gemini_rotator
            api_key = gemini_rotator.get_available_key() or getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
            if not api_key:
                return {}

            model_name = getattr(settings, 'GEMINI_MODEL', '') or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
            candidate_models = [model_name, 'gemini-flash-latest']

            system_instruction = (
                "You are an expert bilingual Khmer-to-English translator for an educational portal. "
                "You receive a JSON object of Khmer fields. Translate the values of each key into professional English. "
                "Return ONLY a valid JSON object matching the exact same keys with translated English string values. "
                "Do NOT wrap in markdown backticks."
            )

            prompt = (
                f"Context: {context}\n"
                f"JSON to translate:\n"
                f"{json.dumps(fields_dict, ensure_ascii=False, indent=2)}\n\n"
                f"JSON Output:"
            )

            for target_model in candidate_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "generationConfig": {
                            "temperature": 0.2,
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 4096,
                        }
                    }
                    resp = requests.post(url, json=payload, timeout=15)
                    if resp.status_code == 200:
                        gemini_rotator.mark_success(api_key)
                        res_json = resp.json()
                        parts = res_json.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                        text_parts = [p.get('text', '') for p in parts if not p.get('thought') and p.get('text')]
                        raw_json_str = "\n".join(text_parts).strip()
                        # Clean backticks if any
                        if raw_json_str.startswith("```"):
                            raw_json_str = re.sub(r'^```(?:json)?\n?', '', raw_json_str)
                            raw_json_str = re.sub(r'\n?```$', '', raw_json_str)
                        parsed = json.loads(raw_json_str)
                        if isinstance(parsed, dict):
                            return parsed
                    elif resp.status_code == 429:
                        gemini_rotator.mark_rate_limited(api_key)
                        break
                    elif resp.status_code in [401, 403]:
                        gemini_rotator.mark_invalid(api_key)
                        break
                except Exception as ex:
                    logger.debug(f"Gemini batch translation error on {target_model}: {ex}")
                    continue
        except Exception as e:
            logger.error(f"Error calling Gemini batch translation: {e}")

        return {}

    @classmethod
    def _offline_fallback_translate(cls, text: str) -> str:
        """
        Rule-based and dictionary-driven offline translation fallback.
        """
        if not text:
            return ""

        # 1. Exact match in dictionary
        if text in OFFLINE_DICTIONARY:
            return OFFLINE_DICTIONARY[text]

        # 2. Phrase substitutions sorted by phrase length (longest first)
        translated = text
        for kh_phrase, en_phrase in sorted(OFFLINE_DICTIONARY.items(), key=lambda x: len(x[0]), reverse=True):
            if kh_phrase in translated:
                translated = translated.replace(kh_phrase, en_phrase)

        # 3. If no Khmer characters remain, return clean English
        if not re.search(r'[\u1780-\u17FF]', translated):
            return re.sub(r'\s+', ' ', translated).strip()

        # 4. If mostly English (less than 25% Khmer), return cleaned
        khmer_count = len(re.findall(r'[\u1780-\u17FF]', translated))
        if khmer_count / max(len(translated), 1) < 0.25:
            # Strip out dangling Khmer characters
            cleaned = re.sub(r'[\u1780-\u17FF]+', '', translated)
            return re.sub(r'\s+', ' ', cleaned).strip()

        # Fallback to general educational title
        return re.sub(r'\s+', ' ', translated).strip()

    # ==========================================================================
    # MODEL AUTO-TRANSLATION HELPERS
    # ==========================================================================

    @classmethod
    def auto_translate_announcement(cls, ann, overwrite: bool = False) -> bool:
        """
        Ensures an Announcement has English title and content.
        If blank or overwrite=True, auto-translates from Khmer fields and saves.
        """
        updated = False
        to_translate = {}
        if ann.title and (overwrite or not ann.title_en):
            to_translate['title_en'] = ann.title
        if ann.content and (overwrite or not ann.content_en):
            to_translate['content_en'] = ann.content

        if to_translate:
            translations = cls.batch_translate_fields(to_translate, context="School Announcement")
            if 'title_en' in translations and translations['title_en']:
                ann.title_en = translations['title_en']
                updated = True
            if 'content_en' in translations and translations['content_en']:
                ann.content_en = translations['content_en']
                updated = True

            if updated:
                ann.save(update_fields=['title_en', 'content_en'])
        return updated

    @classmethod
    def auto_translate_news(cls, article, overwrite: bool = False) -> bool:
        """
        Ensures a NewsArticle has English title, excerpt, and content.
        If blank or overwrite=True, auto-translates from Khmer fields and saves.
        """
        updated = False
        to_translate = {}
        if article.title and (overwrite or not article.title_en):
            to_translate['title_en'] = article.title
        if article.excerpt and (overwrite or not article.excerpt_en):
            to_translate['excerpt_en'] = article.excerpt
        if article.content and (overwrite or not article.content_en):
            to_translate['content_en'] = article.content

        if to_translate:
            translations = cls.batch_translate_fields(to_translate, context="School News Article")
            if 'title_en' in translations and translations['title_en']:
                article.title_en = translations['title_en']
                updated = True
            if 'excerpt_en' in translations and translations['excerpt_en']:
                article.excerpt_en = translations['excerpt_en']
                updated = True
            if 'content_en' in translations and translations['content_en']:
                article.content_en = translations['content_en']
                updated = True

            if updated:
                article.save(update_fields=['title_en', 'excerpt_en', 'content_en'])
        return updated

    @classmethod
    def auto_translate_school_profile(cls, profile, overwrite: bool = False) -> bool:
        """
        Ensures SchoolProfile has English fields (name_en, short_name_en, motto_en, school_type_en,
        about_school_en, street_address_en, principal_name_en).
        """
        updated_fields = []
        to_translate = {}
        if profile.name_kh and (overwrite or not profile.name_en):
            to_translate['name_en'] = profile.name_kh
        if profile.short_name and (overwrite or not profile.short_name_en):
            to_translate['short_name_en'] = profile.short_name
        if profile.motto and (overwrite or not profile.motto_en):
            to_translate['motto_en'] = profile.motto
        if profile.school_type and (overwrite or not profile.school_type_en):
            to_translate['school_type_en'] = profile.school_type
        if profile.about_school and (overwrite or not profile.about_school_en):
            to_translate['about_school_en'] = profile.about_school
        if profile.street_address and (overwrite or not profile.street_address_en):
            to_translate['street_address_en'] = profile.street_address
        if profile.principal_name and (overwrite or not profile.principal_name_en):
            to_translate['principal_name_en'] = profile.principal_name
        if getattr(profile, 'doe_name', None) and (overwrite or not getattr(profile, 'doe_name_en', None)):
            to_translate['doe_name_en'] = profile.doe_name
        if getattr(profile, 'education_levels', None) and (overwrite or not getattr(profile, 'education_levels_en', None)):
            to_translate['education_levels_en'] = profile.education_levels
        if getattr(profile, 'poe_name', None) and (overwrite or not getattr(profile, 'poe_name_en', None)):
            to_translate['poe_name_en'] = profile.poe_name
        if getattr(profile, 'ministry_name', None) and (overwrite or not getattr(profile, 'ministry_name_en', None)):
            to_translate['ministry_name_en'] = profile.ministry_name
        if getattr(profile, 'province', None) and (overwrite or not getattr(profile, 'province_en', None)):
            to_translate['province_en'] = profile.province
        if getattr(profile, 'district', None) and (overwrite or not getattr(profile, 'district_en', None)):
            to_translate['district_en'] = profile.district
        if getattr(profile, 'commune', None) and (overwrite or not getattr(profile, 'commune_en', None)):
            to_translate['commune_en'] = profile.commune
        if getattr(profile, 'village', None) and (overwrite or not getattr(profile, 'village_en', None)):
            to_translate['village_en'] = profile.village

        if to_translate:
            translations = cls.batch_translate_fields(to_translate, context="School Profile and Identity")
            for k, val in translations.items():
                if val and hasattr(profile, k):
                    setattr(profile, k, val)
                    updated_fields.append(k)

            if updated_fields:
                profile.save(update_fields=updated_fields)
                return True
        return False

    @classmethod
    def auto_translate_gallery_album(cls, album, overwrite: bool = False) -> bool:
        """
        Ensures a GalleryAlbum has English title and description.
        If blank or overwrite=True, auto-translates from Khmer fields and saves.
        """
        updated = False
        to_translate = {}
        if album.title and (overwrite or not album.title_en):
            to_translate['title_en'] = album.title
        if album.description and (overwrite or not album.description_en):
            to_translate['description_en'] = album.description

        if to_translate:
            translations = cls.batch_translate_fields(to_translate, context="School Gallery Album")
            if 'title_en' in translations and translations['title_en']:
                album.title_en = translations['title_en']
                updated = True
            if 'description_en' in translations and translations['description_en']:
                album.description_en = translations['description_en']
                updated = True

            if updated:
                album.save(update_fields=['title_en', 'description_en'])
        return updated

