#!/usr/bin/env bash
# Быстрый запуск: ./setup.sh  → сайт на http://127.0.0.1:8000, админка /admin (admin / admin12345)
set -e
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --with-admin
python manage.py runserver
