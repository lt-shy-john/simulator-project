#!/bin/bash
source .venv/Scripts/activate
coverage run run_tests.py
coverage html