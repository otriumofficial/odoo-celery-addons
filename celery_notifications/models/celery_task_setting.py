# Copyright Otrium (http://www.otrium.nl)

from odoo import api, fields, models, _
from odoo import SUPERUSER_ID
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

_intervalTypes = {
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(days=7 * interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}


class CeleryTaskSetting(models.Model):
    _inherit = 'celery.task.setting'

    def _default_user_ids(self):
        return [(6, 0, [self._uid])]

    def _default_email_template(self):
        template = self.env.ref('celery_notifications.celery_task_template', raise_if_not_found=False)
        if template:
            return template.id

    jammed_notify_users_ids = fields.Many2many(
        string="Notify users (jammed)",
        comodel_name="res.users",
        relation="celery_task_setting_res_users_jammed_rel",
        column1="task_id",
        column2="user_id",
        default=_default_user_ids,
        help="Users to receive a Web/E-mail notification when these tasks are jammed.",
        track_visibility='onchange',
    )
    jammed_send_email_notification = fields.Boolean(string="Send Instant E-mail notification (jammed)", default=False)
    jammed_send_email_template = fields.Many2one('mail.template', string="Mail template (jammed)",
                                                 help="Use this mail template for jammed task e-mails.", default=_default_email_template)
    jammed_are_you_inside = fields.Boolean(string='Are you inside the matrix? (jammed)',
                                           compute='_are_you_inside', store=False, readonly=True)
    jammed_notification_duration = fields.Integer(string="Notification Duration for Jammed Tasks (seconds)", default=5)

    failed_notify_users_ids = fields.Many2many(
        string="Notify users (failed)",
        comodel_name="res.users",
        relation="celery_task_setting_res_users_failed_rel",
        column1="task_id",
        column2="user_id",
        default=_default_user_ids,
        help="Users to receive a Web/E-mail notification when these tasks fail.",
    )
    failed_send_email_notification = fields.Boolean(string="Send Instant E-mail notification (failed)", default=False)
    failed_send_email_template = fields.Many2one('mail.template', string="Mail template (failed)",
                                                 help="Use this mail template for failed task e-mails.", default=_default_email_template)
    failed_are_you_inside = fields.Boolean(string='Are you inside the matrix? (failed)',
                                           compute='_are_you_inside', store=False, readonly=True)
    failed_notification_duration = fields.Integer(string="Notification Duration for Failed Tasks (seconds)", default=5)

    success_notify_users_ids = fields.Many2many(
        string="Notify users (successful)",
        comodel_name="res.users",
        relation="celery_task_setting_res_users_success_rel",
        column1="task_id",
        column2="user_id",
        help="Users to receive a Web/E-mail notification when these tasks are successful.",
    )
    success_send_email_notification = fields.Boolean(string="Send Instant E-mail notification (successful)", default=False)
    success_send_email_template = fields.Many2one('mail.template', string="Mail template (successful)",
                                                  help="Use this mail template for successful task e-mails.", default=_default_email_template)
    success_are_you_inside = fields.Boolean(string='Are you inside the matrix? (successful)',
                                            compute='_are_you_inside', store=False, readonly=True)
    success_notification_duration = fields.Integer(string="Notification Duration for Successful Tasks (seconds)", default=5)

    send_task_digest_email = fields.Boolean(string="Send a Digest E-mail To Followers Every: ", track_visibility='onchange')
    send_task_digest_email_interval = fields.Integer(string="E-mail Digest interval number", default=1, required=True, track_visibility='onchange')
    send_task_digest_email_interval_type = fields.Selection([
        ('weeks', 'Weeks'),
        ('days', 'Days'),
        ('hours', 'Hours'),
        ('minutes', 'Minutes'),
    ], string='E-mail Digest interval type', default='hours', required=True, track_visibility='onchange')

    @api.one
    def _are_you_inside(self):
        self.jammed_are_you_inside = bool(self.env.uid in [u.id for u in self.jammed_notify_users_ids])
        self.failed_are_you_inside = bool(self.env.uid in [u.id for u in self.failed_notify_users_ids])
        self.success_are_you_inside = bool(self.env.uid in [u.id for u in self.success_notify_users_ids])

    @api.multi
    def action_join(self):
        self.ensure_one()
        state_change = self.env.context.get('state_change', False)
        if state_change and state_change == 'jammed':
            return self.write({'jammed_notify_users_ids': [(4, self._uid)]})
        elif state_change and state_change == 'failed':
            return self.write({'failed_notify_users_ids': [(4, self._uid)]})
        elif state_change and state_change == 'success':
            return self.write({'success_notify_users_ids': [(4, self._uid)]})

    @api.multi
    def action_quit(self):
        self.ensure_one()
        state_change = self.env.context.get('state_change', False)
        if state_change and state_change == 'jammed':
            return self.write({'jammed_notify_users_ids': [(3, self._uid)]})
        elif state_change and state_change == 'failed':
            return self.write({'failed_notify_users_ids': [(3, self._uid)]})
        elif state_change and state_change == 'success':
            return self.write({'success_notify_users_ids': [(3, self._uid)]})

    @api.multi
    def write(self, vals):
        res = super(CeleryTaskSetting, self).write(vals)
        # set cron interval value for the digest email
        self.set_email_digest_cron_interval()

    @api.multi
    def unlink(self):
        for setting in self:
            try:
                cron = self.env.ref('celery_notifications.ir_cron_celery_notifications_digest_%d' % (setting.id), raise_if_not_found=False)
            except Exception as e:
                cron = False
                _logger.warning('Celery Cron Digest Configuration Error: %s' % (str(e), ))
            if cron:
                cron.unlink()
        return super(CeleryTaskSetting, self).unlink()

    @api.model
    def set_email_digest_cron_interval(self):
        for setting in self:
            if setting.send_task_digest_email and setting.send_task_digest_email_interval and setting.send_task_digest_email_interval_type:
                try:
                    cron = self.env.ref('celery_notifications.ir_cron_celery_notifications_digest_%d' % (setting.id), raise_if_not_found=False)
                except Exception as e:
                    cron = False
                    _logger.warning('Celery Cron Digest Configuration Error: %s' % (str(e), ))
                if cron:
                    cron.sudo().write({
                        'interval_number': setting.send_task_digest_email_interval,
                        'interval_type': setting.send_task_digest_email_interval_type
                    })
                else:
                    nextcall = datetime.now()
                    nextcall += _intervalTypes[setting.send_task_digest_email_interval_type](setting.send_task_digest_email_interval)
                    vals = {
                        'active': True,
                        'interval_number': setting.send_task_digest_email_interval,
                        'interval_type': setting.send_task_digest_email_interval_type,
                        'nextcall': nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                        'model_id': self.env['ir.model'].sudo().search([('model', '=', 'celery.task')], limit=1).id,
                        'state': 'code',
                        'code': "model.cron_notifications_digest(celery_task_setting_id=%d)" % (setting.id),
                        'user_id': SUPERUSER_ID
                    }
                    name = 'Celery Task E-mail Digest for: ' + setting.model + ' : ' + setting.method
                    vals.update({'name': name})
                    new_cron = self.env['ir.cron'].sudo().create(vals)
                    self.env['ir.model.data'].sudo().create({
                        'module': 'celery_notifications',
                        'name': 'ir_cron_celery_notifications_digest_%d' % (setting.id),
                        'model': 'ir.cron',
                        'res_id': new_cron.id,
                        'noupdate': True
                    })
            else:
                try:
                    cron = self.env.ref('celery_notifications.ir_cron_celery_notifications_digest_%d' % (setting.id), raise_if_not_found=False)
                except Exception as e:
                    cron = False
                    _logger.warning('Celery Cron Digest Configuration Error: %s' % (str(e), ))
                if cron:
                    cron.unlink()

    @api.multi
    def toggle_digest(self):
        for record in self:
            if record.send_task_digest_email:
                record.send_task_digest_email = False
            else:
                record.send_task_digest_email = True
