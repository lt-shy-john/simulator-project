from django.urls import path

from .. import views

urlpatterns = [
    path("<int:id>/", views.get_simulation_by_id, name="Get simulation"),
    path("", views.set_view_simulation, name="Get all/ record simulation"),
    path("<int:id>/update_date", views.patch_simulation_date, name="Update simulation run")
]