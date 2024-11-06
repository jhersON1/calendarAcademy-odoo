from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Course(models.Model):
    _name = 'academy.course'
    _description = 'Curso'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'complete_name'

    name = fields.Char(string='Identificador', compute='_compute_name', store=True)
    complete_name = fields.Char(string='Nombre Completo', compute='_compute_name', store=True)
    code = fields.Char(string='Código', required=True, tracking=True)

    # Relaciones principales
    period_id = fields.Many2one('academy.period', string='Período Académico', required=True, tracking=True)
    level_id = fields.Many2one('academy.level', string='Nivel', required=True, tracking=True)
    parallel_id = fields.Many2one('academy.parallel', string='Paralelo', required=True, tracking=True)

    # Capacidad y estudiantes
    capacity = fields.Integer(string='Capacidad', required=True, default=40)
    min_students = fields.Integer(string='Mínimo de Estudiantes', default=15)
    student_ids = fields.Many2many('academy.student',
                                   'course_student_rel',
                                   'course_id',
                                   'student_id',
                                   string='Estudiantes')

    # Materias y profesores
    teacher_ids = fields.Many2many('academy.teacher',
                                   'course_teacher_rel',
                                   'course_id',
                                   'teacher_id',
                                   string='Profesores')

    subject_ids = fields.Many2many('academy.subject',
                                   'course_subject_rel',
                                   'course_id',
                                   'subject_id',
                                   string='Materias')
    enrolled_count = fields.Integer(compute='_compute_counts', store=True)

    # Horario
    schedule_ids = fields.One2many('academy.schedule', 'course_id', string='Horarios')

    # Estado y seguimiento
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('finished', 'Finalizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    active = fields.Boolean(default=True)

    @api.depends('level_id', 'parallel_id', 'period_id')
    def _compute_name(self):
        for record in self:
            if record.level_id and record.parallel_id:
                record.name = f"{record.level_id.name}{record.parallel_id.name}"
                record.complete_name = f"{record.level_id.name}{record.parallel_id.name} - {record.period_id.name}"
            else:
                record.name = "Nuevo Curso"
                record.complete_name = "Nuevo Curso"

    @api.depends('student_ids')
    def _compute_counts(self):
        for record in self:
            record.enrolled_count = len(record.student_ids)

    @api.depends('level_id')
    def _compute_subjects(self):
        """Obtiene las materias asignadas al nivel"""
        for record in self:
            if record.level_id:
                record.subject_ids = record.level_id.subject_ids
            else:
                record.subject_ids = False

    @api.depends('schedule_ids.teacher_id')
    def _compute_teachers(self):
        """Obtiene los profesores asignados a través del horario"""
        for record in self:
            record.teacher_ids = record.schedule_ids.mapped('teacher_id')

    @api.constrains('enrolled_count', 'capacity')
    def _check_capacity(self):
        for record in self:
            if record.enrolled_count > record.capacity:
                raise ValidationError(_('No se puede exceder la capacidad del curso'))

    def action_activate(self):
        for record in self:
            if record.enrolled_count < record.min_students:
                raise ValidationError(_('No se puede activar el curso: insuficientes estudiantes'))
            record.write({'state': 'active'})

    def action_finish(self):
        return self.write({'state': 'finished'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def action_draft(self):
        return self.write({'state': 'draft'})

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.complete_name))
        return result