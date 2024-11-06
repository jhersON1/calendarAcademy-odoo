from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class Enrollment(models.Model):
    _name = 'academy.enrollment'
    _description = 'Matrícula'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Número de Matrícula', readonly=True, copy=False, default='Nuevo')
    student_id = fields.Many2one('academy.student', string='Estudiante', required=True, tracking=True)
    course_id = fields.Many2one('academy.course', string='Curso', required=True, tracking=True)
    period_id = fields.Many2one(related='course_id.period_id', store=True)
    enrollment_date = fields.Date(string='Fecha de Matrícula', default=fields.Date.today, required=True)

    # Información del representante
    parent_id = fields.Many2one('academy.parent', string='Representante', required=True)
    parent_relationship = fields.Selection([
        ('father', 'Padre'),
        ('mother', 'Madre'),
        ('guardian', 'Tutor Legal'),
        ('other', 'Otro')
    ], string='Parentesco', required=True)

    # Documentos requeridos
    document_ids = fields.One2many('academy.enrollment.document', 'enrollment_id', string='Documentos')
    documents_complete = fields.Boolean(compute='_compute_documents_complete', store=True)

    # Estado de la matrícula
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('submitted', 'Enviada'),
        ('confirmed', 'Confirmada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_student_period',
         'UNIQUE(student_id, period_id)',
         'El estudiante ya está matriculado en este período académico')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('academy.enrollment') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('document_ids.is_submitted')
    def _compute_documents_complete(self):
        for record in self:
            record.documents_complete = all(record.document_ids.mapped('is_submitted'))

    @api.constrains('enrollment_date')
    def _check_enrollment_date(self):
        for record in self:
            if record.enrollment_date and record.period_id:
                if record.enrollment_date < record.period_id.enrollment_start_date or \
                        record.enrollment_date > record.period_id.enrollment_end_date:
                    raise ValidationError(_('La fecha de matrícula debe estar dentro del período de matrículas'))

    # @api.constrains('enrollment_date')
    # def _check_enrollment_date(self):
    #     for record in self:
    #         if record.enrollment_date > fields.Date.today():
    #             raise ValidationError(_('La fecha de matrícula no puede ser futura'))
    #         if record.period_id:
    #             if record.enrollment_date < record.period_id.start_date or \
    #                     record.enrollment_date > record.period_id.end_date:
    #                 raise ValidationError(_('La fecha de matrícula debe estar dentro del período académico'))

    def action_submit(self):
        self.ensure_one()
        if not self.documents_complete:
            raise ValidationError(_('Debe subir todos los documentos requeridos'))
        self.write({'state': 'submitted'})

    def action_confirm(self):
        self.ensure_one()
        # Agregar estudiante al curso
        self.course_id.write({
            'student_ids': [(4, self.student_id.id)]
        })
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.ensure_one()
        # Remover estudiante del curso si estaba confirmado
        if self.state == 'confirmed':
            self.course_id.write({
                'student_ids': [(3, self.student_id.id)]
            })
        self.write({'state': 'cancelled'})


class EnrollmentDocument(models.Model):
    _name = 'academy.enrollment.document'
    _description = 'Documento de Matrícula'

    name = fields.Char(string='Nombre del Documento', required=True)
    enrollment_id = fields.Many2one('academy.enrollment', string='Matrícula', required=True)
    document_type = fields.Selection([
        ('id', 'Documento de Identidad'),
        ('photo', 'Fotografía'),
        ('certificate', 'Certificado'),
        ('report', 'Libreta de Calificaciones'),
        ('other', 'Otro')
    ], string='Tipo de Documento', required=True)
    is_required = fields.Boolean(string='Requerido', default=True)
    is_submitted = fields.Boolean(string='Entregado', default=False)
    submission_date = fields.Date(string='Fecha de Entrega')
    notes = fields.Text(string='Observaciones')
    attachment_ids = fields.Many2many('ir.attachment', string='Archivos Adjuntos')
