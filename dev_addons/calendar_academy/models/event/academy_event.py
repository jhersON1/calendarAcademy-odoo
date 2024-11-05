from odoo import models, fields, api, _
from datetime import datetime, timedelta


class AcademyEvent(models.Model):
    _name = 'academy.event'
    _description = 'Academic Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True
    )

    event_type = fields.Selection([
        ('academic', 'Académico'),
        ('administrative', 'Administrativo'),
        ('extracurricular', 'Extracurricular')
    ], string='Tipo de Evento',
       required=True,
       default='academic',
       tracking=True)

    start_date = fields.Datetime(
        string='Fecha Inicio',
        required=True,
        tracking=True
    )

    end_date = fields.Datetime(
        string='Fecha Fin',
        required=True,
        tracking=True
    )

    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )

    is_virtual = fields.Boolean(
        string='Es Virtual',
        tracking=True
    )

    location = fields.Char(
        string='Ubicación',
        tracking=True
    )

    virtual_url = fields.Char(
        string='Link de Reunión',
        tracking=True
    )

    description = fields.Html(
        string='Descripción',
        sanitize=True
    )

    # Participantes
    course_ids = fields.Many2many(
        'academy.course',
        string='Cursos'
    )

    teacher_ids = fields.Many2many(
        'academy.teacher',
        string='Profesores'
    )

    student_ids = fields.Many2many(
        'academy.student',
        string='Estudiantes'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Realizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado',
       default='draft',
       tracking=True)

    # Computed fields
    color = fields.Integer(
        string='Color',
        compute='_compute_color',
        store=True
    )

    @api.depends('event_type')
    def _compute_color(self):
        for record in self:
            colors = {
                'academic': 1,      # Azul
                'administrative': 2, # Verde
                'extracurricular': 4 # Rojo
            }
            record.color = colors.get(record.event_type, 0)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValueError(
                        _('La fecha de fin no puede ser anterior a la fecha de inicio'))

    # Simple workflow
    def action_confirm(self):
        """Confirmar evento"""
        self.write({'state': 'confirmed'})

    def action_mark_done(self):
        """Marcar evento como realizado"""
        self.write({'state': 'done'})

    def action_cancel(self):
        """Cancelar evento"""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})