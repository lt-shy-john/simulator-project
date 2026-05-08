from django.urls import path

from .. import views

urlpatterns = [
    path("", views.set_view_simulation_run, name="Create simulation run"),
    path("by-simulation-id", views.view_simulation_run_by_simulation_id, name="View simulation runs by simulation ID"),
    path("<int:id>/", views.view_simulation_run, name="View simulation run"),
    path("<int:id>/update-status", views.patch_simulation_run_status, name="Update simulation run status")
]