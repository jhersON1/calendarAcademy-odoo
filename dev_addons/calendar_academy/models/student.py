from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class Student(models.Model):
    _name = 'academy.student'
    _description = 'Estudiante'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    image = fields.Binary(string='Imagen', attachment=True)

    # Información personal
    name = fields.Char(string='Nombre Completo', required=True, tracking=True)
    identification = fields.Char(string='Identificación', required=True, tracking=True)
    birth_date = fields.Date(string='Fecha de Nacimiento', required=True)
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro')
    ], string='Género', required=True)
    age = fields.Integer(string='Edad', compute='_compute_age', store=True)

    # Información de contacto
    email = fields.Char(string='Correo Electrónico')
    phone = fields.Char(string='Teléfono')
    address = fields.Text(string='Dirección')

    # Información académica
    enrollment_date = fields.Date(string='Fecha de Matriculación', default=fields.Date.today)
    current_course_id = fields.Many2one('academy.course', string='Curso Actual',
                                        compute='_compute_current_course', store=True)
    course_ids = fields.Many2many('academy.course',
                                  'course_student_rel',
                                  'student_id',
                                  'course_id',
                                  string='Historial de Cursos')

    # Información médica
    blood_type = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-')
    ], string='Tipo de Sangre')
    medical_conditions = fields.Text(string='Condiciones Médicas')
    allergies = fields.Text(string='Alergias')

    # Relaciones
    parent_id = fields.Many2one('academy.parent', string='Representante Principal', required=True)
    secondary_parent_id = fields.Many2one('academy.parent', string='Representante Secundario')
    user_id = fields.Many2one('res.users', string='Usuario Relacionado')

    # Estados y seguimiento
    status = fields.Selection([
        ('enrolled', 'Matriculado'),
        ('suspended', 'Suspendido'),
        ('graduated', 'Graduado'),
        ('withdrawn', 'Retirado')
    ], string='Estado', default='enrolled', tracking=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_identification',
         'UNIQUE(identification)',
         'Ya existe un estudiante con esta identificación')
    ]

    @api.depends('birth_date')
    def _compute_age(self):
        today = date.today()
        for record in self:
            if record.birth_date:
                record.age = today.year - record.birth_date.year - \
                             ((today.month, today.day) <
                              (record.birth_date.month, record.birth_date.day))
            else:
                record.age = 0

    @api.depends('course_ids')
    def _compute_current_course(self):
        current_period = self.env['academy.period'].search([
            ('state', '=', 'active')
        ], limit=1)
        for record in self:
            current_course = record.course_ids.filtered(
                lambda c: c.period_id == current_period
            )
            record.current_course_id = current_course[0] if current_course else False

    @api.constrains('birth_date')
    def _check_birth_date(self):
        for record in self:
            if record.birth_date and record.birth_date > fields.Date.today():
                raise ValidationError(_('La fecha de nacimiento no puede ser futura'))

    def action_create_user(self):
        """Crea un usuario para el estudiante"""
        for record in self:
            if not record.user_id:
                # Primero creamos el usuario básico
                user = self.env['res.users'].with_context(no_reset_password=True).create({
                    'name': record.name,
                    'login': record.email,
                    'email': record.email,
                    'password': record.identification,
                })
                # Luego asignamos el grupo
                self.env['res.groups'].browse(
                    self.env.ref('calendar_academy.group_academy_student').id
                ).write({'users': [(4, user.id)]})
                record.user_id = user.id

    def action_view_grades(self):
        self.ensure_one()
        return {
            'name': _('Calificaciones'),
            'view_mode': 'list,form',
            'res_model': 'academy.grade.line',
            'type': 'ir.actions.act_window',
            'domain': [('student_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_view_attendance(self):
        self.ensure_one()
        return {
            'name': _('Asistencia'),
            'view_mode': 'list,form',
            'res_model': 'academy.attendance.line',
            'type': 'ir.actions.act_window',
            'domain': [('student_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_suspend(self):
        return self.write({'status': 'suspended'})

    def action_reactivate(self):
        return self.write({'status': 'enrolled'})

    def action_graduate(self):
        return self.write({'status': 'graduated'})

    def action_withdraw(self):
        return self.write({'status': 'withdrawn'})