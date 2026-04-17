import os
import sys

# Add paths
sys.path.insert(0, '/app/shared/python/node_core')
sys.path.insert(0, '/app/api')

from celery import Celery

# Import from API tasks
from api.tasks import celery_app

if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=INFO"])