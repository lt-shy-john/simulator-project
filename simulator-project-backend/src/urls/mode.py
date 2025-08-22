from django.urls import path

from .. import views

urlpatterns = [
    path("<int:id>/", views.get_mode_by_id, name="Get mode metadata"),
    path("<int:id>/update", views.patch_mode_by_id, name="Update mode"),
    path("", views.set_mode, name="Create mode"),
]