import os
from celery import Celery
from celery.schedules import crontab


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_system.settings')

app = Celery('library_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-overdue-book-loans-daily': {
        'task': 'library.tasks.check_overdue_loans',
        'schedule': crontab(hour=9, minute=0)
    }
}
