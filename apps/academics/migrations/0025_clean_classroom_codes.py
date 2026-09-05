# Generated to clean existing classroom codes
from django.db import migrations


def clean_existing_classroom_codes(apps, schema_editor):
    Classroom = apps.get_model('academics', 'Classroom')
    prefixes = ['ថ្នាក់ទី', 'ថ្នាក់ ទី', 'ថ្នាក់', 'ថ្នាក់ ']
    for c in Classroom.objects.all():
        if c.code:
            code = str(c.code).strip()
            orig = code
            changed = True
            while changed:
                changed = False
                for pfx in prefixes:
                    if code.startswith(pfx):
                        code = code[len(pfx):].strip()
                        changed = True
            if code != orig:
                c.code = code
                c.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0024_alter_classroom_code_alter_classroom_name'),
    ]

    operations = [
        migrations.RunPython(clean_existing_classroom_codes, reverse_code=migrations.RunPython.noop),
    ]
