# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AcademyEvent(models.Model):
    _name = 'academy.event'
    _description = 'Evento Institucional'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'event.reminder.mixin', 'event.color.mixin']
    _order = 'start_date, id desc'

    # Campos base
    name = fields.Char(
        string='Nombre del Evento',
        required=True,
        tracking=True
    )
    reference = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        default='Nuevo'
    )
    event_type = fields.Selection([
        ('exam', 'Examen'),
        ('activity', 'Actividad Extracurricular'),
        ('meeting', 'Reunión'),
        ('academic', 'Evento Académico'),
        ('administrative', 'Evento Administrativo')
    ], string='Tipo de Evento', required=True, tracking=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Importante'),
        ('2', 'Urgente')
    ], string='Prioridad', default='0', tracking=True)

    description = fields.Html(
        string='Descripción',
        sanitize=True,
        sanitize_tags=True
    )

    # Campos de fecha y tiempo
    start_date = fields.Datetime(
        string='Fecha de Inicio',
        required=True,
        tracking=True
    )
    end_date = fields.Datetime(
        string='Fecha de Fin',
        required=True,
        tracking=True
    )
    duration = fields.Float(
        string='Duración (Horas)',
        compute='_compute_duration',
        store=True
    )
    all_day = fields.Boolean(
        string='Todo el Día',
        default=False
    )

    # Campos de ubicación
    location = fields.Char(string='Ubicación')
    virtual_location = fields.Char(string='Ubicación Virtual')
    is_virtual = fields.Boolean(string='Es Virtual', default=False)

    # Campos de participantes
    course_ids = fields.Many2many(
        'academy.course',
        string='Cursos Involucrados'
    )
    level_ids = fields.Many2many(
        'academy.level',
        string='Niveles'
    )
    teacher_ids = fields.Many2many(
        'academy.teacher',
        string='Profesores'
    )
    student_ids = fields.Many2many(
        'academy.student',
        string='Estudiantes'
    )
    parent_ids = fields.Many2many(
        'academy.parent',
        string='Representantes'
    )

    # Campos de responsabilidad y estado
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En Proceso'),
        ('done', 'Realizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    # Campos de recordatorios y notificaciones
    reminder_ids = fields.One2many(
        'academy.event.reminder',
        'event_id',
        string='Recordatorios'
    )
    has_reminders = fields.Boolean(
        compute='_compute_has_reminders',
        store=True,
        string='Tiene Recordatorios'
    )
    next_reminder = fields.Datetime(
        compute='_compute_next_reminder',
        string='Próximo Recordatorio'
    )

    # Campos de visualización y UI
    color = fields.Integer(string='Color en Calendario')
    active = fields.Boolean(default=True)
    custom_color = fields.Char(
        string='Color Personalizado',
        help='Color en formato hexadecimal (#RRGGBB)'
    )
    display_color = fields.Char(
        compute='_compute_display_color',
        string='Color de Visualización'
    )

    # Campos estadísticos
    participant_count = fields.Integer(
        compute='_compute_participant_stats',
        store=True,
        string='Total Participantes'
    )
    attendance_rate = fields.Float(
        compute='_compute_participant_stats',
        store=True,
        string='Tasa de Asistencia'
    )
    confirmation_rate = fields.Float(
        compute='_compute_participant_stats',
        store=True,
        string='Tasa de Confirmación'
    )

    # Constraints SQL
    _sql_constraints = [
        ('check_dates',
         'CHECK(end_date > start_date)',
         'La fecha de fin debe ser posterior a la fecha de inicio.')
    ]

    # Métodos CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nuevo') == 'Nuevo':
                vals['reference'] = self.env['ir.sequence'].next_by_code('academy.event')
        return super().create(vals_list)

    # Métodos computados
    @api.depends('start_date', 'end_date', 'all_day')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.all_day:
                    record.duration = 24
                else:
                    duration = fields.Datetime.from_string(record.end_date) - \
                               fields.Datetime.from_string(record.start_date)
                    record.duration = duration.total_seconds() / 3600
            else:
                record.duration = 0

    @api.depends('reminder_ids')
    def _compute_has_reminders(self):
        for record in self:
            record.has_reminders = bool(record.reminder_ids)

    @api.depends('reminder_ids.trigger_time', 'reminder_ids.state')
    def _compute_next_reminder(self):
        now = fields.Datetime.now()
        for record in self:
            pending_reminders = record.reminder_ids.filtered(
                lambda r: r.state == 'pending' and r.trigger_time > now
            )
            record.next_reminder = min(pending_reminders.mapped('trigger_time')) if pending_reminders else False

    @api.depends('event_type', 'priority', 'state', 'custom_color')
    def _compute_display_color(self):
        for record in self:
            record.display_color = record.calculate_display_color(
                record.event_type,
                record.priority,
                record.state,
                record.custom_color
            )

    @api.depends('teacher_ids', 'student_ids', 'parent_ids')
    def _compute_participant_stats(self):
        for record in self:
            total_participants = len(record.teacher_ids) + len(record.student_ids) + len(record.parent_ids)
            record.participant_count = total_participants

            # Calcular tasa de asistencia y confirmación
            if total_participants > 0:
                confirmed_participants = len(record.teacher_ids.filtered('present')) + \
                                         len(record.student_ids.filtered('present')) + \
                                         len(record.parent_ids.filtered('present'))
                record.attendance_rate = (confirmed_participants / total_participants) * 100

                confirmed_attendance = len(record.teacher_ids.filtered('confirmed')) + \
                                       len(record.student_ids.filtered('confirmed')) + \
                                       len(record.parent_ids.filtered('confirmed'))
                record.confirmation_rate = (confirmed_attendance / total_participants) * 100
            else:
                record.attendance_rate = 0.0
                record.confirmation_rate = 0.0

    # Métodos de acción
    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self._create_notifications()
        return True

    def action_start(self):
        self.write({'state': 'in_progress'})
        return True

    def action_mark_done(self):
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self.reminder_ids.action_cancel()
        return True

    def action_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_schedule_reminder(self, reminder_type, interval, notification_type='both'):
        """Programa un nuevo recordatorio para el evento"""
        self.ensure_one()
        return self.schedule_reminder(reminder_type, interval, notification_type)

    def action_send_invitation(self):
        """Envía invitaciones a todos los participantes"""
        self.ensure_one()
        template = self.env.ref('calendar_academy.event_invitation_template')
        for partner in self.get_reminder_recipients():
            template.send_mail(
                self.id,
                force_send=True,
                email_values={'email_to': partner.email}
            )
        return True

    # Métodos privados
    def _create_notifications(self):
        """Crea notificaciones para los participantes del evento"""
        partners = self.get_reminder_recipients()
        if partners:
            self.message_subscribe(partner_ids=partners.ids)
            self.message_post(
                body=_(f'Nuevo evento confirmado: {self.name}'),
                partner_ids=partners.ids,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )

    def _get_calendar_view_colors(self):
        """Obtiene los colores para la vista de calendario"""
        self.ensure_one()
        return self.get_calendar_frontend_colors(
            self.event_type,
            self.priority,
            self.state
        )