# -*- coding: utf-8 -*-
# from odoo import http


# class CalendarAcademy(http.Controller):
#     @http.route('/calendar_academy/calendar_academy', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/calendar_academy/calendar_academy/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('calendar_academy.listing', {
#             'root': '/calendar_academy/calendar_academy',
#             'objects': http.request.env['calendar_academy.calendar_academy'].search([]),
#         })

#     @http.route('/calendar_academy/calendar_academy/objects/<model("calendar_academy.calendar_academy"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('calendar_academy.object', {
#             'object': obj
#         })

