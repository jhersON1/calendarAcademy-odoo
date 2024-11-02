from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AcademyEvent(models.Model):
    _name = 'academy.event'
    _description = 'Evento Institucional'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date, id desc'

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

    # Fechas y duración
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

    # Ubicación
    location = fields.Char(string='Ubicación')
    virtual_location = fields.Char(string='Ubicación Virtual')
    is_virtual = fields.Boolean(string='Es Virtual', default=False)

    # Participantes
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

    # Responsable y estado
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

    # Campos para integración con calendario
    color = fields.Integer(string='Color en Calendario')
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nuevo') == 'Nuevo':
                vals['reference'] = self.env['ir.sequence'].next_by_code('academy.event')
        return super().create(vals_list)

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

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('La fecha de fin no puede ser anterior a la fecha de inicio'))

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self._create_notifications()

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_mark_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _create_notifications(self):
        """Crea notificaciones para los participantes del evento"""
        partners = self.env['res.partner']

        # Recolectar todos los participantes
        if self.student_ids:
            partners |= self.student_ids.mapped('user_id.partner_id')
        if self.teacher_ids:
            partners |= self.teacher_ids.mapped('user_id.partner_id')
        if self.parent_ids:
            partners |= self.parent_ids.mapped('user_id.partner_id')

        # Crear notificación
        if partners:
            self.message_subscribe(partner_ids=partners.ids)
            self.message_post(
                body=_(f'Nuevo evento programado: {self.name}'),
                partner_ids=partners.ids,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )