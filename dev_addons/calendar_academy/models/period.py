from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class Period(models.Model):
    _name = 'academy.period'
    _description = 'Período Académico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    code = fields.Char(string='Código', compute='_compute_code', store=True)
    year = fields.Integer(string='Año', compute='_compute_year', store=True)

    start_date = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    end_date = fields.Date(string='Fecha Fin', required=True, tracking=True)

    # Fechas importantes
    enrollment_start_date = fields.Date(string='Inicio de Matrículas')
    enrollment_end_date = fields.Date(string='Fin de Matrículas')
    class_start_date = fields.Date(string='Inicio de Clases')
    class_end_date = fields.Date(string='Fin de Clases')

    # Estados y configuración
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('enrollment', 'Matrículas'),
        ('active', 'En Curso'),
        ('finished', 'Finalizado'),
        ('closed', 'Cerrado')
    ], string='Estado', default='draft', tracking=True)

    # Relaciones
    course_ids = fields.One2many('academy.course', 'period_id', string='Cursos')

    # Contadores
    course_count = fields.Integer(compute='_compute_counts', store=True)
    student_count = fields.Integer(compute='_compute_counts', store=True)
    teacher_count = fields.Integer(compute='_compute_counts', store=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_year_dates',
         'UNIQUE(year, start_date, end_date)',
         'Ya existe un período académico para estas fechas')
    ]

    @api.depends('start_date', 'end_date')
    def _compute_name(self):
        for record in self:
            if record.start_date and record.end_date:
                record.name = f"Período Académico {record.start_date.year}-{record.end_date.year}"
            else:
                record.name = "Nuevo Período"

    @api.depends('start_date')
    def _compute_code(self):
        for record in self:
            if record.start_date:
                record.code = f"P{record.start_date.year}"
            else:
                record.code = False

    @api.depends('start_date')
    def _compute_year(self):
        for record in self:
            record.year = record.start_date.year if record.start_date else False

    @api.depends('course_ids', 'course_ids.student_ids', 'course_ids.teacher_ids')
    def _compute_counts(self):
        for record in self:
            record.course_count = len(record.course_ids)
            students = record.course_ids.mapped('student_ids')
            record.student_count = len(students)
            teachers = record.course_ids.mapped('teacher_ids')
            record.teacher_count = len(teachers)

    @api.constrains('start_date', 'end_date', 'enrollment_start_date', 'enrollment_end_date',
                    'class_start_date', 'class_end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('La fecha de fin no puede ser anterior a la fecha de inicio'))

            if record.enrollment_start_date and record.enrollment_end_date:
                if record.enrollment_start_date > record.enrollment_end_date:
                    raise ValidationError(_('La fecha de fin de matrículas no puede ser anterior a la fecha de inicio'))
                if record.enrollment_start_date < record.start_date or record.enrollment_end_date > record.end_date:
                    raise ValidationError(_('Las fechas de matrícula deben estar dentro del período académico'))

            if record.class_start_date and record.class_end_date:
                if record.class_start_date > record.class_end_date:
                    raise ValidationError(_('La fecha de fin de clases no puede ser anterior a la fecha de inicio'))
                if record.class_start_date < record.start_date or record.class_end_date > record.end_date:
                    raise ValidationError(_('Las fechas de clases deben estar dentro del período académico'))

    def action_start_enrollment(self):
        self.write({'state': 'enrollment'})

    def action_start_classes(self):
        if not self.class_start_date or not self.class_end_date:
            raise ValidationError(_('Debe definir las fechas de inicio y fin de clases'))
        self.write({'state': 'active'})

    def action_finish(self):
        self.write({'state': 'finished'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_courses(self):
        self.ensure_one()
        return {
            'name': _('Cursos'),
            'view_mode': 'tree,form',
            'res_model': 'academy.course',
            'type': 'ir.actions.act_window',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id}
        }