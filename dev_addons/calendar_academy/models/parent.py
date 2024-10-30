from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Parent(models.Model):
    _name = 'academy.parent'
    _description = 'Padre/Representante'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Nombre Completo', required=True, tracking=True)
    identification = fields.Char(string='Identificación', required=True, tracking=True)

    # Información de contacto
    email = fields.Char(string='Correo Electrónico', required=True)
    phone = fields.Char(string='Teléfono Principal')
    mobile = fields.Char(string='Teléfono Móvil')
    address = fields.Text(string='Dirección')

    # Información laboral
    occupation = fields.Char(string='Ocupación')
    workplace = fields.Char(string='Lugar de Trabajo')
    work_phone = fields.Char(string='Teléfono del Trabajo')

    # Relaciones
    student_ids = fields.One2many('academy.student', 'parent_id', string='Estudiantes')
    user_id = fields.Many2one('res.users', string='Usuario Relacionado')

    # Contacto de emergencia
    emergency_contact = fields.Char(string='Contacto de Emergencia')
    emergency_phone = fields.Char(string='Teléfono de Emergencia')
    emergency_relation = fields.Char(string='Relación con Contacto de Emergencia')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_identification',
         'UNIQUE(identification)',
         'Ya existe un representante con esta identificación')
    ]

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and '@' not in record.email:
                raise ValidationError(_('Por favor ingrese un correo electrónico válido'))

    def action_create_user(self):
        """Crea un usuario del portal para el padre"""
        for record in self:
            if not record.user_id:
                user = self.env['res.users'].create({
                    'name': record.name,
                    'login': record.email,
                    'email': record.email,
                    'password': record.identification,
                    'groups_id': [(6, 0, [self.env.ref('calendar_academy.group_academy_parent').id])]
                })
                record.user_id = user.id

    def action_view_students(self):
        self.ensure_one()
        return {
            'name': _('Estudiantes'),
            'view_mode': 'tree,form',
            'res_model': 'academy.student',
            'type': 'ir.actions.act_window',
            'domain': [('parent_id', '=', self.id)]
        }