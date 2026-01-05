"""
Minimal Django settings for multipart parser benchmarking.
"""

SECRET_KEY = "benchmark-secret-key-not-for-production"

DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

MIDDLEWARE = [
    "benchproject.middleware.MultipartParserMiddleware",
]

ROOT_URLCONF = "benchproject.urls"

WSGI_APPLICATION = "benchproject.wsgi.application"

# Use memory upload handler for benchmarks
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
]

# No limits for benchmarking
DATA_UPLOAD_MAX_MEMORY_SIZE = None
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
DATA_UPLOAD_MAX_NUMBER_FILES = None

DEFAULT_CHARSET = "utf-8"

USE_TZ = True
