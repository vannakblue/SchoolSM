from django import template
from apps.accounts.translation_service import t, get_current_language

register = template.Library()

@register.filter(name='t')
def translate_filter(key, lang=None):
    """
    Template filter: {{ 'all_students'|t:current_language }}
    """
    return t(str(key), lang=lang or 'km')

@register.simple_tag(takes_context=True)
def lang_switch(context, kh_text, en_text):
    """
    Simple tag to cleanly output Khmer or English text based on active language:
    {% lang_switch "បញ្ជីសិស្សទាំងអស់" "All Students" %}
    """
    current_lang = context.get('current_language', 'km')
    if current_lang == 'en':
        return en_text
    return kh_text

@register.simple_tag(takes_context=True)
def trans_key(context, key, default=None):
    """
    Simple tag to translate dictionary key:
    {% trans_key 'enroll_student' %}
    """
    current_lang = context.get('current_language', 'km')
    return t(key, lang=current_lang, default=default)
