# Simulation Project Backend

Part of the whole simulation full stack system. This is where the simulation happens.  

This is part of the whole 3-tier architecture: 

![](../frontend/public/docs/Summary_Architecture.png)

## Features

* Pagination is provided in GET `/simulation/` and GET `/simulation/simulation-runs/status` endpoints. Default page size is 10 and max page size is 500. Example use: `/simulations/?page=2&page_size=20` to move to page 2 and enlarge page size to 20 simulation records.

## Getting Started
To start this application, please run `py manage.py runserver`. This will run the application under port `8000` the default port. 

To check the OpenAPI/ Swagger docs, use `/api/schema/swagger-ui/`. This will provide the list of endpoints. By running into status 404 it will also lists the endpoints available. 

### Installation
You need to install the following libraries
* `django`
* `django-cors-headers`
* `djangorestframework`
* `drf-spectacular`

Add the requirements from `requirements.txt` at the root folder. It is recommended to create a virtual environment (i.e. a new `.venv` folder) at the root folder. 

## Testing
At the root of the Simulation Project Backend folder, run `bash run_reports.sh`. This will run all tests and generate three reports:

* `reports/test_report.html` — shows which tests passed or failed
* `reports/endpoint_coverage_{date}.txt` — shows which endpoints and status codes were tested
* `htmlcov/index.html` — shows line-by-line test coverage

To view the coverage report in your browser, serve it locally:
```bash
cd htmlcov
python -m http.server 8080
```
Then open `http://localhost:8080` in your browser.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.