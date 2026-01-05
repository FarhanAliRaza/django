"""
WSGI application with default Django parser.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "benchproject.settings")
application = get_wsgi_application()
