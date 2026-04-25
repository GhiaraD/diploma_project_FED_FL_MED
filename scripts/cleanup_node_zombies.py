#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta

db_path = "/storage/node.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find zombie jobs (older than 1 hour)
cutoff = datetime.now() - timedelta(hours=1)
cutoff_str = cutoff.isoformat()

cursor.execute("""
    SELECT job_id, job_type, started_at
    FROM jobs
    WHERE status = 'running'
    AND started_at < ?
""", (cutoff_str,))

zombie_jobs = cursor.fetchall()
print(f"Found {len(zombie_jobs)} zombie jobs")

if zombie_jobs:
    for job_id, job_type, started_at in zombie_jobs:
        print(f"  - {job_id} ({job_type}) started at {started_at}")
    
    # Update them
    cursor.execute("""
        UPDATE jobs
        SET status = 'failed',
            error = 'Job marked as failed due to timeout (zombie cleanup)',
            completed_at = ?
        WHERE status = 'running'
        AND started_at < ?
    """, (datetime.now().isoformat(), cutoff_str))
    
    conn.commit()
    print(f"✓ Marked {cursor.rowcount} jobs as failed")
else:
    print("✓ No zombie jobs found")

conn.close()
