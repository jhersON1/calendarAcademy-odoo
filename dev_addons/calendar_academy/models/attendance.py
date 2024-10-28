from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class Attendance(models.Model):
    _name = 'academy.attendance'
    _description = 'Control de Asistencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, course_id'

    name = fields.Char(string='Referencia', readonly=True, copy=False, default='Nuevo')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.today, tracking=True)
    course_id = fields.Many2one('academy.course', string='Curso', required=True, tracking=True)
    subject_id = fields.Many2one('academy.subject', string='Materia', required=True, tracking=True)
    teacher_id = fields.Many2one('academy.teacher', string='Profesor', required=True, tracking=True)
    period_id = fields.Many2one(related='course_id.period_id', store=True)

    attendance_line_ids = fields.One2many('academy.attendance.line', 'attendance_id', string='Líneas de Asistencia')
    total_present = fields.Integer(compute='_compute_attendance_stats', store=True)
    total_absent = fields.Integer(compute='_compute_attendance_stats', store=True)
    total_late = fields.Integer(compute='_compute_attendance_stats', store=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('taken', 'Tomada'),
        ('confirmed', 'Confirmada')
    ], string='Estado', default='draft', tracking=True)

    _sql_constraints = [
        ('unique_attendance',
         'UNIQUE(date, course_id, subject_id)',
         'Ya existe un registro de asistencia para esta fecha, curso y materia')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('academy.attendance') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('attendance_line_ids.attendance_status')
    def _compute_attendance_stats(self):
        for record in self:
            record.total_present = len(record.attendance_line_ids.filtered(lambda r: r.attendance_status == 'present'))
            record.total_absent = len(record.attendance_line_ids.filtered(lambda r: r.attendance_status == 'absent'))
            record.total_late = len(record.attendance_line_ids.filtered(lambda r: r.attendance_status == 'late'))

    def action_generate_attendance_lines(self):
        """Genera líneas de asistencia para todos los estudiantes del curso"""
        for record in self:
            # Eliminar líneas existentes
            record.attendance_line_ids.unlink()

            # Crear nueva línea para cada estudiante
            for student in record.course_id.student_ids:
                self.env['academy.attendance.line'].create({
                    'attendance_id': record.id,
                    'student_id': student.id,
                    'attendance_status': 'present'
                })

            record.state = 'taken'

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})


class AttendanceLine(models.Model):
    _name = 'academy.attendance.line'
    _description = 'Línea de Asistencia'

    attendance_id = fields.Many2one('academy.attendance', string='Asistencia', required=True, ondelete='cascade')
    student_id = fields.Many2one('academy.student', string='Estudiante', required=True)
    attendance_status = fields.Selection([
        ('present', 'Presente'),
        ('absent', 'Ausente'),
        ('late', 'Atrasado'),
        ('justified', 'Justificado')
    ], string='Estado', required=True, default='present')
    justification = fields.Text(string='Justificación')
    arrival_time = fields.Float(string='Hora de Llegada')

    @api.constrains('arrival_time')
    def _check_arrival_time(self):
        for record in self:
            if record.arrival_time and (record.arrival_time < 0 or record.arrival_time >= 24):
                raise ValidationError(_('La hora de llegada debe estar entre 0 y 24'))