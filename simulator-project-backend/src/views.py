import json
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

from drf_spectacular.utils import extend_schema, OpenApiResponse

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SimulationRun, RunsRecord, File, Mode
from .serializers import UserSerializer, SimulationSetterSerializer, SimulationGetterSerializer, RunsRecordSetterSerializer, FileSetterSerializer, FileGetterSerializer, ModeSetterSerializer, ModeGetterSerializer, SimulationRunFullSerializer, SimulationRunSetterSerializer, SimulationRunStatusPatchSerializer

# Create your views here.
@api_view(['GET'])
def index(request):
    return HttpResponse("Hello, world. You're at the simulation index.")

@api_view(['GET'])
def get_user_by_id(request, id):
    user = get_object_or_404(User, pk=id)
    return Response(json.dumps(user))

@api_view(['GET'])
def get_user_by_username(request, username):
    return User.objects.get_by_natural_key(username)


# todo: Find a way to disable this securely
@csrf_exempt
@extend_schema(
        summary="Create new user",
        request=UserSerializer,
        responses={
            201: OpenApiResponse(response=UserSerializer,
                                 description='Created'),
            400: OpenApiResponse(description='Invalid parameter')
        }, methods=["POST"]
    )
@api_view(['POST'])
def set_user(request):
    if request.method != 'POST':
        raise HttpResponseNotAllowed('POST')
    serializer = UserSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['PATCH'])
def patch_username(request):
    return None

@extend_schema(
        summary="Get simulation record by ID",
        request=SimulationGetterSerializer,
        responses={
            200: OpenApiResponse(response=SimulationGetterSerializer,
                                 description='Created'),
            404: OpenApiResponse(description='Simulation not found')
        }, methods=["POST"]
    )
@extend_schema(
        summary="Delete simulation record",
        request=SimulationGetterSerializer,
        responses={
            204: OpenApiResponse(response=SimulationGetterSerializer,
                                 description='Deleted'),
            404: OpenApiResponse(description='Simulation not found')
        }, methods=["DELETE"]
    )
@extend_schema(
        summary="Patch existing simulation set by ID",
        request=SimulationGetterSerializer,
        responses={
            200: OpenApiResponse(response=SimulationGetterSerializer,
                                 description='Success'),
            204: OpenApiResponse(response=SimulationGetterSerializer,
                                 description='No content'),
        }, methods=["PATCH"]
    )
@api_view(['GET', 'DELETE', 'PATCH'])
def get_patch_delete_simulation_by_id(request, id):
    if request.method == 'GET':
        simulation = get_object_or_404(SimulationRun, pk=id)
        serializer = SimulationGetterSerializer(simulation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'PATCH':
        simulation = get_object_or_404(SimulationRun, pk=id)
        serializer = SimulationGetterSerializer(simulation, context={'request': request}, data=request.data, partial=True)
        if 'createdBy' in request.data:
            # todo: check user if registered
            del request.data['createdBy']
        request.data['updateDate'] = datetime.today().strftime('%Y-%m-%d')
        if serializer.is_valid():
            serializer.update(simulation, request.data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        simulation = get_object_or_404(SimulationRun, pk=id)
        SimulationRun.objects.filter(pk=id).delete()
        return Response(f"Simulation {id} has been deletd. ", status=status.HTTP_204_NO_CONTENT)

@csrf_exempt
@extend_schema(
        summary="Set new simulation set",
        request=SimulationSetterSerializer,
        responses={
            201: OpenApiResponse(response=SimulationSetterSerializer,
                                 description='Created'),
            400: OpenApiResponse(description='Invalid parameter')
        }, methods=["POST"]
    )
@extend_schema(
        summary="View existing simulation set",
        responses={
            200: OpenApiResponse(response=SimulationGetterSerializer,
                                 description='Success')
        }, methods=["GET"]
    )
@api_view(['GET', 'POST'])
def set_view_simulation(request):
    if request.method == 'GET':
        simulations = SimulationRun.objects.all().order_by('id')
        serializer = SimulationGetterSerializer(simulations, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        serializer = SimulationSetterSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    else:
        raise HttpResponseNotAllowed('POST')


@csrf_exempt
@api_view(['PATCH'])
def patch_simulation_date(request, id):
    return None

@api_view(['GET'])
@extend_schema(
        summary="Get mode document",
        responses={
            200: OpenApiResponse(response=ModeGetterSerializer,
                                 description='Success'),
            404: OpenApiResponse(description='Simulation not found')
        }
    )
def get_mode_by_id(request, id):
    mode = get_object_or_404(Mode, pk=id)
    serializer = ModeGetterSerializer(mode, context={'request': request})
    return Response(serializer.data)

@csrf_exempt
@api_view(['PATCH'])
def patch_mode_by_id(request, id):
    return None

@csrf_exempt
@extend_schema(
        summary="Create new mode document",
        request=ModeSetterSerializer,
        responses={
            201: OpenApiResponse(response=ModeSetterSerializer,
                                 description='Created'),
            400: OpenApiResponse(description='Invalid parameter'),
            404: OpenApiResponse(description='Simulation not found')
        }
    )
@api_view(['POST'])
def set_mode(request):
    if request.method != 'POST':
        raise HttpResponseNotAllowed('POST')
    serializer = ModeSetterSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@extend_schema(
        summary="Get mode document",
        responses={
            200: OpenApiResponse(response=FileGetterSerializer,
                                 description='Success'),
            404: OpenApiResponse(description='File not found')
        }
    )
def get_file_by_id(request, id):
    file = get_object_or_404(File, pk=id)
    serializer = FileGetterSerializer(file, context={'request': request})
    return Response(serializer.data)

@csrf_exempt
@extend_schema(
        summary="Record file item on database",
        request=FileSetterSerializer,
        responses={
            201: OpenApiResponse(response=FileSetterSerializer,
                                 description='Created'),
            400: OpenApiResponse(description='Invalid parameter'),
            404: OpenApiResponse(description='Simulation not found')
        }
    )
@api_view(['POST'])
def set_file(request):
    if request.method != 'POST':
        raise HttpResponseNotAllowed('POST')
    serializer = FileSetterSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
        summary="Create new mode document",
        request=SimulationRunSetterSerializer,
        responses={
            201: OpenApiResponse(response=SimulationRunSetterSerializer,
                                 description='OK'),
            400: OpenApiResponse(description='Invalid parameter'),
            404: OpenApiResponse(description='Simulation run not found'),
            409: OpenApiResponse(description='Simulation is running')
        }
    )
@api_view(['POST'])
def set_simulation_run(request):
    serializer = SimulationRunSetterSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        runRecord = serializer.save()
        print("Saved instance PK:", runRecord.pk)
        print("Exists in DB:", SimulationRun.objects.filter(pk=runRecord.pk).exists())
        output_serialiser = SimulationRunFullSerializer(runRecord)
        return Response(output_serialiser.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
        summary="View simulation run",
        responses={
            200: OpenApiResponse(response=SimulationRunFullSerializer,
                                 description='OK'),
            400: OpenApiResponse(description='Invalid parameter'),
            404: OpenApiResponse(description='Simulation run not found')
        }
    )
@api_view(['GET'])
def view_simulation_run(request, id):
    runRecord = get_object_or_404(RunsRecord, pk=id)
    serializer = SimulationRunFullSerializer(runRecord, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

@extend_schema(
        summary="Create new mode document",
        request=SimulationRunStatusPatchSerializer,
        responses={
            200: OpenApiResponse(response=SimulationRunFullSerializer,
                                 description='OK'),
            400: OpenApiResponse(description='Invalid parameter'),
            404: OpenApiResponse(description='Simulation run not found')
        }
    )
@api_view(['PATCH'])
def patch_simulation_run_status(request, id):
    runsRecord = get_object_or_404(RunsRecord, pk=id)
    request.data['status'] = request.data['status'].upper()
    serializer = SimulationRunStatusPatchSerializer(runsRecord, context={'request': request}, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.update(runsRecord, request.data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)