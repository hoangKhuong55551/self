#!/usr/bin/env bash
# Lệnh build trên Render: cài thư viện, gom file tĩnh, cập nhật database
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
