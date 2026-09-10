#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py ensure_system_defaults
python manage.py seed_locations

# Live student, teacher, and exam records are strictly preserved.
# Master roster imports can be triggered manually by the administrator when desired.
