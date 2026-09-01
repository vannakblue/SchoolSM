#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_locations
python manage.py import_students_from_excel --file 2025-2026.xlsm --year 2025-2026



