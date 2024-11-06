# -*- coding: utf-8 -*-
{
    'name': "calendarAcademy",

    'summary': "Sistema de gestión de tareas académicas",

    'description': """
        Sistema completo para la gestión de una academia:
        - Gestión de períodos académicos
        - Gestión de cursos
        - Gestión de estudiantes
        - Gestión de profesores
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Education',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'portal', 'website'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # Vistas
        'views/period_views.xml',
        'views/level_views.xml',
        'views/parallel_views.xml',
        'views/course_views.xml',
        'views/subject_views.xml',
        'views/student_views.xml',
        'views/teacher_views.xml',
        'views/parent_views.xml',
        'views/enrollment_views.xml',
        'views/attendance_views.xml',
        'views/grade_views.xml',
        'views/schedule_views.xml',

        'views/portal_templates.xml',

        # Data
        'data/sequence.xml',
        'data/mail_template.xml',
        'data/reminder_cron.xml',
        'data/reminder_mail_templates.xml',

        # Communication
        'views/communication_views.xml',
        'views/communication_template_views.xml',

        # Task
        'views/task_views.xml',
        'views/submission_views.xml',

        # Event
        'views/academy_event_views.xml',

        # Dashboard
        'views/dashboard/academy_dashboard.xml',

        # Menu
        'views/menu_views.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
}
