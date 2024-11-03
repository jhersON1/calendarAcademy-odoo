# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError


class EventReminderMixin(models.AbstractModel):
    _name = 'event.reminder.mixin'
    _description = 'Mixin para recordatorios de eventos'

    def _get_reminder_types(self):
        """Define los tipos de recordatorios disponibles"""
        return [
            ('minutes', 'Minutos'),
            ('hours', 'Horas'),
            ('days', 'Días')
        ]

    def _get_default_intervals(self):
        """Define los intervalos predeterminados para cada tipo"""
        return {
            'minutes': [15, 30, 45, 60],
            'hours': [1, 2, 4, 8, 12, 24],
            'days': [1, 2, 3, 5, 7]
        }

    def _get_notification_templates(self):
        """Define las plantillas de notificación por tipo de evento"""
        return {
            'exam': 'calendar_academy.reminder_template_exam',
            'activity': 'calendar_academy.reminder_template_activity',
            'meeting': 'calendar_academy.reminder_template_meeting',
            'academic': 'calendar_academy.reminder_template_academic',
            'administrative': 'calendar_academy.reminder_template_administrative'
        }

    def schedule_reminder(self, reminder_type, interval, notification_type='both'):
        """
        Programa un nuevo recordatorio
        Args:
            reminder_type: tipo de recordatorio (minutes/hours/days)
            interval: intervalo de tiempo
            notification_type: tipo de notificación (email/system/both)
        """
        self.ensure_one()
        if not self.start_date:
            raise ValidationError(_('El evento debe tener una fecha de inicio para programar recordatorios'))

        # Validar el intervalo
        valid_intervals = self._get_default_intervals().get(reminder_type, [])
        if interval not in valid_intervals:
            raise ValidationError(_('Intervalo no válido para el tipo de recordatorio seleccionado'))

        # Calcular tiempo de activación
        trigger_time = self._calculate_trigger_time(reminder_type, interval)

        # Crear el recordatorio
        vals = {
            'event_id': self.id,
            'reminder_type': reminder_type,
            'interval': interval,
            'notification_type': notification_type,
            'trigger_time': trigger_time,
            'state': 'pending'
        }

        return self.env['academy.event.reminder'].create(vals)

    def _calculate_trigger_time(self, reminder_type, interval):
        """Calcula el momento exacto para activar el recordatorio"""
        if reminder_type == 'minutes':
            delta = timedelta(minutes=interval)
        elif reminder_type == 'hours':
            delta = timedelta(hours=interval)
        else:  # days
            delta = timedelta(days=interval)

        return self.start_date - delta

    def process_pending_reminders(self):
        """Procesa los recordatorios pendientes"""
        now = fields.Datetime.now()
        pending_reminders = self.env['academy.event.reminder'].search([
            ('state', '=', 'pending'),
            ('trigger_time', '<=', now)
        ])

        for reminder in pending_reminders:
            reminder.execute_reminder()

    def get_reminder_recipients(self):
        """Obtiene los destinatarios para las notificaciones"""
        self.ensure_one()
        recipients = self.env['res.partner']

        # Añadir profesores
        if self.teacher_ids:
            recipients |= self.teacher_ids.mapped('user_id.partner_id')

        # Añadir estudiantes
        if self.student_ids:
            recipients |= self.student_ids.mapped('user_id.partner_id')

        # Añadir representantes
        if self.parent_ids:
            recipients |= self.parent_ids.mapped('user_id.partner_id')

        return recipients

    def send_reminder_notification(self, reminder):
        """Envía las notificaciones del recordatorio"""
        self.ensure_one()
        recipients = self.get_reminder_recipients()

        if not recipients:
            return False

        if reminder.notification_type in ['email', 'both']:
            template = self._get_notification_templates().get(self.event_type)
            if template:
                template_id = self.env.ref(template)
                for recipient in recipients:
                    template_id.send_mail(
                        self.id,
                        force_send=True,
                        email_values={'email_to': recipient.email}
                    )

        if reminder.notification_type in ['system', 'both']:
            notification_data = {
                'title': _('Recordatorio: %s') % self.name,
                'message': self._get_reminder_message(reminder),
                'type': 'user_notification',
                'sticky': True,
                'partner_ids': [(6, 0, recipients.ids)]
            }
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'calendar_reminder', notification_data)

        return True

    def _get_reminder_message(self, reminder):
        """Genera el mensaje para el recordatorio"""
        self.ensure_one()
        date_format = self.env['res.lang']._lang_get(self.env.user.lang).date_format
        event_date = fields.Datetime.context_timestamp(self, self.start_date)

        return _("""
            Recordatorio para el evento: %(name)s
            Fecha: %(date)s
            Tipo: %(type)s
            Ubicación: %(location)s
        """) % {
            'name': self.name,
            'date': event_date.strftime(date_format + ' %H:%M'),
            'type': dict(self._fields['event_type'].selection).get(self.event_type),
            'location': self.location or self.virtual_location or _('No especificada')
        }

    def cron_process_reminders(self):
        """Método para ser llamado por el cron job"""
        self.process_pending_reminders()