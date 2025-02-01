from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


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

    creator_type = fields.Selection([
        ('student', 'Estudiante'),
        ('teacher', 'Profesor'),
        ('admin', 'Administrativo')
    ], string='Tipo de Creador', default='admin', required=True)

    is_admin_event = fields.Boolean(compute='_compute_is_admin_event', store=True)
    is_teacher_event = fields.Boolean(compute='_compute_is_teacher_event', store=True)
    student_creator_id = fields.Many2one('academy.student', string='Estudiante Creador')

    read_status_ids = fields.One2many(
        'academy.event.read.status',
        'event_id',
        string='Estados de Lectura'
    )
    read_count = fields.Integer(
        string='Lecturas',
        compute='_compute_read_count',
        store=True
    )
    unread_count = fields.Integer(
        string='No Leídos',
        compute='_compute_read_count',
        store=True
    )

    # En academy.event
    is_task = fields.Boolean(compute='_compute_is_task')
    task_id = fields.Many2one('academy.task', string='Tarea Relacionada', tracking=True)

    # En academy.event
    subject_id = fields.Many2one(
        'academy.subject',
        string='Materia',
        domain="[('id', 'in', available_subjects_ids)]"
    )

    available_subjects_ids = fields.Many2many(
        'academy.subject',
        compute='_compute_available_subjects',
        store=True
    )

    # Campos específicos cuando es tarea
    max_score = fields.Float(
        string='Puntuación Máxima',
        default=10.0
    )
    weight = fields.Float(
        string='Peso en Calificación (%)',
        default=100.0
    )
    submission_type = fields.Selection([
        ('online', 'En línea'),
        ('physical', 'Física'),
        ('both', 'Ambas')
    ], string='Tipo de Entrega', default='online')

    allow_late_submission = fields.Boolean(
        string='Permitir Entregas Tardías',
        default=False
    )
    late_submission_penalty = fields.Float(
        string='Penalización por Retraso (%)',
        default=0
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Archivos Adjuntos'
    )


    @api.constrains('weight')
    def _check_weight(self):
        for record in self:
            if record.reminder_type == 'task':
                if record.weight < 0 or record.weight > 100:
                    raise ValidationError(_('El peso debe estar entre 0 y 100'))

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            if record.reminder_type == 'task':
                # Crear tarea al confirmar el recordatorio
                task_vals = {
                    'name': record.name,
                    'course_id': record.course_ids[0].id if record.course_ids else False,
                    'subject_id': record.subject_id.id,
                    'teacher_id': self.env['academy.teacher'].search(
                        [('user_id', '=', record.responsible_id.id)], limit=1
                    ).id,
                    'description': record.description,
                    'deadline': record.end_date,
                    'available_from': record.start_date,
                    'max_score': record.max_score,
                    'weight': record.weight,
                    'submission_type': record.submission_type,
                    'allow_late_submission': record.allow_late_submission,
                    'late_submission_penalty': record.late_submission_penalty,
                    'attachment_ids': [(6, 0, record.attachment_ids.ids)],
                    'state': 'published'
                }
                task = self.env['academy.task'].create(task_vals)
                record.task_id = task.id
        return res

    @api.depends('course_ids', 'responsible_id')
    def _compute_available_subjects(self):
        for record in self:
            teacher = self.env['academy.teacher'].search(
                [('user_id', '=', record.responsible_id.id)], limit=1
            )
            if teacher:
                # Primero obtenemos las especialidades del profesor
                teacher_subjects = teacher.specialty

                # Si hay cursos seleccionados, filtramos las materias que el profesor
                # puede dictar en esos cursos específicos
                if record.course_ids:
                    course_subjects = record.course_ids.mapped('subject_ids')
                    # Intersección entre especialidades del profesor y materias del curso
                    available_subjects = teacher_subjects & course_subjects
                else:
                    # Si no hay cursos seleccionados, mostramos todas sus especialidades
                    available_subjects = teacher_subjects

                record.available_subjects_ids = available_subjects.ids
            else:
                record.available_subjects_ids = []

    @api.onchange('reminder_type', 'responsible_id')
    def _onchange_reminder_type(self):
        if self.reminder_type == 'task':
            self.event_type = 'academic'  # Forzar tipo académico

            # Verificar si el profesor tiene especialidades
            teacher = self.env['academy.teacher'].search(
                [('user_id', '=', self.responsible_id.id)], limit=1
            )
            if teacher and not teacher.specialty:
                return {
                    'warning': {
                        'title': _('Advertencia'),
                        'message': _('No tiene materias asignadas en su perfil de profesor. '
                                     'Por favor, actualice sus especialidades antes de crear una tarea.')
                    }
                }

    @api.constrains('reminder_type', 'subject_id', 'responsible_id')
    def _check_teacher_subject(self):
        for record in self:
            if record.reminder_type == 'task':
                teacher = self.env['academy.teacher'].search(
                    [('user_id', '=', record.responsible_id.id)], limit=1
                )
                if teacher and record.subject_id not in teacher.specialty:
                    raise ValidationError(_(
                        'Solo puede crear tareas para materias que estén en sus especialidades.'
                    ))

    @api.depends('reminder_type')
    def _compute_is_task(self):
        for record in self:
            record.is_task = record.reminder_type == 'task'

    @api.onchange('reminder_type')
    def _onchange_reminder_type(self):
        if self.reminder_type == 'task':
            # Mostrar campos adicionales
            self.event_type = 'academic'  # Forzar tipo académico

    @api.depends('read_status_ids.read_status')
    def _compute_read_count(self):
        for record in self:
            read_statuses = record.read_status_ids
            record.read_count = len(read_statuses.filtered(lambda r: r.read_status == 'read'))
            record.unread_count = len(read_statuses.filtered(lambda r: r.read_status == 'unread'))

    def _prepare_read_status(self, users):
        """Prepara los estados de lectura para los usuarios especificados"""
        status_vals = []
        for user in users:
            if not self.read_status_ids.filtered(lambda r: r.user_id == user):
                status_vals.append({
                    'event_id': self.id,
                    'user_id': user.id,
                    'read_status': 'unread'
                })
        return status_vals

    def action_view_read_status(self):
        """Abre una vista con el estado de lectura de los usuarios"""
        self.ensure_one()
        return {
            'name': 'Estado de Lectura',
            'view_mode': 'list,form',
            'res_model': 'academy.event.read.status',
            'domain': [('event_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_event_id': self.id}
        }

    # En academy_event.py
    def notify_event_read(self, user_id):
        """
        Marca el evento como leído por un usuario específico
        Args:
            user_id (int): ID del usuario que lee el evento
        Returns:
            bool: True si se marca correctamente
        """
        self.ensure_one()

        _logger.info("Iniciando notify_event_read para evento %s y usuario %s", self.id, user_id)

        try:
            EventReadStatus = self.env['academy.event.read.status']

            # Buscar registro existente
            read_status = EventReadStatus.search([
                ('event_id', '=', self.id),
                ('user_id', '=', user_id)
            ], limit=1)

            current_time = fields.Datetime.now()

            if read_status:
                if read_status.read_status != 'read':
                    read_status.write({
                        'read_status': 'read',
                        'read_date': current_time
                    })
            else:
                # Crear nuevo registro
                EventReadStatus.create({
                    'event_id': self.id,
                    'user_id': user_id,
                    'read_status': 'read',
                    'read_date': current_time
                })

            # Notificar al creador si es diferente del lector
            if self.responsible_id and self.responsible_id.id != user_id:
                reader_name = self.env['res.users'].browse(user_id).name
                self.message_post(
                    body=_("%s ha leído el evento.") % reader_name,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )

            return True

        except Exception as e:
            _logger.error("Error en notify_event_read: %s", str(e))
            raise ValidationError(_('Error al registrar la lectura del evento: %s') % str(e))

    def _notify_creator_about_read(self, reader_id):
        """Notifica al creador que alguien ha leído el evento"""
        reader = self.env['res.users'].browse(reader_id)
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Evento leído',
                'message': f'{reader.name} ha leído el evento "{self.name}"',
                'type': 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
        self.env['bus.bus']._sendone(
            self.responsible_id.partner_id,
            'event_read_notification',
            notification
        )

    @api.depends('event_type', 'responsible_id')
    def _compute_is_admin_event(self):
        for record in self:
            record.is_admin_event = (
                    record.event_type == 'administrative' and
                    record.responsible_id.has_group('calendar_academy.group_academy_manager')
            )

    @api.depends('responsible_id', 'teacher_ids', 'course_ids')
    def _compute_is_teacher_event(self):
        for record in self:
            is_responsible = record.responsible_id == self.env.user
            is_teacher = self.env.user.id in record.teacher_ids.mapped('user_id').ids
            is_course_teacher = self.env.user.id in record.course_ids.mapped('teacher_ids.user_id').ids
            record.is_teacher_event = any([is_responsible, is_teacher, is_course_teacher])

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
        """Confirma el evento y crea la tarea si es necesario"""
        for record in self:
            # Primero cambiamos el estado
            record.write({'state': 'confirmed'})

            # Si es tipo tarea, creamos la tarea asociada
            if record.is_task and not record.task_id:
                # Validar campos requeridos
                if not record.subject_id:
                    raise ValidationError(_('Debe seleccionar una materia para la tarea'))
                if not record.course_ids:
                    raise ValidationError(_('Debe seleccionar al menos un curso'))

                # Obtener profesor
                teacher = self.env['academy.teacher'].search(
                    [('user_id', '=', record.responsible_id.id)], limit=1
                )
                if not teacher:
                    raise ValidationError(_('El responsable debe ser un profesor'))

                # Crear la tarea
                task_vals = {
                    'name': record.name,
                    'course_id': record.course_ids[0].id,
                    'subject_id': record.subject_id.id,
                    'teacher_id': teacher.id,
                    'description': record.description,
                    'deadline': record.end_date,
                    'available_from': record.start_date,
                    'max_score': record.max_score,
                    'weight': record.weight,
                    'submission_type': record.submission_type,
                    'allow_late_submission': record.allow_late_submission,
                    'late_submission_penalty': record.late_submission_penalty,
                    'attachment_ids': [(6, 0, record.attachment_ids.ids)],
                    'event_id': record.id,
                    'state': 'draft'
                }

                task = self.env['academy.task'].create(task_vals)
                record.task_id = task.id

                # Registrar en el chatter
                record.message_post(
                    body=_("Tarea creada: %s") % task.name,
                    message_type='notification'
                )

        return True

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

        # Si el usuario actual es un estudiante
        if self.env.user.has_group('calendar_academy.group_academy_student'):
            current_student = self.env['academy.student'].search([('user_id', '=', self.env.user.id)], limit=1)
            if current_student:
                defaults.update({
                    'student_creator_id': current_student.id,  # Falta este campo
                    'creator_type': 'student',
                    'event_type': 'academic',
                    'student_ids': [(4, current_student.id)]
                })
        # Si el usuario actual es un profesor
        elif self.env.user.has_group('calendar_academy.group_academy_teacher'):
            current_teacher = self.env['academy.teacher'].search([('user_id', '=', self.env.user.id)], limit=1)
            if current_teacher:
                defaults.update({
                    'teacher_ids': [(4, current_teacher.id)],
                    'responsible_id': self.env.user.id,
                    'event_type': 'academic'
                })
        # Si es administrador
        elif self.env.user.has_group('calendar_academy.group_academy_manager'):
            defaults.update({
                'event_type': 'administrative'
            })

        return defaults

    @api.onchange('reminder_type', 'event_type')
    def _onchange_type_student(self):
        """Asegura que los estudiantes no puedan cambiar el tipo de evento"""
        if self.env.user.has_group('calendar_academy.group_academy_student'):
            self.event_type = 'academic'

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir create para establecer el tipo de creador y relación"""
        for vals in vals_list:
            if self.env.user.has_group('calendar_academy.group_academy_student'):
                student = self.env['academy.student'].search([('user_id', '=', self.env.user.id)], limit=1)
                if student:
                    vals.update({
                        'creator_type': 'student',
                        'student_creator_id': student.id,
                        'event_type': 'academic'  # Forzar tipo académico
                    })
            elif self.env.user.has_group('calendar_academy.group_academy_teacher'):
                vals.update({
                    'creator_type': 'teacher'
                })
            else:
                vals.update({
                    'creator_type': 'admin'
                })
        return super().create(vals_list)

    def action_create_reminder(self):
        """Acción para crear nuevo recordatorio desde el dashboard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nuevo Recordatorio',
            'res_model': 'academy.event',
            'view_mode': 'form',
            'view_id': self.env.ref('calendar_academy.view_student_event_form').id,
            'target': 'new',
            'context': {
                'default_event_type': 'academic',
                'default_responsible_id': self.env.user.id,
                'default_reminder_type': 'note',
                'default_creator_type': 'student'
            }
        }

    @api.model
    def _get_student_domain(self):
        """Dominio para eventos visibles para estudiantes"""
        student = self.env['academy.student'].search([('user_id', '=', self.env.user.id)], limit=1)
        return [
            '|',
            ('student_creator_id', '=', student.id),
            '&',
            ('creator_type', '!=', 'student'),
            '|',
            ('student_ids', '=', student.id),
            '&',
            ('course_ids.student_ids', '=', student.id),
            ('creator_type', 'in', ['teacher', 'admin'])
        ]

    @api.model
    def _get_teacher_domain(self):
        """Dominio para eventos visibles para profesores"""
        teacher = self.env['academy.teacher'].search([('user_id', '=', self.env.user.id)], limit=1)
        return [
            '|',
            '&',
            ('creator_type', '=', 'teacher'),
            ('responsible_id', '=', self.env.user.id),
            '&',
            ('creator_type', '=', 'admin'),
            '|',
            ('teacher_ids', '=', teacher.id),
            ('course_ids.teacher_ids', '=', teacher.id)
        ]

    def check_user_has_read(self, user_id):
        """
        Verifica si un usuario específico ya ha leído el evento
        Args:
            user_id (int): ID del usuario a verificar
        Returns:
            bool: True si el usuario ya leyó el evento, False en caso contrario
        """
        self.ensure_one()

        read_status = self.env['academy.event.read.status'].sudo().search([
            ('event_id', '=', self.id),
            ('user_id', '=', user_id),
            ('read_status', '=', 'read')
        ], limit=1)

        return bool(read_status)

    # Push notification

    def action_notify_participants(self):
        """Notifica a los participantes cuando se les comparte un recordatorio"""
        self.ensure_one()

        # Obtener todos los usuarios participantes
        participant_partners = self.env['res.partner']

        # Añadir profesores
        if self.teacher_ids:
            participant_partners |= self.teacher_ids.mapped('user_id.partner_id')

        # Añadir estudiantes
        if self.student_ids:
            participant_partners |= self.student_ids.mapped('user_id.partner_id')

        # Excluir al creador de las notificaciones
        participant_partners = participant_partners.filtered(
            lambda p: p.user_ids and p.user_ids[0] != self.env.user
        )

        if participant_partners:
            # Crear el mensaje de notificación
            notification_msg = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nuevo Recordatorio Compartido'),
                    'message': _(
                        '%(user)s ha compartido contigo el recordatorio: %(event)s'
                    ) % {
                                   'user': self.env.user.name,
                                   'event': self.name
                               },
                    'type': 'info',
                    'sticky': True,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'academy.event',
                        'res_id': self.id,
                        'view_mode': 'form',
                    }
                }
            }

            # Enviar notificación a cada participante
            for partner in participant_partners:
                self.env['bus.bus']._sendone(
                    partner,
                    'new_reminder',
                    notification_msg
                )

                # Crear registro de actividad
                activity_type = self.env['mail.activity.type'].search([('category', '=', 'default')], limit=1)
                if activity_type:
                    self.env['mail.activity'].create({
                        'activity_type_id': activity_type.id,
                        'note': notification_msg['params']['message'],
                        'user_id': partner.user_ids[0].id,
                        'res_model_id': self.env['ir.model']._get('academy.event').id,
                        'res_id': self.id,
                        'summary': _('Nuevo Recordatorio Compartido')
                    })

    # Modificar el método create para enviar notificaciones al crear
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.action_notify_participants()
        return records

    # Modificar el método write para enviar notificaciones al modificar participantes
    def write(self, vals):
        result = super().write(vals)

        # Si se modificaron los participantes
        if any(field in vals for field in ['teacher_ids', 'student_ids']):
            self.action_notify_participants()

        return result

    def action_create_ai(self):
        """
        Método para manejar la creación de recordatorios por IA
        Por ahora solo devuelve una acción de notificación
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Función de IA en desarrollo',
                'type': 'info',
                'sticky': False,
            }
        }
    def _notify_event_creation(self):
        """Enviar notificación cuando se crea un evento"""
        _logger.info(f"Starting event creation notification for event ID: {self.id}")
        
        try:
            notification = self.env['fcm.notification']
            
            # Obtener los user_ids de los participantes
            participant_user_ids = []
            if self.teacher_ids:
                participant_user_ids.extend(self.teacher_ids.mapped('user_id.id'))
            if self.student_ids:
                participant_user_ids.extend(self.student_ids.mapped('user_id.id'))
            if self.course_ids:
                participant_user_ids.extend(self.course_ids.mapped('student_ids.user_id.id'))
                participant_user_ids.extend(self.course_ids.mapped('teacher_ids.user_id.id'))
            
            # Eliminar duplicados y valores False
            participant_user_ids = list(set(filter(None, participant_user_ids)))
            
            _logger.info(f"Participant user IDs: {participant_user_ids}")
            
            # Obtener los tokens de los dispositivos de los participantes
            devices = self.env['fcm.device'].search([
                ('user_id', 'in', participant_user_ids),
                ('active', '=', True)
            ])
            
            if not devices:
                _logger.info("No active devices found for participants")
                return False
                
            _logger.info(f"Found {len(devices)} active devices for participants")
            
            # Prepare notification data
            data = {
                'event_id': str(self.id),
                'event_type': self.event_type if self.event_type else '',
                'reminder_type': self.reminder_type if self.reminder_type else '',
                'start_date': str(self.start_date) if self.start_date else '',
                'priority': str(self.priority) if hasattr(self, 'priority') else '',
            }
            
            title = f"Nuevo {dict(self._fields['reminder_type'].selection).get(self.reminder_type, '')}"
            body = f"{self.name}\nFecha: {self.start_date.strftime('%d/%m/%Y %H:%M') if self.start_date else ''}"
            
            # Send notification only to participant devices
            result = notification.send_notification(title, body, data)
            return result
            
        except Exception as e:
            _logger.error(f"Error in _notify_event_creation: {str(e)}")
            return False

    @api.model_create_multi
    def create(self, vals_list):
        """Create events with notification"""
        _logger.info(f"Creating {len(vals_list)} new events")
        
        try:
            records = super().create(vals_list)
            _logger.info(f"Successfully created {len(records)} events")
            
            for record in records:
                _logger.info(f"Processing notifications for event ID: {record.id}")
                record._notify_event_creation()
                
            return records
            
        except Exception as e:
            _logger.error(f"Error in create method: {str(e)}")
            _logger.error(f"Exception type: {type(e)}")
            _logger.error(f"Exception args: {e.args}")
            raise