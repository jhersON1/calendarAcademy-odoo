# -*- coding: utf-8 -*-
from odoo import models, fields, api
from colorsys import rgb_to_hsv, hsv_to_rgb


class EventColorMixin(models.AbstractModel):
    _name = 'event.color.mixin'
    _description = 'Mixin para manejo de colores de eventos'

    def _get_event_colors(self):
        """Define los colores base para cada tipo de evento"""
        return {
            'exam': '#FF6B6B',  # Rojo suave
            'activity': '#4ECDC4',  # Turquesa
            'meeting': '#45B7D1',  # Azul claro
            'academic': '#96CEB4',  # Verde suave
            'administrative': '#FFEEAD'  # Amarillo suave
        }

    def _get_state_opacity(self):
        """Define la opacidad basada en el estado"""
        return {
            'draft': 0.7,  # Más transparente para borradores
            'confirmed': 1.0,  # Color completo para confirmados
            'in_progress': 0.9,  # Casi opaco para en progreso
            'done': 0.6,  # Más transparente para completados
            'cancelled': 0.4  # Muy transparente para cancelados
        }

    def _hex_to_rgb(self, hex_color):
        """Convierte color hexadecimal a RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        """Convierte RGB a hexadecimal"""
        return '#{:02x}{:02x}{:02x}'.format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )

    def _adjust_color_priority(self, hex_color, priority):
        """Ajusta el color basado en la prioridad (0-2)"""
        rgb = self._hex_to_rgb(hex_color)
        hsv = rgb_to_hsv(*rgb)

        # Ajustar saturación y valor basado en prioridad
        if priority == '2':  # Urgente
            # Aumentar saturación y valor para destacar
            new_hsv = (hsv[0], min(hsv[1] * 1.3, 1.0), min(hsv[2] * 1.2, 1.0))
        elif priority == '1':  # Importante
            # Aumentar ligeramente la saturación
            new_hsv = (hsv[0], min(hsv[1] * 1.1, 1.0), hsv[2])
        else:  # Normal
            new_hsv = hsv

        rgb = hsv_to_rgb(*new_hsv)
        return self._rgb_to_hex(rgb)

    def _apply_state_opacity(self, hex_color, state):
        """Aplica opacidad al color basado en el estado"""
        rgb = self._hex_to_rgb(hex_color)
        opacity = self._get_state_opacity().get(state, 1.0)

        # Mezclar con blanco basado en la opacidad
        result_rgb = tuple(c * opacity + (1 - opacity) for c in rgb)
        return self._rgb_to_hex(result_rgb)

    def calculate_display_color(self, event_type, priority, state, custom_color=False):
        """
        Calcula el color final del evento considerando:
        - Tipo de evento (color base)
        - Prioridad (intensidad)
        - Estado (opacidad)
        - Color personalizado (si existe)
        """
        if custom_color:
            base_color = custom_color
        else:
            base_color = self._get_event_colors().get(event_type, '#FFFFFF')

        # Ajustar por prioridad
        color_with_priority = self._adjust_color_priority(base_color, priority)

        # Aplicar opacidad según estado
        final_color = self._apply_state_opacity(color_with_priority, state)

        return final_color

    def get_calendar_frontend_colors(self, event_type, priority, state):
        """
        Devuelve un diccionario con los colores para el frontend del calendario
        """
        base_color = self._get_event_colors().get(event_type, '#FFFFFF')
        final_color = self.calculate_display_color(event_type, priority, state)

        return {
            'backgroundColor': final_color,
            'borderColor': base_color,
            'textColor': '#000000' if state != 'cancelled' else '#666666'
        }