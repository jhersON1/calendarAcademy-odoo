# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AcademyEventReminder(models.Model):
    _name = 'academy.event.reminder'
    _description = 'Recordatorio de Evento'
    _inherit = ['event.reminder.mixin']
    _order = 'trigger_time'
    _rec_name = 'display_name'

    event_id = fields.Many2one(
        'academy.event',
        string='Evento',
        required=True,
        ondelete='cascade',
        index=True
    )
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )
    reminder_type = fields.Selection(
        selection='_get_reminder_types',
        string='Tipo de Recordatorio',
        required=True
    )
    interval = fields.Integer(
        string='Intervalo',
        required=True
    )
    trigger_time = fields.Datetime(
        string='Hora de Activación',
        compute='_compute_trigger_time',
        store=True,
        index=True
    )
    notification_type = fields.Selection([
        ('email', 'Correo Electrónico'),
        ('system', 'Notificación del Sistema'),
        ('both', 'Ambos')
    ], string='Tipo de Notificación',
        required=True,
        default='both'
    )
    recipient_ids = fields.Many2many(
        'res.partner',
        'event_reminder_recipient_rel',
        'reminder_id',
        'partner_id',
        string='Destinatarios Específicos'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado')
    ], string='Estado',
        default='draft',
        required=True,
        tracking=True
    )
    last_execution = fields.Datetime(
        string='Última Ejecución',
        readonly=True
    )
    execution_log = fields.Text(
        string='Registro de Ejecución',
        readonly=True
    )
    retry_count = fields.Integer(
        string='Intentos de Reenvío',
        default=0
    )
    active = fields.Boolean(
        default=True
    )

    _sql_constraints = [
        ('unique_reminder_per_type',
         'UNIQUE(event_id, reminder_type, interval)',
         'Ya existe un recordatorio con este intervalo para este evento')
    ]

    @api.depends('event_id.name', 'reminder_type', 'interval')
    def _compute_display_name(self):
        for record in self:
            if record.event_id and record.reminder_type and record.interval:
                record.display_name = _(
                    'Recordatorio: %(event)s - %(interval)s %(type)s antes'
                ) % {
                                          'event': record.event_id.name,
                                          'interval': record.interval,
                                          'type': dict(self._fields['reminder_type'].selection).get(
                                              record.reminder_type)
                                      }
            else:
                record.display_name = _('Nuevo Recordatorio')

    @api.depends('event_id.start_date', 'reminder_type', 'interval')
    def _compute_trigger_time(self):
        for record in self:
            if record.event_id.start_date and record.reminder_type and record.interval:
                record.trigger_time = record._calculate_trigger_time(
                    record.reminder_type,
                    record.interval
                )
            else:
                record.trigger_time = False

    @api.constrains('interval', 'reminder_type')
    def _check_interval(self):
        for record in self:
            valid_intervals = self._get_default_intervals().get(record.reminder_type, [])
            if record.interval not in valid_intervals:
                raise ValidationError(_(
                    'El intervalo %s no es válido para el tipo de recordatorio %s'
                ) % (record.interval, record.reminder_type))

    @api.constrains('trigger_time')
    def _check_trigger_time(self):
        now = fields.Datetime.now()
        for record in self:
            if record.trigger_time and record.trigger_time < now and record.state == 'draft':
                raise ValidationError(_(
                    'No se puede programar un recordatorio para una fecha pasada'
                ))

    def action_confirm(self):
        """Confirma y activa el recordatorio"""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_('Solo los recordatorios en borrador pueden ser confirmados'))

        self.write({
            'state': 'pending',
            'execution_log': f"{fields.Datetime.now()}: Recordatorio confirmado\n"
        })

    def action_cancel(self):
        """Cancela el recordatorio"""
        self.write({
            'state': 'cancelled',
            'execution_log': f"{fields.Datetime.now()}: Recordatorio cancelado\n" +
                             (self.execution_log or '')
        })

    def action_reset_to_draft(self):
        """Devuelve el recordatorio a estado borrador"""
        self.write({
            'state': 'draft',
            'retry_count': 0,
            'execution_log': f"{fields.Datetime.now()}: Recordatorio reiniciado\n" +
                             (self.execution_log or '')
        })

    def execute_reminder(self):
        """Ejecuta el recordatorio"""
        self.ensure_one()
        if self.state != 'pending':
            return False

        try:
            # Enviar notificaciones
            if self.notification_type in ['email', 'both']:
                self._send_email_notification()

            if self.notification_type in ['system', 'both']:
                self._send_system_notification()

            self.write({
                'state': 'sent',
                'last_execution': fields.Datetime.now(),
                'execution_log': f"{fields.Datetime.now()}: Recordatorio enviado exitosamente\n" +
                                 (self.execution_log or '')
            })
            return True

        except Exception as e:
            self.write({
                'state': 'failed',
                'retry_count': self.retry_count + 1,
                'execution_log': f"{fields.Datetime.now()}: Error al enviar recordatorio - {str(e)}\n" +
                                 (self.execution_log or '')
            })
            return False

    def _send_email_notification(self):
        """Envía la notificación por correo electrónico"""
        self.ensure_one()
        template = self.env.ref(
            f'calendar_academy.reminder_template_{self.event_id.event_type}',
            raise_if_not_found=False
        )
        if not template:
            template = self.env.ref('calendar_academy.reminder_template_base')

        recipients = self.recipient_ids or self.event_id.get_reminder_recipients()
        if not recipients:
            raise ValidationError(_('No hay destinatarios definidos para el recordatorio'))

        for recipient in recipients:
            template.with_context(recipient_name=recipient.name).send_mail(
                self.event_id.id,
                force_send=True,
                email_values={'email_to': recipient.email}
            )

    def _send_system_notification(self):
        """Envía la notificación del sistema"""
        self.ensure_one()
        recipients = self.recipient_ids or self.event_id.get_reminder_recipients()
        if not recipients:
            raise ValidationError(_('No hay destinatarios definidos para el recordatorio'))

        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recordatorio de Evento'),
                'message': self.event_id._get_reminder_message(self),
                'type': 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }

        self.env['bus.bus']._sendmany([
            [partner, 'calendar_reminder', notification]
            for partner in recipients
        ])

    def retry_failed_reminder(self):
        """Reintenta el envío de un recordatorio fallido"""
        self.ensure_one()
        if self.state != 'failed':
            raise ValidationError(_('Solo se pueden reintentar recordatorios fallidos'))

        if self.retry_count >= 3:
            raise ValidationError(_('Se ha excedido el número máximo de intentos'))

        self.write({'state': 'pending'})
        return self.execute_reminder()