from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime


class TaskSubmission(models.Model):
    _name = 'academy.task.submission'
    _description = 'Entrega de Tarea'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'task_id'

    task_id = fields.Many2one(
        'academy.task',
        string='Tarea',
        required=True,
        ondelete='cascade'
    )
    student_id = fields.Many2one(
        'academy.student',
        string='Estudiante',
        required=True
    )
    deadline = fields.Datetime(
        string='Fecha Límite',
        required=True
    )
    submission_date = fields.Datetime(
        string='Fecha de Entrega',
        readonly=True
    )

    # Contenido de la entrega
    content = fields.Html(
        string='Contenido',
        sanitize=True
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'submission_attachment_rel',
        'submission_id',
        'attachment_id',
        string='Archivos Adjuntos'
    )

    # Calificación
    score = fields.Float(
        string='Calificación',
        tracking=True
    )
    max_score = fields.Float(
        related='task_id.max_score',
        string='Calificación Máxima'
    )
    feedback = fields.Text(
        string='Retroalimentación',
        tracking=True
    )

    # Control de estado
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('submitted', 'Entregada'),
        ('graded', 'Calificada'),
        ('late', 'Entrega Tardía')
    ], string='Estado', default='pending', tracking=True)

    is_late = fields.Boolean(
        string='¿Entrega Tardía?',
        compute='_compute_is_late',
        store=True
    )

    @api.depends('submission_date', 'deadline')
    def _compute_is_late(self):
        for record in self:
            if record.submission_date and record.deadline:
                record.is_late = record.submission_date > record.deadline
            else:
                record.is_late = False

    @api.constrains('score', 'max_score')
    def _check_score(self):
        for record in self:
            if record.score < 0:
                raise ValidationError(_('La calificación no puede ser negativa'))
            if record.score > record.max_score:
                raise ValidationError(_('La calificación no puede ser mayor que la máxima permitida'))

    def action_submit(self):
        """Registra la entrega de la tarea"""
        self.ensure_one()
        if not (self.content or self.attachment_ids):
            raise ValidationError(_('Debe proporcionar contenido o archivos adjuntos'))

        values = {
            'state': 'late' if self.is_late else 'submitted',
            'submission_date': fields.Datetime.now()
        }

        if self.is_late and not self.task_id.allow_late_submission:
            raise ValidationError(_('No se permiten entregas tardías para esta tarea'))

        return self.write(values)

    def action_grade(self):
        """Califica la entrega"""
        self.ensure_one()
        if not self.score:
            raise ValidationError(_('Debe asignar una calificación'))

        # Aplicar penalización por retraso si corresponde
        if self.is_late and self.task_id.late_submission_penalty > 0:
            penalty = (self.task_id.late_submission_penalty / 100) * self.score
            self.score = max(0, self.score - penalty)

        return self.write({'state': 'graded'})

    def action_reset(self):
        """Devuelve la entrega a estado pendiente"""
        return self.write({
            'state': 'pending',
            'submission_date': False,
            'score': 0,
            'feedback': False
        })