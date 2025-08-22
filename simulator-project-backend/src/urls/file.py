from django.urls import path

from .. import views

urlpatterns = [
    path("<int:id>/", views.get_file_by_id, name="Get file content"),
    path("", views.set_file, name="Upload file record"),
]