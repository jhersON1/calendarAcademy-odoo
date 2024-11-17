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

    def _process_attachment_for_ai(self, attachment):
        """Procesa un archivo adjunto para análisis de IA"""
        try:
            if attachment.mimetype.startswith('text/'):
                return {
                    'type': 'text',
                    'content': attachment.raw.decode('utf-8', errors='ignore')[:1000]
                }
            elif attachment.mimetype.startswith('image/'):
                # Formato correcto para GPT-4 Vision
                return {
                    'type': 'image',
                    'content': {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{attachment.mimetype};base64,{attachment.datas.decode('utf-8')}"
                        }
                    }
                }
            else:
                return {
                    'type': 'unsupported',
                    'content': f"Archivo no procesable: {attachment.name} ({attachment.mimetype})"
                }
        except Exception as e:
            _logger.error(f"Error processing attachment {attachment.name}: {str(e)}")
            return None

    def action_analyze_with_ai(self):
        """Analiza la tarea usando IA"""
        self.ensure_one()
        if self.state not in ['submitted', 'late']:
            raise ValidationError(_('Solo se pueden analizar tareas entregadas'))

        api_key = self.env['ir.config_parameter'].sudo().get_param('calendar_academy.openai_api_key')
        if not api_key:
            raise ValidationError(_('La clave API de OpenAI no está configurada'))

        self.ai_analysis_state = 'analyzing'
        try:
            client = openai.OpenAI(api_key=api_key)
            
            # Preparar el contenido del mensaje
            message_content = [{
                "type": "text",
                "text": f"""
                    Tarea: {self.task_id.name or ''}
                    Descripción: {self.task_id.description or ''}
                    Puntuación máxima: {self.task_id.max_score or 0}
                    
                    Contenido de la entrega:
                    {self.content or 'No hay contenido textual'}
                """
            }]

            # Procesar adjuntos
            for attachment in self.attachment_ids:
                processed = self._process_attachment_for_ai(attachment)
                if processed:
                    if processed['type'] == 'image':
                        message_content.append(processed['content'])
                    else:
                        message_content.append({
                            "type": "text",
                            "text": processed['content']
                        })

            # Agregar instrucciones finales
            message_content.append({
                "type": "text",
                "text": """
                Por favor, proporciona:
                1. Una evaluación detallada de la entrega (incluyendo análisis de imágenes si hay)
                2. Retroalimentación constructiva para el estudiante
                3. Una puntuación sugerida
                4. Justificación de la puntuación

                Estructura tu respuesta así:
                <EVALUACION>tu evaluación detallada</EVALUACION>
                <RETROALIMENTACION>tus comentarios constructivos</RETROALIMENTACION>
                <PUNTUACION>número sugerido</PUNTUACION>
                <JUSTIFICACION>justificación de la puntuación</JUSTIFICACION>
                """
            })

            # Llamar a la API
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Usar el modelo con capacidad de visión
                    messages=[{
                        "role": "user",
                        "content": message_content
                    }],
                    max_tokens=1000,
                    temperature=0.7
                )
            except Exception as e:
                _logger.error(f"Error en la llamada a la API: {str(e)}")
                raise ValidationError(_('Error en la llamada a la API: %s') % str(e))

            # Validate API response
            if not response.choices or not response.choices[0].message.content:
                raise ValidationError(_('La respuesta de la API está vacía'))

            ai_response = response.choices[0].message.content

            # Process response sections
            sections = {
                'EVALUACION': '',
                'RETROALIMENTACION': '',
                'PUNTUACION': '',
                'JUSTIFICACION': ''
            }
            
            for section in sections.keys():
                sections[section] = self._extract_section(ai_response, section)
                if not sections[section] and section in ['EVALUACION', 'PUNTUACION']:
                    raise ValidationError(_(f'Sección {section} no encontrada en la respuesta'))

            try:
                score = float(sections['PUNTUACION'].strip() or 0)
                if score < 0 or score > self.task_id.max_score:
                    raise ValidationError(_('Puntuación sugerida fuera de rango'))
            except ValueError:
                raise ValidationError(_('Error al procesar la puntuación sugerida'))

            # Format final feedback
            feedback_final = self._format_ai_feedback(sections)

            # Update record
            self.write({
                'ai_feedback': feedback_final,
                'ai_suggested_score': score,
                'ai_analysis_state': 'completed'
            })

            self.message_post(
                body=_("Análisis de IA completado. Puntuación sugerida: %s") % score,
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

    def _prepare_ai_prompt(self, task_context, submission_content, attachment_texts):
        """Prepara el prompt para la IA"""
        return f"""Actúa como un profesor experto evaluando esta tarea.
            
            CONTEXTO DE LA TAREA:
            {task_context}

            ENTREGA DEL ESTUDIANTE:
            Contenido textual:
            {submission_content}

            Archivos adjuntos:
            {chr(10).join(attachment_texts)}

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

    def _format_ai_feedback(self, sections):
        """Formatea la retroalimentación de la IA"""
        return f"""
            EVALUACIÓN DETALLADA:
            {sections['EVALUACION']}

            RETROALIMENTACIÓN:
            {sections['RETROALIMENTACION']}

            JUSTIFICACIÓN DE LA PUNTUACIÓN:
            {sections['JUSTIFICACION']}
            """

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
