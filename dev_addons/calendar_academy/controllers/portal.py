from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.osv.expression import OR


class AcademyPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        student = request.env['academy.student'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if student:
            values['student'] = student
            if 'grade_count' in counters:
                values['grade_count'] = request.env['academy.grade.line'].sudo().search_count([
                    ('student_id', '=', student.id)
                ])
            if 'task_count' in counters:
                values['task_count'] = request.env['academy.task.submission'].sudo().search_count([
                    ('student_id', '=', student.id)
                ])
            if 'attendance_count' in counters:
                values['attendance_count'] = request.env['academy.attendance.line'].sudo().search_count([
                    ('student_id', '=', student.id)
                ])
        return values

    @http.route(['/my/academics'], type='http', auth="user", website=True)
    def portal_my_academics(self, **kw):
        values = self._prepare_portal_layout_values()
        student = request.env['academy.student'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not student:
            return request.redirect('/my')

        values.update({
            'student': student,
            'current_course': student.current_course_id,
            'page_name': 'academics'
        })
        return request.render("calendar_academy.portal_my_academics", values)

    @http.route(['/my/grades'], type='http', auth="user", website=True)
    def portal_my_grades(self, **kw):
        values = self._prepare_portal_layout_values()
        student = request.env['academy.student'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not student:
            return request.redirect('/my')

        grades = request.env['academy.grade.line'].sudo().search([
            ('student_id', '=', student.id)
        ])

        values.update({
            'grades': grades,
            'page_name': 'grades'
        })
        return request.render("calendar_academy.portal_my_grades", values)

    @http.route(['/my/tasks'], type='http', auth="user", website=True)
    def portal_my_tasks(self, **kw):
        values = self._prepare_portal_layout_values()
        student = request.env['academy.student'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not student:
            return request.redirect('/my')

        tasks = request.env['academy.task.submission'].sudo().search([
            ('student_id', '=', student.id)
        ])

        values.update({
            'tasks': tasks,
            'page_name': 'tasks'
        })
        return request.render("calendar_academy.portal_my_tasks", values)

    @http.route(['/my/attendance'], type='http', auth="user", website=True)
    def portal_my_attendance(self, **kw):
        values = self._prepare_portal_layout_values()
        student = request.env['academy.student'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not student:
            return request.redirect('/my')

        attendance = request.env['academy.attendance.line'].sudo().search([
            ('student_id', '=', student.id)
        ])

        values.update({
            'attendance': attendance,
            'page_name': 'attendance'
        })
        return request.render("calendar_academy.portal_my_attendance", values)