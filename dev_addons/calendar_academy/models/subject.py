from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Subject(models.Model):
    _name = 'academy.subject'
    _description = 'Materia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, tracking=True)
    code = fields.Char(string='Código', required=True, tracking=True)
    description = fields.Text(string='Descripción')

    # Configuración académica
    credits = fields.Integer(string='Créditos', default=1)
    hours_per_week = fields.Integer(string='Horas por Semana', required=True)
    min_grade = fields.Float(string='Nota Mínima', default=7.0)
    weight = fields.Float(string='Peso en Promedio', default=1.0)
    is_mandatory = fields.Boolean(string='Es Obligatoria', default=True)

    # Relaciones
    level_ids = fields.Many2many('academy.level',
                                 'level_subject_rel',
                                 'subject_id',
                                 'level_id',
                                 string='Niveles')
    prerequisite_ids = fields.Many2many(
        'academy.subject',
        'subject_prerequisites_rel',
        'subject_id',
        'prerequisite_id',
        string='Prerrequisitos'
    )

    # Método de evaluación
    evaluation_method = fields.Selection([
        ('numeric', 'Numérica'),
        ('letter', 'Letras'),
        ('approval', 'Aprobación')
    ], string='Método de Evaluación', default='numeric', required=True)

    # Componentes de evaluación
    has_homework = fields.Boolean(string='Tiene Tareas')
    has_projects = fields.Boolean(string='Tiene Proyectos')
    has_midterm = fields.Boolean(string='Tiene Examen Parcial')
    has_final = fields.Boolean(string='Tiene Examen Final')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_code',
         'UNIQUE(code)',
         'El código de la materia debe ser único')
    ]

    @api.constrains('min_grade')
    def _check_min_grade(self):
        for record in self:
            if record.min_grade < 0 or record.min_grade > 10:
                raise ValidationError(_('La nota mínima debe estar entre 0 y 10'))

    @api.constrains('hours_per_week')
    def _check_hours(self):
        for record in self:
            if record.hours_per_week <= 0:
                raise ValidationError(_('Las horas por semana deben ser mayores a 0'))

    @api.constrains('prerequisite_ids')
    def _check_prerequisites(self):
        for record in self:
            if record in record.prerequisite_ids:
                raise ValidationError(_('Una materia no puede ser prerrequisito de sí misma'))

    def name_get(self):
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result