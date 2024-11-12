from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AcademicTask(models.Model):
    _name = 'academy.task'
    _description = 'Tarea Académica'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline, id desc'

    name = fields.Char(
        string='Título',
        required=True,
        tracking=True
    )
    reference = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        default='Nuevo'
    )
    description = fields.Html(
        string='Descripción',
        required=True,
        sanitize=True
    )

    # Relaciones académicas
    course_id = fields.Many2one(
        'academy.course',
        string='Curso',
        required=True,
        tracking=True
    )
    subject_id = fields.Many2one(
        'academy.subject',
        string='Materia',
        required=True,
        tracking=True
    )
    teacher_id = fields.Many2one(
        'academy.teacher',
        string='Profesor',
        required=True,
        default=lambda self: self._get_current_teacher(),
        tracking=True
    )

    # Fechas y plazos
    assign_date = fields.Datetime(
        string='Fecha de Asignación',
        default=fields.Datetime.now,
        required=True
    )
    deadline = fields.Datetime(
        string='Fecha de Entrega',
        required=True,
        tracking=True
    )
    available_from = fields.Datetime(
        string='Disponible Desde',
        default=fields.Datetime.now
    )

    # Configuración de la tarea
    max_score = fields.Float(
        string='Puntuación Máxima',
        default=10.0,
        required=True
    )
    weight = fields.Float(
        string='Peso en Calificación (%)',
        default=100.0,
        required=True
    )
    submission_type = fields.Selection([
        ('online', 'En línea'),
        ('physical', 'Física'),
        ('both', 'Ambas')
    ], string='Tipo de Entrega', required=True, default='online')

    allow_late_submission = fields.Boolean(
        string='Permitir Entregas Tardías',
        default=False
    )
    late_submission_penalty = fields.Float(
        string='Penalización por Retraso (%)',
        default=0
    )

    # Archivos adjuntos
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'task_attachment_rel',
        'task_id',
        'attachment_id',
        string='Archivos Adjuntos'
    )

    # Entregas
    submission_ids = fields.One2many(
        'academy.task.submission',
        'task_id',
        string='Entregas'
    )
    submission_count = fields.Integer(
        compute='_compute_submission_stats',
        string='Total Entregas'
    )
    graded_count = fields.Integer(
        compute='_compute_submission_stats',
        string='Entregas Calificadas'
    )
    pending_count = fields.Integer(
        compute='_compute_submission_stats',
        string='Entregas Pendientes'
    )

    # Estados

    # Agregar campo para relación con evento
    event_id = fields.Many2one(
        'academy.event',
        string='Evento Relacionado',
        tracking=True
    )

    # Modificar estados para simplificar
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('published', 'Publicada'),
        ('closed', 'Cerrada')
    ], string='Estado',
        default='draft',
        tracking=True
    )

    def action_publish(self):
        """Publicar tarea y notificar"""
        self.ensure_one()
        if not self.course_id.student_ids:
            raise ValidationError(_('No hay estudiantes en el curso'))

        # Crear entregas para cada estudiante
        for student in self.course_id.student_ids:
            self.env['academy.task.submission'].create({
                'task_id': self.id,
                'student_id': student.id,
                'deadline': self.deadline
            })

        self.write({'state': 'published'})
        self._notify_students()

        # Actualizar evento relacionado si existe
        if self.event_id:
            self.event_id.message_post(
                body=_("Tarea publicada y notificada a los estudiantes"),
                message_type='notification'
            )

    def action_close(self):
        """Cerrar tarea"""
        return self.write({'state': 'closed'})

    @api.model
    def _get_current_teacher(self):
        """Obtiene el profesor basado en el usuario actual"""
        teacher = self.env['academy.teacher'].search([('user_id', '=', self.env.user.id)], limit=1)
        return teacher.id if teacher else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nuevo') == 'Nuevo':
                vals['reference'] = self.env['ir.sequence'].next_by_code('academy.task') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('submission_ids', 'submission_ids.state')
    def _compute_submission_stats(self):
        for record in self:
            submissions = record.submission_ids
            record.submission_count = len(submissions)
            record.graded_count = len(submissions.filtered(lambda s: s.state == 'graded'))
            record.pending_count = len(submissions.filtered(lambda s: s.state == 'submitted'))

    @api.constrains('deadline', 'available_from')
    def _check_dates(self):
        for record in self:
            if record.deadline and record.available_from and record.deadline < record.available_from:
                raise ValidationError(_('La fecha de entrega debe ser posterior a la fecha de inicio'))

    @api.constrains('weight')
    def _check_weight(self):
        for record in self:
            if record.weight < 0 or record.weight > 100:
                raise ValidationError(_('El peso debe estar entre 0 y 100'))

    def action_publish(self):
        """Publica la tarea y crea las entregas para cada estudiante"""
        self.ensure_one()
        if not self.course_id.student_ids:
            raise ValidationError(_('No hay estudiantes en el curso'))

        # Crear entregas para cada estudiante
        for student in self.course_id.student_ids:
            self.env['academy.task.submission'].create({
                'task_id': self.id,
                'student_id': student.id,
                'deadline': self.deadline
            })

        self.write({'state': 'published'})
        self._notify_students()

    def action_close(self):
        """Cierra la tarea e integra las calificaciones"""
        self.ensure_one()
        # Asegurarse que todas las entregas estén calificadas
        pending = self.submission_ids.filtered(lambda s: s.state == 'submitted')
        if pending:
            raise ValidationError(_('Hay entregas pendientes de calificar'))

        self.write({'state': 'closed'})
        self._integrate_grades()

    def action_reopen(self):
        """Reabre una tarea cerrada"""
        return self.write({'state': 'in_progress'})

    def action_archive(self):
        """Archiva la tarea"""
        return self.write({'state': 'archived'})

    def _notify_students(self):
        """Notifica a los estudiantes sobre la nueva tarea"""
        template = self.env.ref('calendar_academy.email_template_new_task', raise_if_not_found=False)

        if not template:
            # Si la plantilla no existe, solo registramos en el chatter
            self.message_post(
                body=_("Tarea publicada: %s") % self.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            return True

        for student in self.course_id.student_ids:
            if student.email:  # Solo enviar si tiene email
                template.send_mail(self.id, force_send=True, email_values={
                    'email_to': student.email
                })

        return True

    def _integrate_grades(self):
        """Integra las calificaciones de la tarea con el sistema de calificaciones"""
        Grade = self.env['academy.grade']
        grade_vals = {
            'course_id': self.course_id.id,
            'subject_id': self.subject_id.id,
            'teacher_id': self.teacher_id.id,
            'evaluation_type': 'task',
            'evaluation_date': fields.Date.today(),
            'max_grade': self.max_score,
            'weight': self.weight,
            'name': f"Tarea: {self.name}"
        }
        grade = Grade.create(grade_vals)

        # Crear líneas de calificación
        for submission in self.submission_ids:
            self.env['academy.grade.line'].create({
                'grade_id': grade.id,
                'student_id': submission.student_id.id,
                'grade': submission.score if submission.state == 'graded' else 0
            })

    def action_view_submissions(self):
        """Abre la vista de entregas relacionadas con esta tarea"""
        self.ensure_one()
        return {
            'name': _('Entregas'),
            'view_mode': 'list,form',
            'res_model': 'academy.task.submission',
            'type': 'ir.actions.act_window',
            'domain': [('task_id', '=', self.id)],
            'context': {
                'default_task_id': self.id,
                'search_default_pending': 1
            }
        }

    # En models/task.py

    def action_view_event(self):
        """Abre el formulario del evento relacionado"""
        self.ensure_one()
        if not self.event_id:
            return

        return {
            'name': _('Evento Relacionado'),
            'type': 'ir.actions.act_window',
            'res_model': 'academy.event',
            'res_id': self.event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
