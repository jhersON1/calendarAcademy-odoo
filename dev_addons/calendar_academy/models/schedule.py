from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Schedule(models.Model):
    _name = 'academy.schedule'
    _description = 'Horario'
    _rec_name = 'display_name'

    course_id = fields.Many2one('academy.course', string='Curso', required=True)
    subject_id = fields.Many2one('academy.subject', string='Materia', required=True)
    teacher_id = fields.Many2one('academy.teacher', string='Profesor', required=True)

    day = fields.Selection([
        ('monday', 'Lunes'),
        ('tuesday', 'Martes'),
        ('wednesday', 'Miércoles'),
        ('thursday', 'Jueves'),
        ('friday', 'Viernes')
    ], string='Día', required=True)

    start_hour = fields.Float(string='Hora Inicio', required=True)
    end_hour = fields.Float(string='Hora Fin', required=True)
    duration = fields.Float(string='Duración (Horas)', compute='_compute_duration', store=True)

    classroom = fields.Char(string='Aula')
    display_name = fields.Char(compute='_compute_display_name', store=True)
    color = fields.Integer(string='Color')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_schedule',
         'UNIQUE(course_id, subject_id, day, start_hour)',
         'Ya existe una clase programada para este horario')
    ]

    @api.depends('start_hour', 'end_hour')
    def _compute_duration(self):
        for record in self:
            record.duration = record.end_hour - record.start_hour

    @api.depends('course_id', 'subject_id', 'day', 'start_hour', 'end_hour')
    def _compute_display_name(self):
        for record in self:
            if record.course_id and record.subject_id:
                start_hour_str = f"{int(record.start_hour):02d}:{int(record.start_hour % 1 * 60):02d}"
                end_hour_str = f"{int(record.end_hour):02d}:{int(record.end_hour % 1 * 60):02d}"
                record.display_name = f"{record.course_id.name} - {record.subject_id.name} - " \
                                      f"{dict(record._fields['day'].selection).get(record.day)} " \
                                      f"({start_hour_str}-{end_hour_str})"
            else:
                record.display_name = "Nuevo Horario"

    @api.constrains('start_hour', 'end_hour')
    def _check_hours(self):
        for record in self:
            if record.start_hour < 0 or record.start_hour >= 24 or \
                    record.end_hour < 0 or record.end_hour >= 24:
                raise ValidationError(_('Las horas deben estar entre 0 y 24'))
            if record.start_hour >= record.end_hour:
                raise ValidationError(_('La hora de inicio debe ser anterior a la hora de fin'))

    @api.constrains('course_id', 'teacher_id', 'day', 'start_hour', 'end_hour')
    def _check_schedule_conflict(self):
        for record in self:
            # Buscar conflictos para el mismo profesor
            conflicting_schedules = self.search([
                ('id', '!=', record.id),
                ('teacher_id', '=', record.teacher_id.id),
                ('day', '=', record.day),
                '|',
                '&', ('start_hour', '<=', record.start_hour), ('end_hour', '>', record.start_hour),
                '&', ('start_hour', '<', record.end_hour), ('end_hour', '>=', record.end_hour)
            ])
            if conflicting_schedules:
                raise ValidationError(_('El profesor ya tiene una clase programada en este horario'))

            # Buscar conflictos para el mismo curso
            conflicting_schedules = self.search([
                ('id', '!=', record.id),
                ('course_id', '=', record.course_id.id),
                ('day', '=', record.day),
                '|',
                '&', ('start_hour', '<=', record.start_hour), ('end_hour', '>', record.start_hour),
                '&', ('start_hour', '<', record.end_hour), ('end_hour', '>=', record.end_hour)
            ])
            if conflicting_schedules:
                raise ValidationError(_('El curso ya tiene una clase programada en este horario'))