# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Communication(models.Model):
    _name = 'academy.communication'
    _description = 'Comunicado Académico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

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
    date = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    type = fields.Selection([
        ('institutional', 'Institucional'),
        ('course', 'Curso'),
        ('academic', 'Académico'),
        ('administrative', 'Administrativo')
    ], string='Tipo', required=True, tracking=True, default='course')

    content = fields.Html(
        string='Contenido',
        required=True,
        sanitize=True,
        sanitize_tags=True,
        sanitize_attributes=True
    )
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Importante'),
        ('2', 'Urgente'),
    ], string='Prioridad', default='0', tracking=True)

    # Destinatarios
    course_ids = fields.Many2many(
        'academy.course',
        string='Cursos'
    )
    student_ids = fields.Many2many(
        'academy.student',
        string='Estudiantes'
    )
    teacher_ids = fields.Many2many(
        'academy.teacher',
        string='Profesores'
    )
    parent_ids = fields.Many2many(
        'academy.parent',
        string='Representantes'
    )

    # Estado y seguimiento
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('archived', 'Archivado')
    ], string='Estado', default='draft', tracking=True)

    author_id = fields.Many2one(
        'res.users',
        string='Autor',
        default=lambda self: self.env.user,
        readonly=True
    )
    read_count = fields.Integer(
        compute='_compute_read_count',
        string='Leído por'
    )
    read_status_ids = fields.One2many(
        'academy.communication.status',
        'communication_id',
        string='Estados de Lectura'
    )
    require_confirmation = fields.Boolean(
        string='Requiere Confirmación',
        default=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nuevo') == 'Nuevo':
                vals['reference'] = self.env['ir.sequence'].next_by_code('academy.communication')
        return super().create(vals_list)

    def action_send(self):
        self.ensure_one()
        if not (self.course_ids or self.student_ids or self.teacher_ids or self.parent_ids):
            raise ValidationError(_('Debe seleccionar al menos un destinatario'))

        # Crear registros de estado de lectura para cada destinatario
        recipients = self._get_all_recipients()
        status_vals = []
        for recipient in recipients:
            status_vals.append({
                'communication_id': self.id,
                'user_id': recipient.user_id.id if recipient.user_id else False,
                'recipient_model': recipient._name,
                'recipient_id': recipient.id,
            })

        self.env['academy.communication.status'].create(status_vals)

        # Enviar notificaciones
        self._send_notifications(recipients)

        self.write({'state': 'sent'})

    def action_archive(self):
        return self.write({'state': 'archived'})

    def action_draft(self):
        return self.write({'state': 'draft'})

    @api.depends('read_status_ids.is_read')
    def _compute_read_count(self):
        for record in self:
            record.read_count = len(record.read_status_ids.filtered('is_read'))

    def _get_all_recipients(self):
        """Obtiene todos los destinatarios únicos del comunicado"""
        self.ensure_one()
        recipients = self.env['res.partner']

        # Agregar estudiantes directos y de cursos
        students = self.student_ids | self.course_ids.mapped('student_ids')
        recipients |= students.mapped('user_id.partner_id')

        # Agregar profesores
        recipients |= self.teacher_ids.mapped('user_id.partner_id')

        # Agregar representantes
        recipients |= self.parent_ids.mapped('user_id.partner_id')

        return recipients.filtered(lambda r: r.user_ids)

    def _send_notifications(self, recipients):
        """Envía notificaciones a los destinatarios"""
        self.ensure_one()
        if not recipients:
            return

        # Preparar valores para la notificación
        notification_type = 'email' if self.priority == '2' else 'inbox'
        subject = f"[{dict(self._fields['type'].selection).get(self.type)}] {self.name}"

        # Crear notificación
        self.env['mail.message'].create({
            'model': self._name,
            'res_id': self.id,
            'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_note').id,
            'subject': subject,
            'body': self.content,
            'author_id': self.author_id.partner_id.id,
            'notification_ids': [(0, 0, {
                'res_partner_id': recipient.id,
                'notification_type': notification_type,
            }) for recipient in recipients],
        })


class CommunicationStatus(models.Model):
    _name = 'academy.communication.status'
    _description = 'Estado de Lectura de Comunicado'
    _rec_name = 'communication_id'

    communication_id = fields.Many2one(
        'academy.communication',
        string='Comunicado',
        required=True,
        ondelete='cascade'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario'
    )
    recipient_model = fields.Char(
        string='Tipo de Destinatario'
    )
    recipient_id = fields.Integer(
        string='ID del Destinatario'
    )
    is_read = fields.Boolean(
        string='Leído',
        default=False
    )
    read_date = fields.Datetime(
        string='Fecha de Lectura'
    )
    confirmation_date = fields.Datetime(
        string='Fecha de Confirmación'
    )

    def mark_as_read(self):
        self.write({
            'is_read': True,
            'read_date': fields.Datetime.now()
        })

    def confirm_reading(self):
        self.write({
            'confirmation_date': fields.Datetime.now()
        })


class CommunicationTemplate(models.Model):
    _name = 'academy.communication.template'
    _description = 'Plantilla de Comunicado'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True
    )
    type = fields.Selection([
        ('institutional', 'Institucional'),
        ('course', 'Curso'),
        ('academic', 'Académico'),
        ('administrative', 'Administrativo')
    ], string='Tipo', required=True)
    content = fields.Html(
        string='Contenido',
        required=True,
        sanitize=True,
        sanitize_tags=True,
        sanitize_attributes=True
    )
    active = fields.Boolean(
        default=True
    )

    def action_use_template(self):
        """Crea un nuevo comunicado usando esta plantilla"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Comunicado'),
            'res_model': 'academy.communication',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': self.name,
                'default_type': self.type,
                'default_content': self.content,
            }
        }