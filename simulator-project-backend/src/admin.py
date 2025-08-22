from django.contrib import admin

from .models import SimulationRun
from .models import RunsRecord
from .models import File
from .models import Mode

# Register your models here.
admin.site.register(SimulationRun)
admin.site.register(RunsRecord)
admin.site.register(File)
admin.site.register(Mode)