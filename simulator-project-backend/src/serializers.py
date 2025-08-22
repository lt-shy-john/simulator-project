from datetime import date

from .models import User, SimulationRun, RunsRecord, File, Mode

from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.core.exceptions import BadRequest
from django.http import Http404


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