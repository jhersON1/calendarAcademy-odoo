from odoo import models, fields, api, _


class Parallel(models.Model):
    _name = 'academy.parallel'
    _description = 'Paralelo'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)  # A, B, C, etc.
    code = fields.Char(string='Código', required=True)  # Puede ser el mismo que el nombre
    description = fields.Text(string='Descripción')

    course_ids = fields.One2many('academy.course', 'parallel_id', string='Cursos')
    total_courses = fields.Integer(compute='_compute_stats')
    total_students = fields.Integer(compute='_compute_stats')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_name',
         'UNIQUE(name)',
         'El nombre del paralelo debe ser único'),
        ('unique_code',
         'UNIQUE(code)',
         'El código del paralelo debe ser único')
    ]

    @api.depends('course_ids', 'course_ids.student_ids')
    def _compute_stats(self):
        for record in self:
            record.total_courses = len(record.course_ids)
            record.total_students = sum(len(course.student_ids) for course in record.course_ids)