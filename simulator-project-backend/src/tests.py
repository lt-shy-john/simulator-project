from unittest import TestCase
import json

from .views import *

from django.urls import reverse
from rest_framework.test import APIClient

# Create your tests here.
class SimulationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def testGetAllSimulationSuccess(self):
        # Act
        response = self.client.get(reverse('Get all/ record simulation'))
        response_body = json.loads(response.content)
        # Assert
        # print(response_body)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_body[0].get('id'), 1)

    def testGetSimulationByIdSuccess(self):
        # Arrange
        actual_id = 1
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Operation on simulation set  by ID', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_body.get('id'), actual_id)

    def testGetSimulationByIdNonexistentId(self):
        # Arrange
        actual_id = 1000000
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Operation on simulation set  by ID', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testSetSimulationSuccess(self):
        # Arrange
        request = {'name': 'Test Simulation', 'numberOfAgent': 3, 'simulationPeriod': 10, 'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.post(reverse('Get all/ record simulation'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testSetSimulationInvalidNTType(self):
        # Arrange
        request = {'name': 'Test Simulation', 'numberOfAgent': 'hello', 'simulationPeriod': 10,
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.post(reverse('Get all/ record simulation'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testSetSimulationInvalidUser(self):
        # Arrange
        request = {'name': 'Test Simulation', 'numberOfAgent': '3', 'simulationPeriod': 10,
                   'createdBy': {'username': 'wrong_admin'}}

        # Act
        response = self.client.post(reverse('Get all/ record simulation'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        # We will forgive the error and log the issue, user should be added manually after
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testPatchSimulationSuccess(self):
        # Arrange
        actual_id = 1
        param = {'id': actual_id}

        # Act
        response = self.client.patch(reverse('Operation on simulation set  by ID', kwargs=param))
        response_body = json.loads(response.content)
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def testPatchSimulationDateSuccess(self):
        # Arrange
        actual_id = 1
        param = {'id': actual_id}

        # Act
        response = self.client.patch(reverse('Update simulation run', kwargs=param))
        response_body = json.loads(response.content)
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def testPatchSimulationDateNonexistentId(self):
        # Arrange
        actual_id = 'string'
        param = {'id': actual_id}

        # Act
        response = self.client.patch(reverse('Update simulation run', kwargs=param))
        response_body = json.loads(response.content)
        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testPatchSimulationDateInvalidIdType(self):
        # Arrange
        actual_id = 'string'
        param = {'id': actual_id}

        # Act
        response = self.client.patch(reverse('Update simulation run', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def testGetFileRecordByIdSuccess(self):
        # Arrange
        actual_id = 1
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Get file content', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_body.get('id'), 1)

    def testGetFileRecordByIdNonexistentId(self):
        # Arrange
        actual_id = 999
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Get file content', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testSetFileRecordSuccess(self):
        # Arrange
        request = {'filename': 'hello.txt', 'simulation_id': 1, 'location': 10,
                   'createdBy': {'username': 'root'}}

        # Act
        response = self.client.post(reverse('Upload file record'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testSetFileRecordNonexistentSimulationId(self):
        # Arrange
        request = {'filename': 'hello.txt', 'simulation_id': 9999, 'location': 10,
                   'createdBy': {'username': 'root'}}

        # Act
        response = self.client.post(reverse('Upload file record'), request, format='json')
        # response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ModeTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def testGetModeByIdSuccess(self):
        # Arrange
        actual_id = 1
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Get mode metadata', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_body.get('id'), 1)

    def testGetModeByIdNonexistentId(self):
        # Arrange
        actual_id = 9999
        param = {'id': actual_id}

        # Act
        response = self.client.get(reverse('Get mode metadata', kwargs=param))
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testSetModeSuccess(self):
        # Arrange
        request = {'simulation_id': 1, 'name': 'Mode name', 'location': 10,
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.post(reverse('Create mode'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testSetModeNonexistentSimulationId(self):
        # Arrange
        request = {'simulation_id': 999, 'name': 'Mode name', 'location': 'root',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.post(reverse('Create mode'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testSetModeNonexistentLocation(self):
        request = {'simulation_id': 1, 'name': 'Mode name', 'location': 'wrong_location',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.post(reverse('Create mode'), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testPatchModeSuccess(self):
        actual_id = 1
        param = {'id': actual_id}
        request = {'simulation_id': 1, 'name': 'Mode name', 'location': 'wrong_location',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.patch(reverse('Update mode', kwargs=param), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def testPatchModeNonexistentId(self):
        actual_id = 999
        param = {'id': actual_id}
        request = {'simulation_id': 1, 'name': 'Mode name', 'location': 'root',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.patch(reverse('Update mode', kwargs=param), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testPatchModeNonexistentSimulationId(self):
        actual_id = 999
        param = {'id': actual_id}
        request = {'simulation_id': 999, 'name': 'Mode name', 'location': 'root',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.patch(reverse('Update mode', kwargs=param), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testPatchModeNonexistentLocation(self):
        actual_id = 1
        param = {'id': actual_id}
        request = {'simulation_id': 1, 'name': 'Mode name', 'location': 'wrong_location',
                   'createdBy': {'username': 'admin'}}

        # Act
        response = self.client.patch(reverse('Update mode', kwargs=param), request, format='json')
        response_body = json.loads(response.content)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
