from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='calendar_academy.openai_api_key'
    )
    openai_model = fields.Selection([
        ('gpt-4', 'GPT-4'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
    ], string='OpenAI Model',
        default='gpt-3.5-turbo',
        config_parameter='calendar_academy.openai_model'
    )