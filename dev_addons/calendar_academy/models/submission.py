from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import openai

import logging

_logger = logging.getLogger(__name__)


class TaskSubmission(models.Model):
    _name = 'academy.task.submission'
    _description = 'Entrega de Tarea'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'task_id'

    task_id = fields.Many2one(
        'academy.task',
        string='Tarea',
        required=True,
        ondelete='cascade'
    )
    student_id = fields.Many2one(
        'academy.student',
        string='Estudiante',
        required=True
    )
    deadline = fields.Datetime(
        string='Fecha Límite',
        required=True
    )
    submission_date = fields.Datetime(
        string='Fecha de Entrega',
        readonly=True
    )

    # Contenido de la entrega
    content = fields.Html(
        string='Contenido',
        sanitize=True
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'submission_attachment_rel',
        'submission_id',
        'attachment_id',
        string='Archivos Adjuntos'
    )

    # Calificación
    score = fields.Float(
        string='Calificación',
        tracking=True
    )
    max_score = fields.Float(
        related='task_id.max_score',
        string='Calificación Máxima'
    )
    feedback = fields.Text(
        string='Retroalimentación',
        tracking=True
    )

    # Control de estado
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('submitted', 'Entregada'),
        ('graded', 'Calificada'),
        ('late', 'Entrega Tardía')
    ], string='Estado', default='pending', tracking=True)

    is_late = fields.Boolean(
        string='¿Entrega Tardía?',
        compute='_compute_is_late',
        store=True
    )

    ai_feedback = fields.Text(string='Retroalimentación IA', readonly=True)
    ai_suggested_score = fields.Float(string='Puntuación Sugerida IA', readonly=True)
    ai_analysis_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('analyzing', 'Analizando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido')
    ], string='Estado Análisis IA', default='pending')

    def action_analyze_with_ai(self):
        """Analiza la tarea usando IA"""
        self.ensure_one()
        if self.state not in ['submitted', 'late']:
            raise ValidationError(_('Solo se pueden analizar tareas entregadas'))

        api_key = self.env['ir.config_parameter'].sudo().get_param('calendar_academy.openai_api_key')
        if not api_key:
            raise ValidationError(_('La clave API de OpenAI no está configurada'))

        model = self.env['ir.config_parameter'].sudo().get_param('calendar_academy.openai_model', 'gpt-3.5-turbo')

        try:
            self.ai_analysis_state = 'analyzing'
            client = openai.OpenAI(api_key=api_key)

            # Preparar el contexto de la tarea
            task_context = f"""
                Tarea: {self.task_id.name}
                Descripción: {self.task_id.description}
                Puntuación máxima: {self.task_id.max_score}
                """

            # Preparar el contenido de la entrega
            submission_content = self.content or "No hay contenido textual"

            # Procesar archivos adjuntos
            attachment_texts = []
            for attachment in self.attachment_ids:
                try:
                    # Intentar decodificar el contenido si es texto
                    if attachment.mimetype.startswith('text/'):
                        attachment_texts.append(f"Contenido de {attachment.name}:\n{attachment.raw.decode()}")
                    else:
                        attachment_texts.append(f"Archivo adjunto: {attachment.name} (tipo: {attachment.mimetype})")
                except:
                    attachment_texts.append(f"Archivo adjunto: {attachment.name} (no procesable)")

            # Crear el prompt para OpenAI
            prompt = f"""Actúa como un profesor experto evaluando esta tarea.

                CONTEXTO DE LA TAREA:
                {task_context}

                ENTREGA DEL ESTUDIANTE:
                Contenido textual:
                {submission_content}

                Archivos adjuntos:
                {'\n'.join(attachment_texts)}

                Por favor, proporciona:
                1. Una evaluación detallada de la entrega
                2. Retroalimentación constructiva para el estudiante
                3. Una puntuación sugerida sobre {self.task_id.max_score} puntos
                4. Justificación de la puntuación

                Estructura tu respuesta así:
                <EVALUACION>tu evaluación detallada</EVALUACION>
                <RETROALIMENTACION>tus comentarios constructivos</RETROALIMENTACION>
                <PUNTUACION>número sugerido</PUNTUACION>
                <JUSTIFICACION>justificación de la puntuación</JUSTIFICACION>
                """

            # Llamar a la API de OpenAI
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            # Procesar la respuesta
            ai_response = response.choices[0].message.content

            # Extraer las secciones usando un método auxiliar
            evaluacion = self._extract_section(ai_response, "EVALUACION")
            retroalimentacion = self._extract_section(ai_response, "RETROALIMENTACION")
            puntuacion = self._extract_section(ai_response, "PUNTUACION")
            justificacion = self._extract_section(ai_response, "JUSTIFICACION")

            # Formatear el feedback final
            feedback_final = f"""
                EVALUACIÓN DETALLADA:
                {evaluacion}

                RETROALIMENTACIÓN:
                {retroalimentacion}

                JUSTIFICACIÓN DE LA PUNTUACIÓN:
                {justificacion}
                """

            # Actualizar el registro
            self.write({
                'ai_feedback': feedback_final,
                'ai_suggested_score': float(puntuacion.strip() or 0),
                'ai_analysis_state': 'completed'
            })

            # Crear nota en el chatter
            self.message_post(
                body=_("Análisis de IA completado. Puntuación sugerida: %s") % puntuacion.strip(),
                message_type='notification'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Análisis Completado'),
                    'message': _('La tarea ha sido analizada por IA correctamente.'),
                    'type': 'success',
                }
            }

        except Exception as e:
            self.ai_analysis_state = 'failed'
            _logger.error("Error en análisis IA: %s", str(e))
            raise ValidationError(_('Error en el análisis de IA: %s') % str(e))

    def _extract_section(self, text, section_name):
        """Extrae una sección específica del texto de respuesta"""
        try:
            start = text.find(f"<{section_name}>") + len(section_name) + 2
            end = text.find(f"</{section_name}>")
            return text[start:end].strip()
        except:
            return ""

    @api.depends('submission_date', 'deadline')
    def _compute_is_late(self):
        for record in self:
            if record.submission_date and record.deadline:
                record.is_late = record.submission_date > record.deadline
            else:
                record.is_late = False

    @api.constrains('score', 'max_score')
    def _check_score(self):
        for record in self:
            if record.score < 0:
                raise ValidationError(_('La calificación no puede ser negativa'))
            if record.score > record.max_score:
                raise ValidationError(_('La calificación no puede ser mayor que la máxima permitida'))

    def action_submit(self):
        """Registra la entrega de la tarea"""
        self.ensure_one()
        if not (self.content or self.attachment_ids):
            raise ValidationError(_('Debe proporcionar contenido o archivos adjuntos'))

        values = {
            'state': 'late' if self.is_late else 'submitted',
            'submission_date': fields.Datetime.now()
        }

        if self.is_late and not self.task_id.allow_late_submission:
            raise ValidationError(_('No se permiten entregas tardías para esta tarea'))

        return self.write(values)

    def action_grade(self):
        """Califica la entrega"""
        self.ensure_one()
        if not self.score:
            raise ValidationError(_('Debe asignar una calificación'))

        # Aplicar penalización por retraso si corresponde
        if self.is_late and self.task_id.late_submission_penalty > 0:
            penalty = (self.task_id.late_submission_penalty / 100) * self.score
            self.score = max(0, self.score - penalty)

        return self.write({'state': 'graded'})

    def action_reset(self):
        """Devuelve la entrega a estado pendiente"""
        return self.write({
            'state': 'pending',
            'submission_date': False,
            'score': 0,
            'feedback': False
        })
