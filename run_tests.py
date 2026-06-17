import argparse
import sys
import os
import time
import xml.etree.ElementTree as ET
import json

def parse_xml_and_write_json(xml_path, json_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        tests = 0
        failures = 0
        errors = 0
        skipped = 0
        duration = 0.0
        
        if root.tag == "testsuite":
            tests = int(root.attrib.get("tests", 0))
            failures = int(root.attrib.get("failures", 0))
            errors = int(root.attrib.get("errors", 0))
            skipped = int(root.attrib.get("skipped", 0))
            duration = float(root.attrib.get("time", 0.0))
        elif root.tag == "testsuites":
            for suite in root.findall("testsuite"):
                tests += int(suite.attrib.get("tests", 0))
                failures += int(suite.attrib.get("failures", 0))
                errors += int(suite.attrib.get("errors", 0))
                skipped += int(suite.attrib.get("skipped", 0))
                duration += float(suite.attrib.get("time", 0.0))
                
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_tests": tests,
            "passed": tests - failures - errors - skipped,
            "failed": failures + errors,
            "skipped": skipped,
            "duration_seconds": duration,
            "status": "PASS" if (failures + errors) == 0 else "FAIL"
        }
        
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        return summary
    except Exception as e:
        print(f"Failed to generate JSON summary: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Auto-Blogging Backend System - E2E Test Runner")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "5"], help="Filter execution by test tier (1-5)")
    parser.add_argument("--feature", choices=["F1", "F2", "F3", "F4", "F5", "F6"], help="Filter execution by feature group (F1-F6)")
    
    args = parser.parse_args()
    
    try:
        import pytest
    except ImportError:
        print("pytest is not installed. Installing pytest, pandas, etc...")
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pandas"], check=True)
            import pytest
        except Exception as e:
            print(f"Failed to install pytest dependencies: {e}")
            sys.exit(1)
            
    os.makedirs("outputs/test-reports", exist_ok=True)
    xml_report_path = "outputs/test-reports/results.xml"
    json_report_path = "outputs/test-reports/summary.json"
    
    pytest_args = []
    
    tier_files = {
        "1": "tests/e2e/test_tier1_feature_coverage.py",
        "2": "tests/e2e/test_tier2_boundary_cases.py",
        "3": "tests/e2e/test_tier3_cross_feature.py",
        "4": "tests/e2e/test_tier4_scenarios.py",
        "5": "tests/e2e/test_tier5_stress_concurrency.py"
    }
    
    if args.tier:
        pytest_args.append(tier_files[args.tier])
    else:
        pytest_args.extend(list(tier_files.values()))
        
    feature_filters = {
        "F1": "test_tc10 or test_tc70",
        "F2": "test_tc20 or test_tc80",
        "F3": "test_tc30 or test_tc90",
        "F4": "test_tc40 or test_tc100",
        "F5": "test_tc50 or test_tc110",
        "F6": "test_tc60 or test_tc120"
    }
    
    if args.feature:
        filter_expr = feature_filters[args.feature]
        pytest_args.extend(["-k", filter_expr])
        
    pytest_args.extend([
        f"--junitxml={xml_report_path}",
        "-v"
    ])
    
    print(f"Running pytest with arguments: {' '.join(pytest_args)}")
    
    exit_code = pytest.main(pytest_args)
    
    summary = None
    if os.path.exists(xml_report_path):
        summary = parse_xml_and_write_json(xml_report_path, json_report_path)
        
    print("\n" + "="*40)
    print("TEST EXECUTION SUMMARY")
    print("="*40)
    if summary:
        print(f"Total Tests Run: {summary['total_tests']}")
        print(f"Passed:          {summary['passed']}")
        print(f"Failed:          {summary['failed']}")
        print(f"Skipped:         {summary['skipped']}")
        print(f"Duration:        {summary['duration_seconds']:.2f} seconds")
        print(f"Status:          {summary['status']}")
    else:
        print(f"Pytest exited with code: {exit_code}")
    print("="*40)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
