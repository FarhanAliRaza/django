from django.urls import path
from benchproject import views

urlpatterns = [
    path("health", views.health),
    path("django", views.django_parser),
    path("python-multipart", views.python_multipart),
    path("multipart", views.multipart_lib),
]
