from datetime import date

from .models import User, SimulationRun, RunsRecord, File, Mode

from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.core.exceptions import BadRequest
from django.http import Http404
from django.utils import timezone
from django.db.models import Max


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username']


class SimulationSetterSerializer(serializers.ModelSerializer):
    createdBy = UserSerializer(read_only=True)

    class Meta:
        model = SimulationRun
        fields = ['name', 'numberOfAgent', 'simulationPeriod', 'createdBy']

    def create(self, validated_data):
        validated_data['createDate'] = date.today().strftime("%Y%m%d")
        try:
            validated_data['createdBy'] = get_object_or_404(User, username=self.initial_data['createdBy']['username'])
        except Http404 as e:
            print(f'{e} User not found. ')
        return super(SimulationSetterSerializer, self).create(validated_data)


class SimulationGetterSerializer(serializers.HyperlinkedModelSerializer):
    createdBy = UserSerializer()
    class Meta:
        model = SimulationRun
        fields = ['id', 'name', 'numberOfAgent', 'simulationPeriod', 'createDate', 'createdBy']


class SimulationFullSerializer(serializers.ModelSerializer):
    createdBy = UserSerializer()
    class Meta:
        model = SimulationRun
        fields = '__all__'


class RunsRecordSetterSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunsRecord
        fields = ['simulation_id', 'runTime']


class FileSetterSerializer(serializers.ModelSerializer):
    simulation = SimulationGetterSerializer(read_only=True)
    class Meta:
        model = File
        fields = ['filename', 'simulation_id', 'location', 'simulation']
        write_only_fields = ['simulation_id']

    def create(self, validated_data):
        validated_data['createDate'] = date.today().strftime("%Y%m%d")
        get_object_or_404(SimulationRun, pk=self.initial_data['simulation_id'])
        try:
            validated_data['simulation'] = get_object_or_404(SimulationRun, pk=self.initial_data['simulation_id'])
        except Http404 as e:
            print(f'{e} Simulation run {self.initial_data["simulation_id"]} not found. ')
            raise BadRequest
        return super(FileSetterSerializer, self).create(validated_data)

class FileGetterSerializer(serializers.ModelSerializer):
    simulation = SimulationGetterSerializer(read_only=True)
    class Meta:
        model = File
        fields = ['id', 'filename', 'simulation_id', 'location', 'simulation']
        write_only_fields = ['simulation_id']


class ModeSetterSerializer(serializers.ModelSerializer):
    createdBy = UserSerializer(read_only=True)
    class Meta:
        model = Mode
        fields = ['simulation_id', 'name', 'location', 'createdBy']

    def create(self, validated_data):
        validated_data['createDate'] = date.today().strftime("%Y%m%d")
        get_object_or_404(SimulationRun, pk=self.initial_data['simulation_id'])
        try:
            validated_data['createdBy'] = get_object_or_404(User, username=self.initial_data['createdBy']['username'])
        except Http404 as e:
            print(f'{e} User not found. ')
        return super(ModeSetterSerializer, self).create(validated_data)

class ModeGetterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mode
        fields = '__all__'

class SimulationRunFullSerializer(serializers.ModelSerializer):
    createdBy = UserSerializer(read_only=True)

    class Meta:
        model = RunsRecord
        fields = '__all__'

    def create(self, validated_data):
        validated_data['status'] = "CREATED"
        validated_data['runTime'] = date.today().strftime("%Y%m%d")
        get_object_or_404(SimulationRun, pk=self.initial_data['simulation_id'])
        try:
            validated_data['createdBy'] = get_object_or_404(User, username=self.initial_data['createdBy']['username'])
        except Http404 as e:
            print(f'{e} User not found. ')
        return super(SimulationRunFullSerializer, self).create(validated_data)

class SimulationRunSetterSerializer(serializers.ModelSerializer):
    # additional input
    simulation_id = serializers.IntegerField(write_only=True)
    createdBy = serializers.DictField(write_only=True)

    # additional output fields
    id = serializers.IntegerField(read_only=True)
    simulation = serializers.PrimaryKeyRelatedField(read_only=True)
    createdBy_username = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(read_only=True)
    runTime = serializers.DateTimeField(read_only=True)


    class Meta:
        model = RunsRecord
        fields = [
            "id",
            "simulation",
            "simulation_id",
            "createdBy",
            "createdBy_username",
            "status",
            "runTime"
        ]


    def get_createdBy_username(self, obj):
        return obj.createdBy.username


    def create(self, validated_data):
        simulation_id = validated_data.pop("simulation_id")
        created_by_data = validated_data.pop("createdBy")

        # Lookup user
        try:
            user = User.objects.get(username=created_by_data["username"])
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"createdBy": f"User {created_by_data['username']} does not exist"}
            )

        # Lookup simulation
        try:
            simulation = SimulationRun.objects.get(pk=simulation_id)
        except SimulationRun.DoesNotExist:
            raise serializers.ValidationError(
                {"simulation_id": f"Simulation {simulation_id} does not exist"}
            )

        # Generate id automatically (example: max+1)
        max_id = RunsRecord.objects.aggregate(max_id=Max('id'))['max_id'] or 0
        new_id = max_id + 1

        return RunsRecord.objects.create(
            id=new_id,
            simulation=simulation,
            createdBy=user,
            status='CREATED',
            runTime=timezone.now()
        )

class SimulationRunStatusPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunsRecord
        fields = ['status']