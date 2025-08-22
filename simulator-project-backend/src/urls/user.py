from django.urls import path

from .. import views

urlpatterns = [
    path("<int:id>/", views.get_user_by_id, name="Get user by ID"),
    path("<str:username>/", views.get_user_by_username, name="Get user by user name"),
    path("", views.set_user, name="Create user"),
    path("<int:id>/username", views.patch_username, name="Change user name")
]