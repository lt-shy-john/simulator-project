import pytest
import sys
import os
import json
from datetime import datetime

def export_endpoint_coverage(endpoint_log):
    lines = []
    lines.append("\n===== ENDPOINT & STATUS COVERAGE =====")
    lines.append(f"{'Method':<8} {'Endpoint':<50} {'Status':<10} {'Result'}")
    lines.append("-" * 85)
    for log in endpoint_log:
        result = 'PASS' if log['passed'] else 'FAIL'
        lines.append(f"{log['method']:<8} {log['endpoint']:<50} {log['actual']:<10} {result}")
    lines.append(f"\nTotal endpoints tested: {len(endpoint_log)}")

    output = '\n'.join(lines)
    print(output)

    date = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('reports', exist_ok=True)
    filepath = f'reports/endpoint_coverage_{date}.txt'
    print(f"DEBUG: Writing to {filepath}")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(output)
    print(f"DEBUG: Successfully written to {filepath}")

# Run pytest and save exit code
exit_code = pytest.main([
    'src/tests.py',
    '--html=reports/test_report.html',
    '--self-contained-html',
    '-v'
])

# Read endpoint log written by assertStatus during tests
try:
    with open('reports/endpoint_log.json', 'r', encoding='utf-8') as f:
        endpoint_log = json.load(f)
    print(f"DEBUG: Loaded {len(endpoint_log)} entries from endpoint_log.json")
    export_endpoint_coverage(endpoint_log)
except FileNotFoundError:
    print("No endpoint log found — skipping endpoint coverage export.")
except Exception as e:
    print(f"Error exporting endpoint coverage: {e}")

# Exit with pytest exit code
sys.exit(exit_code)