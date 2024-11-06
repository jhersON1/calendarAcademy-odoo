from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError

class Grade(models.Model):
    _name = 'academy.grade'
    _description = 'Calificación'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'period_id desc, evaluation_date'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    course_id = fields.Many2one('academy.course', string='Curso', required=True, tracking=True)
    subject_id = fields.Many2one('academy.subject', string='Materia', required=True, tracking=True)
    period_id = fields.Many2one(related='course_id.period_id', store=True)
    teacher_id = fields.Many2one('academy.teacher', string='Profesor', required=True, tracking=True)

    evaluation_type = fields.Selection([
        ('homework', 'Tarea'),
        ('test', 'Prueba'),
        ('exam', 'Examen'),
        ('project', 'Proyecto'),
        ('participation', 'Participación')
    ], string='Tipo de Evaluación', required=True)

    evaluation_date = fields.Date(string='Fecha de Evaluación', required=True)
    max_grade = fields.Float(string='Nota Máxima', default=10.0, required=True)
    weight = fields.Float(string='Peso (%)', default=100, required=True)

    grade_line_ids = fields.One2many('academy.grade.line', 'grade_id', string='Calificaciones')
    average_grade = fields.Float(compute='_compute_average', store=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Ingresada'),
        ('published', 'Publicada')
    ], string='Estado', default='draft', tracking=True)

    @api.depends('course_id', 'subject_id', 'evaluation_type', 'evaluation_date')
    def _compute_name(self):
        for record in self:
            if record.course_id and record.subject_id:
                record.name = f"{record.course_id.name} - {record.subject_id.name} - " \
                              f"{dict(record._fields['evaluation_type'].selection).get(record.evaluation_type)} - " \
                              f"{record.evaluation_date}"
            else:
                record.name = "Nueva Calificación"

    @api.depends('grade_line_ids.grade')
    def _compute_average(self):
        for record in self:
            grades = record.grade_line_ids.mapped('grade')
            record.average_grade = sum(grades) / len(grades) if grades else 0.0

    @api.constrains('weight')
    def _check_weight(self):
        for record in self:
            if record.weight < 0 or record.weight > 100:
                raise ValidationError(_('El peso debe estar entre 0 y 100'))

    @api.constrains('max_grade')
    def _check_max_grade(self):
        for record in self:
            if record.max_grade <= 0:
                raise ValidationError(_('La nota máxima debe ser mayor a 0'))

    def action_generate_grade_lines(self):
        """Genera líneas de calificación para todos los estudiantes del curso"""
        for record in self:
            # Eliminar líneas existentes
            record.grade_line_ids.unlink()

            # Crear nueva línea para cada estudiante
            for student in record.course_id.student_ids:
                self.env['academy.grade.line'].create({
                    'grade_id': record.id,
                    'student_id': student.id,
                })

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_publish(self):
        self.write({'state': 'published'})

    def action_draft(self):
        self.write({'state': 'draft'})


class GradeLine(models.Model):
    _name = 'academy.grade.line'
    _description = 'Línea de Calificación'
    _rec_name = 'student_id'

    grade_id = fields.Many2one('academy.grade', string='Calificación', required=True, ondelete='cascade')
    student_id = fields.Many2one('academy.student', string='Estudiante', required=True)
    grade = fields.Float(string='Nota', default=0.0)
    comment = fields.Text(string='Comentario')

    max_grade = fields.Float(related='grade_id.max_grade')

    @api.constrains('grade', 'max_grade')
    def _check_grade(self):
        for record in self:
            if record.grade < 0:
                raise ValidationError(_('La calificación no puede ser negativa'))
            if record.grade > record.max_grade:
                raise ValidationError(_('La calificación no puede ser mayor a la nota máxima'))


class StudentGradeReport(models.Model):
    _name = 'academy.student.grade.report'
    _description = 'Reporte de Calificaciones del Estudiante'
    _auto = False
    _order = 'period_id desc, course_id, subject_id'

    student_id = fields.Many2one('academy.student', string='Estudiante', readonly=True)
    course_id = fields.Many2one('academy.course', string='Curso', readonly=True)
    subject_id = fields.Many2one('academy.subject', string='Materia', readonly=True)
    period_id = fields.Many2one('academy.period', string='Período', readonly=True)
    final_grade = fields.Float(string='Nota Final', readonly=True, group_operator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                SELECT
                    row_number() OVER () as id,
                    gl.student_id,
                    g.course_id,
                    g.subject_id,
                    g.period_id,
                    SUM(gl.grade * g.weight / 100) / SUM(g.weight / 100) as final_grade
                FROM academy_grade_line gl
                JOIN academy_grade g ON gl.grade_id = g.id
                WHERE g.state = 'published'
                GROUP BY gl.student_id, g.course_id, g.subject_id, g.period_id
            )
        """ % self._table)