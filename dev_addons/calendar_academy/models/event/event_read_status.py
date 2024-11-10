from odoo import models, fields, api


class EventReadStatus(models.Model):
    _name = 'academy.event.read.status'
    _description = 'Estado de Lectura de Evento'
    _rec_name = 'event_id'

    event_id = fields.Many2one(
        'academy.event',
        string='Evento',
        required=True,
        ondelete='cascade'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True
    )
    read_date = fields.Datetime(
        string='Fecha de Lectura',
        readonly=True
    )
    read_status = fields.Selection([
        ('unread', 'No Leído'),
        ('read', 'Leído')
    ], string='Estado',
        default='unread',
        required=True
    )

    _sql_constraints = [
        ('unique_event_user',
         'UNIQUE(event_id, user_id)',
         'Ya existe un registro de lectura para este usuario en este evento')
    ]

    def mark_as_read(self, device_info=None):
        self.ensure_one()
        if self.read_status == 'unread':
            self.write({
                'read_status': 'read',
                'read_date': fields.Datetime.now(),
            })