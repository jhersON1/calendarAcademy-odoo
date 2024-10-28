# # -*- coding: utf-8 -*-
#
# from odoo import models, fields, api
#
#
# class calendar_academy(models.Model):
#     _name = 'calendar_academy.calendar_academy'
#     _description = 'calendar_academy.calendar_academy'
#
#     period = fields.Char()
# #     value = fields.Integer()
# #     value2 = fields.Float(compute="_value_pc", store=True)
# #     description = fields.Text()
# #
# #     @api.depends('value')
# #     def _value_pc(self):
# #         for record in self:
# #             record.value2 = float(record.value) / 100
#

# -*- coding: utf-8 -*-

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class calendar_academy(models.Model):
    _name = 'calendar_academy.calendar_academy'
    _description = 'calendar_academy.calendar_academy'
    _order = 'start_date desc'

    name = fields.Char(string='Nombre del Período', compute='_compute_name', store=True)
    start_date = fields.Date(
        string='Fecha de Inicio',
        required=True,
        default=fields.Date.context_today
    )
    end_date = fields.Date(
        string='Fecha de Fin',
        required=True,
        default=lambda self: fields.Date.context_today(self) + relativedelta(months=4)
    )
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', required=True)

    @api.depends('start_date', 'end_date')
    def _compute_name(self):
        for record in self:
            if record.start_date and record.end_date:
                year = record.start_date.year
                month = record.start_date.month
                if month <= 4:
                    period = '1'
                elif month <= 8:
                    period = '2'
                else:
                    period = '3'
                record.name = f'Período {year}-{period}'
            else:
                record.name = 'Nuevo Período'

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date:
            self.end_date = self.start_date + relativedelta(months=12)