#!/usr/bin/env python3
"""Quick script to find and remove orphaned document records."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "documents.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Find all documents needing review
cursor.execute('''
    SELECT id, original_filename, current_path, status 
    FROM documents 
    WHERE status IN ('needs_review', 'processed')
''')

orphans = []
for row in cursor.fetchall():
    doc_id, filename, current_path, status = row
    if current_path and not Path(current_path).exists():
        orphans.append((doc_id, filename, current_path, status))
        print(f"Orphan found: ID={doc_id}, {filename}")
        print(f"  Path: {current_path}")
        print(f"  Status: {status}")

if orphans:
    print(f"\nFound {len(orphans)} orphaned record(s)")
    print("Deleting orphaned records...")
    for doc_id, filename, _, _ in orphans:
        cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        cursor.execute('DELETE FROM activity_log WHERE document_id = ?', (doc_id,))
        print(f"  Deleted: {filename}")
    conn.commit()
    print(f"\nDone! Deleted {len(orphans)} orphaned records.")
else:
    print("No orphaned records found.")

conn.close()

