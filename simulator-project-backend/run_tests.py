import pytest
import sys

sys.exit(pytest.main([
    'src/tests.py',
    '--html=reports/test_report.html',
    '--self-contained-html',
    '-v'
]))