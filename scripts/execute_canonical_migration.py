import sys
import sqlite3
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from library.storage_manager import migrate_storage_to_canonical

def run_migration():
    db_path = settings.library_db_path
    base_dir = settings.output_dir
    print(f"=== V6 CANONICAL FILESYSTEM MIGRATION ===")
    print(f"Target Directory: {base_dir}")
    print(f"Database Path: {db_path}")

    conn = sqlite3.connect(str(db_path))
    res = migrate_storage_to_canonical(conn, base_dir, dry_run=False)
    conn.close()

    print("\n--- MIGRATION RESULTS ---")
    print(f"Total physical files discovered: {res['total_files_discovered']}")
    print(f"Successfully mapped: {res['successfully_mapped']}")
    print(f"Migrated count: {res['migrated_count']}")
    print(f"Already canonical: {res['already_canonical_count']}")
    print(f"Duplicates detected: {len(res['duplicates_detected'])}")
    print(f"Ambiguous / unmapped: {len(res['ambiguous_unmapped'])}")
    print(f"Temporary artifacts removed: {len(res['temporary_artifacts_removed'])}")
    print(f"Files intentionally untouched: {len(res['files_untouched'])}")
    print(f"Errors encountered: {len(res['errors'])}")

    print("\n--- MIGRATED FILES LOG ---")
    for m in res['migrated']:
        print(f"  MOVED: '{m['from']}' -> '{m['to']}'")

    if res['duplicates_detected']:
        print("\n--- DUPLICATES LOG ---")
        for d in res['duplicates_detected']:
            print(f"  DUPLICATE: '{d['source']}' (Canonical exists at '{d['canonical_target']}')")

    if res['temporary_artifacts_removed']:
        print("\n--- TEMPORARY ARTIFACTS REMOVED ---")
        for t in res['temporary_artifacts_removed']:
            print(f"  REMOVED: '{t}'")

    if res['ambiguous_unmapped']:
        print("\n--- AMBIGUOUS / UNMAPPED FILES ---")
        for u in res['ambiguous_unmapped']:
            print(f"  UNMAPPED: '{u['file']}' - {u['reason']}")

    if res['errors']:
        print("\n--- ERRORS ---")
        for e in res['errors']:
            print(f"  ERROR: {e}")

    # Inspect final directory structure
    print("\n--- FINAL DIRECTORY ROOT INSPECTION ---")
    root_entries = list(Path(base_dir).iterdir())
    for item in sorted(root_entries):
        if item.is_dir():
            child_count = len(list(item.iterdir()))
            print(f"  [DIR]  {item.name}/ ({child_count} children)")
        else:
            print(f"  [FILE] {item.name} ({item.stat().st_size} bytes)")

    # Save detailed JSON report
    report_path = Path(__file__).resolve().parent / "canonical_migration_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nSaved detailed report to: {report_path}")

if __name__ == "__main__":
    run_migration()
