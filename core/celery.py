import os
from celery import Celery
from django.conf import settings
from kombu import Queue

# Set default Django settings module for 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load config from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Define dedicated queue for this project
app.conf.task_queues = (
    Queue('auth_vk_queue', routing_key='auth_vk.#'),
)

# Route all tasks from auth_vk app to this queue
app.conf.task_routes = {
    'auth_vk.tasks.*': {'queue': 'auth_vk_queue', 'routing_key': 'auth_vk.tasks'},
}

# Auto-discover tasks only in 'auth_vk' app
app.autodiscover_tasks(['auth_vk'])

# Setup Django before importing any models or tasks
import django
django.setup()
