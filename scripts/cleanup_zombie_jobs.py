#!/usr/bin/env python3
"""
Cleanup zombie jobs that are stuck in 'running' state.
"""
import sys
import sqlite3
from datetime import datetime, timedelta

def cleanup_zombie_jobs(db_path, max_age_hours=1):
    """
    Mark old running jobs as failed.
    
    Args:
        db_path: Path to SQLite database
        max_age_hours: Jobs older than this are considered zombie
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Calculate cutoff time
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    cutoff_str = cutoff.isoformat()
    
    # Find zombie jobs
    cursor.execute("""
        SELECT job_id, job_type, created_at, started_at
        FROM jobs
        WHERE status = 'running'
        AND started_at < ?
    """, (cutoff_str,))
    
    zombie_jobs = cursor.fetchall()
    
    if not zombie_jobs:
        print("✓ No zombie jobs found")
        conn.close()
        return 0
    
    print(f"Found {len(zombie_jobs)} zombie job(s):")
    for job_id, job_type, created_at, started_at in zombie_jobs:
        print(f"  - {job_id} ({job_type})")
        print(f"    Started: {started_at}")
    
    print()
    
    # Update zombie jobs
    cursor.execute("""
        UPDATE jobs
        SET status = 'failed',
            error = 'Job marked as failed due to timeout (zombie cleanup)',
            completed_at = ?
        WHERE status = 'running'
        AND started_at < ?
    """, (datetime.now().isoformat(), cutoff_str))
    
    conn.commit()
    updated = cursor.rowcount
    
    print(f"✓ Marked {updated} job(s) as failed")
    
    conn.close()
    return updated


if __name__ == "__main__":
    # Cleanup for all nodes
    nodes = ["node1", "node2", "node3"]
    
    total_cleaned = 0
    
    for node in nodes:
        db_path = f"storage/{node}/node.db"
        print(f"\n{'='*50}")
        print(f"Cleaning up {node}...")
        print('='*50)
        
        try:
            cleaned = cleanup_zombie_jobs(db_path, max_age_hours=1)
            total_cleaned += cleaned
        except Exception as e:
            print(f"✗ Error cleaning {node}: {e}")
    
    print(f"\n{'='*50}")
    print(f"Total zombie jobs cleaned: {total_cleaned}")
    print('='*50)
