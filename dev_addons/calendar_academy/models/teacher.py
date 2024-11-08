from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Teacher(models.Model):
    _name = 'academy.teacher'
    _description = 'Profesor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    image = fields.Binary(string='Imagen', attachment=True)

    # Información personal
    name = fields.Char(string='Nombre Completo', required=True, tracking=True)
    identification = fields.Char(string='Identificación', required=True, tracking=True)
    birth_date = fields.Date(string='Fecha de Nacimiento')
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro')
    ], string='Género')

    # Información de contacto
    email = fields.Char(string='Correo Electrónico', required=True, tracking=True)
    phone = fields.Char(string='Teléfono')
    mobile = fields.Char(string='Celular')
    address = fields.Text(string='Dirección')

    # Información profesional
    specialty = fields.Many2many('academy.subject', string='Especialidades')
    education_level = fields.Selection([
        ('bachelor', 'Licenciatura'),
        ('master', 'Maestría'),
        ('phd', 'Doctorado'),
        ('other', 'Otro')
    ], string='Nivel de Educación')
    years_experience = fields.Integer(string='Años de Experiencia')
    hire_date = fields.Date(string='Fecha de Contratación', default=fields.Date.today)

    # Información laboral
    schedule_ids = fields.One2many('academy.schedule', 'teacher_id', string='Horarios')
    course_ids = fields.Many2many('academy.course',
                                  'course_teacher_rel',
                                  'teacher_id',
                                  'course_id',
                                  string='Cursos Asignados')
    max_hours = fields.Integer(string='Máximo de Horas Semanales', default=40)
    current_hours = fields.Float(string='Horas Actuales', compute='_compute_hours')

    # Usuario relacionado
    user_id = fields.Many2one('res.users', string='Usuario Relacionado')

    # Estado y seguimiento
    status = fields.Selection([
        ('active', 'Activo'),
        ('on_leave', 'De Permiso'),
        ('inactive', 'Inactivo')
    ], string='Estado', default='active', tracking=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_identification',
         'UNIQUE(identification)',
         'Ya existe un profesor con esta identificación'),
        ('unique_email',
         'UNIQUE(email)',
         'Ya existe un profesor con este correo electrónico')
    ]

    @api.depends('schedule_ids.course_id')
    def _compute_courses(self):
        for record in self:
            record.course_ids = record.schedule_ids.mapped('course_id')

    @api.depends('schedule_ids')
    def _compute_hours(self):
        for record in self:
            total_hours = 0
            for schedule in record.schedule_ids:
                total_hours += schedule.duration
            record.current_hours = total_hours

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and '@' not in record.email:
                raise ValidationError(_('Por favor ingrese un correo electrónico válido'))

    @api.constrains('current_hours', 'max_hours')
    def _check_hours(self):
        for record in self:
            if record.current_hours > record.max_hours:
                raise ValidationError(_('El profesor no puede exceder el máximo de horas semanales'))

    def action_create_user(self):
        """Crea un usuario para el profesor"""
        for record in self:
            if not record.user_id:
                user = self.env['res.users'].create({
                    'name': record.name,
                    'login': record.email,
                    'email': record.email,
                    'password': record.identification,
                    'groups_id': [(6, 0, [self.env.ref('calendar_academy.group_academy_teacher').id])]
                })
                record.user_id = user.id

    def action_view_schedule(self):
        self.ensure_one()
        return {
            'name': _('Horario'),
            'view_mode': 'list,form',
            'res_model': 'academy.schedule',
            'type': 'ir.actions.act_window',
            'domain': [('teacher_id', '=', self.id)],
            'context': {'default_teacher_id': self.id},
            'views': [
                (self.env.ref('calendar_academy.view_academy_schedule_list').id, 'list'),
                (self.env.ref('calendar_academy.view_academy_schedule_form').id, 'form')
            ]
        }

    def action_on_leave(self):
        return self.write({'status': 'on_leave'})

    def action_activate(self):
        return self.write({'status': 'active'})

    def action_inactivate(self):
        return self.write({'status': 'inactive'})

    def action_view_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard del Profesor',
            'res_model': 'academy.event',
            'view_mode': 'calendar,kanban',
            'domain': [
                ('start_date', '>=', fields.Date.today()),
                '|', '|',
                ('responsible_id', '=', self.user_id.id),
                ('teacher_ids', 'in', [self.id]),
                ('course_ids.teacher_ids', 'in', [self.id])
            ],
            'context': {
                'search_default_upcoming': 1,
                'calendar_view': True,
                'default_responsible_id': self.user_id.id,
                'default_teacher_ids': [(4, self.id)],
                'default_reminder_type': 'event',
                'default_event_type': 'academic'
            }
        }
