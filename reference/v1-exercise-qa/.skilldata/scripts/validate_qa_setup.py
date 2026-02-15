#!/usr/bin/env python3
"""
Validate QA Setup

Validates that QA project initialization is complete and all required files exist.

Usage:
    python scripts/validate_qa_setup.py [qa-directory]

Example:
    python scripts/validate_qa_setup.py ./tests
"""

import sys
import re
from pathlib import Path

def validate_qa_setup(base_path):
    """Validate QA project setup."""

    errors = []
    warnings = []

    # Required directories
    required_dirs = [
        "tests/docs",
        "tests/docs/templates",
        "tests/docs/reports",
        "tests/e2e",
        "tests/fixtures",
        "tests/scripts"
    ]

    # Required files
    required_files = [
        "tests/docs/README.md",
        "tests/docs/01-TEST-STRATEGY.md",
        "tests/docs/02-CLI-TEST-CASES.md",
        "tests/docs/03-WEB-TEST-CASES.md",
        "tests/docs/04-API-TEST-CASES.md",
        "tests/docs/05-SECURITY-TEST-CASES.md",
        "tests/docs/BASELINE-METRICS.md",
        "tests/docs/QA-HANDOVER-INSTRUCTIONS.md",
        "tests/docs/MASTER-QA-PROMPT.md",
        "tests/docs/templates/TEST-EXECUTION-TRACKING.csv",
        "tests/docs/templates/BUG-TRACKING-TEMPLATE.csv",
        "tests/docs/templates/WEEKLY-PROGRESS-REPORT.md",
        "tests/docs/templates/DAY-1-ONBOARDING-CHECKLIST.md",
    ]

    print(f"\n{'='*60}")
    print(f"QA SETUP VALIDATION")
    print(f"{'='*60}\n")
    print(f"Base Path: {base_path}\n")

    # Check directories
    print("📁 Checking directories...")
    for dir_path in required_dirs:
        full_path = base_path / dir_path
        if full_path.exists():
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ❌ {dir_path} - MISSING")
            errors.append(f"Missing directory: {dir_path}")

    print()

    # Check files
    print("📄 Checking required files...")
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            if size == 0:
                print(f"   ⚠️  {file_path} - EMPTY")
                warnings.append(f"Empty file: {file_path}")
            else:
                print(f"   ✅ {file_path} ({size} bytes)")
        else:
            print(f"   ❌ {file_path} - MISSING")
            errors.append(f"Missing file: {file_path}")

    print()

    # Validate CSV structure
    print("📊 Validating CSV files...")
    csv_files = [
        ("TEST-EXECUTION-TRACKING.csv", ['Test Case ID', 'Category', 'Priority', 'Status', 'Result', 'Bug ID']),
        ("BUG-TRACKING-TEMPLATE.csv", ['Bug ID', 'Title', 'Severity', 'Status', 'Reported Date'])
    ]

    for csv_file, required_columns in csv_files:
        csv_path = base_path / "tests/docs/templates" / csv_file
        if csv_path.exists():
            try:
                with open(csv_path, 'r') as f:
                    header = f.readline().strip().split(',')
                    missing_cols = [col for col in required_columns if col not in header]
                    if missing_cols:
                        print(f"   ⚠️  {csv_file} - Missing columns: {', '.join(missing_cols)}")
                        warnings.append(f"{csv_file} missing columns: {', '.join(missing_cols)}")
                    else:
                        print(f"   ✅ {csv_file} - Structure valid")
            except Exception as e:
                print(f"   ❌ {csv_file} - Error reading: {e}")
                errors.append(f"Error reading {csv_file}: {e}")
        else:
            print(f"   ❌ {csv_file} - File not found")

    print()

    # Check test case documents have content
    print("📝 Validating test case documents...")
    test_docs = [
        "02-CLI-TEST-CASES.md",
        "03-WEB-TEST-CASES.md",
        "04-API-TEST-CASES.md",
        "05-SECURITY-TEST-CASES.md"
    ]

    for doc in test_docs:
        doc_path = base_path / "tests/docs" / doc
        if doc_path.exists():
            content = doc_path.read_text()
            # Check for test case pattern TC-XXX-YYY
            test_cases = re.findall(r'TC-[A-Z]+-\d{3}', content)
            if test_cases:
                print(f"   ✅ {doc} - Found {len(set(test_cases))} unique test cases")
            else:
                print(f"   ⚠️  {doc} - No test cases found (might be template only)")
                warnings.append(f"{doc} contains no test case IDs")
        else:
            print(f"   ❌ {doc} - File not found")

    print()

    # Summary
    print(f"{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}\n")

    if errors:
        print(f"❌ Errors: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
        print()

    if warnings:
        print(f"⚠️  Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"   - {warning}")
        print()

    if not errors and not warnings:
        print("✅ All checks passed! QA setup is complete.\n")
        return True
    elif not errors:
        print("⚠️  Setup is functional but has warnings. Review above.\n")
        return True
    else:
        print("❌ Setup is incomplete. Fix errors above and re-run validation.\n")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        base_path = Path(".")
    else:
        base_path = Path(sys.argv[1])

    if not base_path.exists():
        print(f"❌ Error: Directory not found: {base_path}")
        sys.exit(1)

    success = validate_qa_setup(base_path.resolve())
    sys.exit(0 if success else 1)
