"""
WSGI config for lab_system_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lab_system_backend.settings')

application = get_wsgi_application()

from task_tools.task_refresh_calibration_state import init_refresh_task
from task_tools.task_remind_return import init_remind_return
from task_tools.task_refresh_currency_rate import init_refresh_currency


def init_uniq():
    """
    只初始化一次的任务
    """
    init_refresh_task()
    init_remind_return()
    init_refresh_currency()

init_uniq()
