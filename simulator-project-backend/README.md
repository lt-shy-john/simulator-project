# Simulation Project Backend

Part of the whole simulation full stack system. This is where the simulation happens.  

This is part of the whole 3-tier architecture: 

![](../frontend/public/docs/Summary_Architecture.png)

## Features

## Getting Started
To start this application, please run `py manage.py runserver`. This will run the application under port `8000` the default port. 

To check the OpenAPI/ Swagger docs, use `/api/schema/swagger-ui/`. This will provide the list of endpoints. By running into status 404 it will also lists the endpoints available. 

### Installation
You need to install the following libraries
* `django`
* `django-cors-headers`
* `djangorestframework`
* `drf-spectacular`

## Testing
At the root of the Simulation Project Backend folder, run `py manage.py test`. 

To export the test results, you can run `py manage.py test > test_result_{date}.txt`. 

## Contributing