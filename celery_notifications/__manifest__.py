# Copyright Otrium (http://www.otrium.nl)
{
    'name': 'Celery Task Notifications',
    'summary': 'Web/E-mail notifications for celery tasks',
    'category': 'General',
    'version': '12.0.1.0.0',
    'author': 'Otrium B.V.',
    'website': 'https://www.otrium.com',
    'license': "LGPL-3",
    'depends': [
        'celery',
        'web_notify_action'
    ],
    'data': [
        'data/email_template_data.xml',
        'data/ir_cron_data.xml',
        'views/celery_task_settings_views.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'description': """
Celery Notifications
====================

Features
--------

* Adds web and e-mail notifications triggered when a task fails, succeeds or gets jammed.
"""
}
