# -*- coding: utf-8 -*-

from odoo import models, fields, api


# class calendar_academy(models.Model):
#     _name = 'calendar_academy.calendar_academy'
#     _description = 'calendar_academy.calendar_academy'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

class materia(models.Model):
    _name = 'calendar_academy.materia'
    _description = 'calendar_academy.materia'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Introduzca el nombre de la materia',
        readonly=False
    )
    descripcion = fields.Text()
    curso = fields.Many2one('calendar_academy.curso', ondelete='cascade', help='Curso relacionado')

class curso(models.Model):
    _name = 'calendar_academy.curso'
    _description = 'calendar_academy.curso'

    name = fields.Char(
        string='Nombre',
        unique=True,
        help='Introduzca el nombre del curso',
        readonly=False
    )
    materias = fields.One2many(string='Materias', comodel_name='calendar_academy.materia', inverse_name='curso')