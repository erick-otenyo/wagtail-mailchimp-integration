import os
import django
from django.conf import settings

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "wagtailmailchimp"))
SANDBOX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "sandbox"))

SECRET_KEY = "django-insecure-od#(q8@gly39*2_to74w6eg78_5@*y53%w*tvgo0yvuenv-_t="

INSTALLED_APPS = [
    "wagtailmailchimp",

    "wagtail",
    "taggit",

    "django.contrib.auth",
    "django.contrib.contenttypes",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(SANDBOX_DIR, "db.sqlite3"),
    }
}


def boot_django():
    settings.configure(
        BASE_DIR=BASE_DIR,
        DEBUG=True,
        INSTALLED_APPS=INSTALLED_APPS,
        TIME_ZONE="UTC",
        USE_TZ=True,
        SECRET_KEY=SECRET_KEY,
        DATABASES=DATABASES,
    )
    django.setup()
