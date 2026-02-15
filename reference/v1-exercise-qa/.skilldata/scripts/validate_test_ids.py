#!/usr/bin/env python3
"""
Validate Test IDs

Validates consistency between test case documentation and tracking CSV.
Implements the Ground Truth Principle validation.

Usage:
    python scripts/validate_test_ids.py <doc-path> <csv-path>

Example:
    python scripts/validate_test_ids.py tests/docs/02-CLI-TEST-CASES.md tests/docs/templates/TEST-EXECUTION-TRACKING.csv
"""

import csv
import re
import sys
from pathlib import Path

def extract_doc_ids(doc_path):
    """Extract all TC-XXX-YYY IDs from markdown documentation."""
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = r'TC-[A-Z]+-\d{3}'
        ids = re.findall(pattern, content)
        return set(ids)
    except Exception as e:
        print(f"❌ Error reading documentation: {e}")
        return set()

def extract_csv_ids(csv_path):
    """Extract all Test Case IDs from CSV."""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            ids = []
            for row in reader:
                test_id = row.get('Test Case ID', '').strip()
                if test_id and test_id != 'Test Case ID':
                    ids.append(test_id)
            return set(ids)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return set()

def validate_sync(doc_path, csv_path):
    """Check consistency between doc and CSV."""

    doc_ids = extract_doc_ids(doc_path)
    csv_ids = extract_csv_ids(csv_path)

    if not doc_ids and not csv_ids:
        print(f"\n❌ No test case IDs found in either file!")
        return False

    matching = doc_ids & csv_ids
    csv_only = csv_ids - doc_ids
    doc_only = doc_ids - csv_ids

    consistency_rate = len(matching) / len(csv_ids) * 100 if csv_ids else 0

    print(f"\n{'='*60}")
    print(f"TEST ID VALIDATION REPORT")
    print(f"{'='*60}\n")

    print(f"📄 Documentation: {doc_path.name}")
    print(f"   Test IDs Found: {len(doc_ids)}")
    print()

    print(f"📊 Tracking CSV: {csv_path.name}")
    print(f"   Test IDs Found: {len(csv_ids)}")
    print()

    print(f"{'='*60}")
    print(f"CONSISTENCY ANALYSIS")
    print(f"{'='*60}\n")

    print(f"✅ Matching IDs:     {len(matching)}")
    print(f"⚠️  CSV-only IDs:     {len(csv_only)} (in CSV but not in docs)")
    print(f"⚠️  Doc-only IDs:     {len(doc_only)} (in docs but not in CSV)")
    print(f"\n📊 Consistency Rate: {consistency_rate:.1f}%\n")

    if consistency_rate >= 95:
        print(f"✅ EXCELLENT - Docs and CSV are well synchronized!\n")
        return True
    elif consistency_rate >= 80:
        print(f"⚠️  GOOD - Minor sync issues detected\n")
    elif consistency_rate >= 50:
        print(f"⚠️  WARNING - Significant sync issues detected\n")
    else:
        print(f"❌ CRITICAL - Major sync issues! CSV and docs are out of sync.\n")

    # Show details
    if csv_only:
        print(f"CSV IDs not in documentation (first 10):")
        for test_id in sorted(csv_only)[:10]:
            print(f"   - {test_id}")
        if len(csv_only) > 10:
            print(f"   ... and {len(csv_only) - 10} more")
        print()

    if doc_only:
        print(f"Doc IDs not in CSV (first 10):")
        for test_id in sorted(doc_only)[:10]:
            print(f"   - {test_id}")
        if len(doc_only) > 10:
            print(f"   ... and {len(doc_only) - 10} more")
        print()

    # Recommendations
    print(f"{'='*60}")
    print(f"RECOMMENDATIONS")
    print(f"{'='*60}\n")

    if csv_only or doc_only:
        print("⚠️  Action Required:")
        if csv_only:
            print("   1. Update documentation to include missing test cases")
            print("   OR remove invalid CSV rows")
        if doc_only:
            print("   2. Add missing test cases to tracking CSV")
            print("   OR remove from documentation if not needed")
        print("\n   3. Re-run validation after fixes")
        print("   4. See ground_truth_principle.md for guidance")
    else:
        print("✅ No action required - perfect sync!")

    print()
    return consistency_rate >= 95

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python validate_test_ids.py <doc-path> <csv-path>")
        print("\nExample:")
        print("  python validate_test_ids.py tests/docs/02-CLI-TEST-CASES.md tests/docs/templates/TEST-EXECUTION-TRACKING.csv")
        sys.exit(1)

    doc_path = Path(sys.argv[1])
    csv_path = Path(sys.argv[2])

    if not doc_path.exists():
        print(f"❌ Error: Documentation file not found: {doc_path}")
        sys.exit(1)

    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        sys.exit(1)

    valid = validate_sync(doc_path, csv_path)
    sys.exit(0 if valid else 1)
