from django.db import models
from django.contrib.auth.models import User

class SimulationRun(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(default='')
    numberOfAgent = models.IntegerField()
    simulationPeriod = models.IntegerField()
    createDate = models.DateField()
    updateDate = models.DateField(null=True)
    createdBy = models.ForeignKey(User, on_delete=models.RESTRICT, null=True)

class RunsRecord(models.Model):
    class Status(models.TextChoices):
        # Value stored in the database, Human-readable label
        CREATED = 'CREATED', 'Created'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        DONE = 'DONE', 'Done'
        ERROR = 'ERROR', 'Error'
        UNDETERMINED = 'UNDERTERMINED', 'Undetermined'
    simulation = models.ForeignKey(SimulationRun, on_delete=models.RESTRICT, null=True)
    status = models.TextField(choices=Status.choices,default=Status.UNDETERMINED)
    runTime = models.DateTimeField()
    createdBy = models.ForeignKey(User, on_delete=models.RESTRICT, null=True)

class File(models.Model):
    id = models.IntegerField(primary_key=True)
    filename = models.TextField()
    simulation = models.ForeignKey(SimulationRun, on_delete=models.RESTRICT, null=True)
    location = models.TextField()
    createDate = models.DateField()
    updateDate = models.DateField(null=True)

class Mode(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ManyToManyField(User)
    simulation = models.ForeignKey(SimulationRun, on_delete=models.RESTRICT, null=True)
    name = models.TextField()
    location = models.TextField()
    createDate = models.DateField()
    updateDate = models.DateField(null=True)
    createdBy = models.TextField()
