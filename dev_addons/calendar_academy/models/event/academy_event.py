from odoo import models, fields, api, _
from datetime import datetime, timedelta


class AcademyEvent(models.Model):
    _name = 'academy.event'
    _description = 'Administrative Reminders and Events'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(
        string='Título',
        required=True,
        tracking=True
    )

    reminder_type = fields.Selection([
        ('event', 'Evento'),
        ('note', 'Nota'),
        ('meeting', 'Reunión'),
        ('task', 'Tarea'),
        ('deadline', 'Fecha Límite'),
        ('reminder', 'Recordatorio General')
    ], string='Tipo de Recordatorio',
        required=True,
        default='event',
        tracking=True)

    event_type = fields.Selection([
        ('academic', 'Académico'),
        ('administrative', 'Administrativo'),
        ('extracurricular', 'Extracurricular')
    ], string='Categoría',
        required=True,
        default='administrative',
        tracking=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Importante'),
        ('2', 'Urgente')
    ], string='Prioridad', default='0', tracking=True)

    start_date = fields.Datetime(
        string='Fecha Inicio',
        required=True,
        tracking=True
    )

    end_date = fields.Datetime(
        string='Fecha Fin',
        required=True,
        tracking=True
    )

    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )

    is_virtual = fields.Boolean(
        string='Es Virtual',
        tracking=True
    )

    location = fields.Char(
        string='Ubicación',
        tracking=True
    )

    virtual_url = fields.Char(
        string='Link de Reunión',
        tracking=True
    )

    description = fields.Html(
        string='Descripción',
        sanitize=True
    )

    # Participantes
    course_ids = fields.Many2many(
        'academy.course',
        string='Cursos Relacionados'
    )

    teacher_ids = fields.Many2many(
        'academy.teacher',
        string='Profesores'
    )

    student_ids = fields.Many2many(
        'academy.student',
        string='Estudiantes'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Realizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado',
        default='draft',
        tracking=True)

    color = fields.Integer(
        string='Color',
        compute='_compute_color',
        store=True
    )

    @api.depends('reminder_type', 'priority')
    def _compute_color(self):
        for record in self:
            # Colores base por tipo de recordatorio
            colors = {
                'event': 1,  # Azul
                'note': 2,  # Verde
                'meeting': 3,  # Amarillo
                'task': 4,  # Rojo
                'deadline': 5,  # Morado
                'reminder': 6  # Naranja
            }
            base_color = colors.get(record.reminder_type, 0)

            # Modificar color según prioridad
            if record.priority == '2':  # Urgente
                base_color += 3
            elif record.priority == '1':  # Importante
                base_color += 1

            record.color = base_color

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValueError(
                        _('La fecha de fin no puede ser anterior a la fecha de inicio'))


    # Simple workflow
    def action_confirm(self):
        """Confirmar evento"""
        self.write({'state': 'confirmed'})

    def action_mark_done(self):
        """Marcar evento como realizado"""
        self.write({'state': 'done'})

    def action_cancel(self):
        """Cancelar evento"""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})

    def action_add_course_students(self):
        """Añade todos los estudiantes de los cursos seleccionados"""
        for record in self:
            if record.course_ids:
                students = record.course_ids.mapped('student_ids')
                record.student_ids = [(6, 0, students.ids)]
        return True

    def action_add_course_teachers(self):
        """Añade todos los profesores de los cursos seleccionados"""
        for record in self:
            if record.course_ids:
                teachers = record.course_ids.mapped('teacher_ids')
                record.teacher_ids = [(6, 0, teachers.ids)]
        return True

    def action_add_all_active_courses(self):
        """Añade todos los cursos activos del período actual"""
        active_period = self.env['academy.period'].search([
            ('state', '=', 'active')
        ], limit=1)

        if active_period:
            active_courses = self.env['academy.course'].search([
                ('period_id', '=', active_period.id),
                ('state', '=', 'active')
            ])

            if active_courses:
                self.write({
                    'course_ids': [(6, 0, active_courses.ids)]
                })
                # Opcional: añadir automáticamente estudiantes y profesores
                self.action_add_course_students()
                self.action_add_course_teachers()

        return True

    def action_add_all_participants(self):
        """Añade todos los participantes activos"""
        self.ensure_one()

        try:
            current_user = self.env.user
            current_teacher = self.env['academy.teacher'].search([('user_id', '=', current_user.id)], limit=1)

            # Si el creador es un profesor, añadirlo automáticamente
            if current_teacher:
                self.write({
                    'teacher_ids': [(4, current_teacher.id)],
                    'responsible_id': current_user.id
                })

            # Obtener todos los profesores activos
            teachers = self.env['academy.teacher'].search([('active', '=', True)])

            # Obtener todos los estudiantes activos
            students = self.env['academy.student'].search([('active', '=', True)])

            # Obtener todos los cursos activos del período actual
            active_period = self.env['academy.period'].search([('state', '=', 'active')], limit=1)
            active_courses = False
            if active_period:
                active_courses = self.env['academy.course'].search([
                    ('period_id', '=', active_period.id),
                    ('state', '=', 'active')
                ])

            # Actualizar los campos
            vals = {
                'teacher_ids': [(6, 0, teachers.ids)],
                'student_ids': [(6, 0, students.ids)]
            }

            if active_courses:
                vals['course_ids'] = [(6, 0, active_courses.ids)]

            self.write(vals)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Se han añadido todos los participantes',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error al añadir participantes: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)

        # Si el usuario actual es un profesor, añadirlo automáticamente
        current_user = self.env.user
        current_teacher = self.env['academy.teacher'].search([('user_id', '=', current_user.id)], limit=1)

        if current_teacher:
            defaults['teacher_ids'] = [(4, current_teacher.id)]
            defaults['responsible_id'] = current_user.id

        return defaults