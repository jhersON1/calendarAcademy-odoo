from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Level(models.Model):
    _name = 'academy.level'
    _description = 'Nivel Académico'
    _order = 'sequence'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    description = fields.Text(string='Descripción')

    # Relaciones
    subject_ids = fields.Many2many('academy.subject',
                                   'level_subject_rel',
                                   'level_id',
                                   'subject_id',
                                   string='Materias')
    course_ids = fields.One2many('academy.course', 'level_id', string='Cursos')

    # Configuración
    min_age = fields.Integer(string='Edad Mínima')
    max_age = fields.Integer(string='Edad Máxima')
    is_mandatory = fields.Boolean(string='Es Obligatorio', default=True)

    # Estadísticas
    total_students = fields.Integer(compute='_compute_stats')
    total_courses = fields.Integer(compute='_compute_stats')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_code',
         'UNIQUE(code)',
         'El código del nivel debe ser único')
    ]

    @api.depends('course_ids', 'course_ids.student_ids')
    def _compute_stats(self):
        for record in self:
            record.total_courses = len(record.course_ids)
            record.total_students = sum(len(course.student_ids) for course in record.course_ids)

    @api.constrains('min_age', 'max_age')
    def _check_ages(self):
        for record in self:
            if record.min_age and record.max_age and record.min_age > record.max_age:
                raise ValidationError(_('La edad mínima no puede ser mayor que la edad máxima'))

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, f"{record.code} - {record.name}"))
        return result