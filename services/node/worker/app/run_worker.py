import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("node-worker", broker=redis_url, backend=redis_url)

@celery_app.task(name="ping")
def ping():
    return {"ok": True, "node_id": os.getenv("NODE_ID", "unknown")}

if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=INFO"])