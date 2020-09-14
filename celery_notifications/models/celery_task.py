# Copyright Otrium (http://www.otrium.nl)

from odoo import api, fields, models, _
from odoo.addons.celery.models.celery_task import STATE_JAMMED, STATE_FAILURE, STATE_SUCCESS
import logging
_logger = logging.getLogger(__name__)


class CeleryTask(models.Model):
    _inherit = 'celery.task'

    sent_with_mail_digest = fields.Boolean(string="Sent with mail digest", default=False)

    def get_task_url(self):
        """
        Methods:
         * _get_signup_url_for_action from res.partner
        """
        self.ensure_one()
        url = self.env.user.partner_id.sudo().with_context(
            signup_valid=True,
        )._get_signup_url_for_action(
            view_type="form",
            model=self._name,
            res_id=self.id,
            action='celery.action_celery_task',
        )[self.env.user.partner_id.id]
        url = url.replace('res_id', 'id')
        return url

    def write(self, vals):
        res = super(CeleryTask, self).write(vals)
        if 'state' in vals:
            mail_server = self.env['ir.mail_server']
            for task in self:
                if task.state in [STATE_JAMMED, STATE_FAILURE, STATE_SUCCESS]:
                    notify_settings = self.env['celery.task.setting'].search([('model', '=', task.model), ('method', '=', task.method)])
                    notification = {
                        'title': 'Celery Task',
                        'message': '{model}:{method}, record: {ref}'.format(model=task.model, method=task.method, ref=task.ref),
                        'type': 'warning',
                        'animate': True,
                        'icon': 'fa-cog',
                        'image_url': '/celery_notifications/static/src/img/celery.png',
                        'timeout': 5000,
                        'buttons': [{
                                'tag': 'open',
                                'action': 'celery.action_celery_task',
                                'text': 'View Tasks',
                                'icon': 'fa-cog'}],
                    }
                    if task.state == STATE_JAMMED and notify_settings and notify_settings.jammed_notify_users_ids:
                        try:
                            notification.update(title='Celery Jammed Task', timeout=notify_settings.jammed_notification_duration * 1000)
                            notify_settings.jammed_notify_users_ids._notify_action(notification)
                            # email
                            if notify_settings.jammed_send_email_notification and notify_settings.jammed_send_email_template:
                                template = notify_settings.jammed_send_email_template
                                for user in notify_settings.jammed_notify_users_ids:
                                    body_html = template._render_template(template.body_html, 'celery.task', task and task.id)
                                    message = mail_server.build_email(
                                        email_from=self.sudo().env.user.email,
                                        subject=_(u'Jammed Celery Task'),
                                        body=body_html,
                                        subtype='html',
                                        email_to=[user.partner_id.email],
                                    )
                                    mail_server.send_email(message)
                        except Exception as e:
                            _logger.warning('Celery Notification Error: %s' % (str(e), ))
                    if task.state == STATE_FAILURE and notify_settings and notify_settings.failed_notify_users_ids:
                        try:
                            notification.update(title='Celery Failed Task', icon='fa fa-3x fa-times', timeout=notify_settings.failed_notification_duration * 1000)
                            notify_settings.failed_notify_users_ids._notify_action(notification)
                            # email
                            if notify_settings.failed_send_email_notification and notify_settings.failed_send_email_template:
                                template = notify_settings.failed_send_email_template
                                for user in notify_settings.failed_notify_users_ids:
                                    body_html = template._render_template(template.body_html, 'celery.task', task and task.id)
                                    mail_server = self.env['ir.mail_server']
                                    message = mail_server.build_email(
                                        email_from=self.sudo().env.user.email,
                                        subject=_(u'Failed Celery Task'),
                                        body=body_html,
                                        subtype='html',
                                        email_to=[user.partner_id.email],
                                    )
                                    mail_server.send_email(message)
                        except Exception as e:
                            _logger.warning('Celery Task Notification Error: %s' % (str(e), ))
                    if task.state == STATE_SUCCESS and notify_settings and notify_settings.success_notify_users_ids:
                        try:
                            notification.update(title='Celery Successful Task', type='notification', icon='fa fa-3x fa-check', timeout=notify_settings.success_notification_duration * 1000)
                            notify_settings.success_notify_users_ids._notify_action(notification)
                            # email
                            if notify_settings.success_send_email_notification and notify_settings.success_send_email_template:
                                template = notify_settings.success_send_email_template
                                for user in notify_settings.success_notify_users_ids:
                                    body_html = template._render_template(template.body_html, 'celery.task', task and task.id)
                                    mail_server = self.env['ir.mail_server']
                                    message = mail_server.build_email(
                                        email_from=self.sudo().env.user.email,
                                        subject=_(u'Successful Celery Task'),
                                        body=body_html,
                                        subtype='html',
                                        email_to=[user.partner_id.email],
                                    )
                                    mail_server.send_email(message)
                        except Exception as e:
                            _logger.warning('Celery Task Notification Error: %s' % (str(e), ))
        return res

    @api.model
    def cron_notifications_digest(self, celery_task_setting_id=False):
        if celery_task_setting_id:
            setting = self.env['celery.task.setting'].browse(celery_task_setting_id)
            if setting and setting.send_task_digest_email and setting.message_follower_ids:
                order_by_field = 'state_date'
                jammed_tasks = self.search([('state', '=', STATE_JAMMED), ('model', '=', setting.model), ('method', '=', setting.method), ('sent_with_mail_digest', '=', False)], order=order_by_field)
                failed_tasks = self.search([('state', '=', STATE_FAILURE), ('model', '=', setting.model), ('method', '=', setting.method), ('sent_with_mail_digest', '=', False)], order=order_by_field)

                if jammed_tasks or failed_tasks:
                    template = self.env.ref('celery_notifications.celery_task_digest_template', raise_if_not_found=False)
                    if template:
                        body_html = template.with_context(jammed_tasks=jammed_tasks, failed_tasks=failed_tasks)._render_template(template.body_html, 'celery.task.setting', setting.id)
                        mail_server = self.env['ir.mail_server']
                        message = mail_server.with_context(jammed_tasks=jammed_tasks, failed_tasks=failed_tasks).build_email(
                            email_from=self.sudo().env.user.email,
                            subject=_(u'Celery Tasks Digest'),
                            body=body_html,
                            subtype='html',
                            email_to=[follower.partner_id.email for follower in setting.message_follower_ids],
                        )
                        mail_server.send_email(message)
                        jammed_tasks.write({'sent_with_mail_digest': True})
                        failed_tasks.write({'sent_with_mail_digest': True})
