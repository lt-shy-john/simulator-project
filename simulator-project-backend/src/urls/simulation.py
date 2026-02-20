from django.urls import path

from .. import views

urlpatterns = [
    path("<int:id>/", views.get_patch_delete_simulation_by_id, name="Operation on simulation set  by ID"),
    path("", views.set_view_simulation, name="Get all/ record simulation"),
    path("simulation-run/status", views.view_simulation_runs_status, name="Get simulation run status"),
    path("<int:id>/update_date", views.patch_simulation_date, name="Update simulation run")
]