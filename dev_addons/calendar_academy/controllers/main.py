from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime
from psycopg2 import Error as PSQLError

_logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar objetos datetime"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

class FCMController(http.Controller):
    @http.route('/api/fcm/register', type='json', auth='none', csrf=False, methods=['POST'])
    def register_device(self, **post):
        """
        Registra un nuevo dispositivo FCM o actualiza uno existente
        """
        try:
            _logger.info("Starting FCM device registration process")
            
            data = json.loads(request.httprequest.data)
            _logger.info(f"Parsed request data: {data}")
            
            token = data.get('token')
            device_name = data.get('device_name', 'Unknown Device')
            
            _logger.info(f"Processing registration - Token: {token}, Device Name: {device_name}")
            
            if not token:
                _logger.error("Token is missing in request")
                return {'success': False, 'error': 'Token is required'}

            env = request.env(su=True)
            
            try:
                with env.cr.savepoint():
                    # Buscar dispositivo existente (incluso inactivos)
                    device = env['fcm.device'].search([
                        ('token', '=', token)
                    ], limit=1)
                    
                    if device:
                        _logger.info(f"Found existing device with ID: {device.id}, Active status: {device.active}")
                        device_data = {
                            'name': device_name,
                            'active': True  # Reactivar si estaba inactivo
                        }
                        _logger.info(f"Updating device with data: {device_data}")
                        device.write(device_data)
                        _logger.info(f"Device updated successfully")
                        device_id = device.id
                    else:
                        _logger.info("Creating new device registration")
                        device_data = {
                            'name': device_name,
                            'token': token,
                            'active': True
                        }
                        _logger.info(f"Creation data: {device_data}")
                        new_device = env['fcm.device'].create(device_data)
                        _logger.info(f"New device created with ID: {new_device.id}")
                        device_id = new_device.id
                    
                    # Verificar el registro
                    verification = env['fcm.device'].search([
                        ('id', '=', device_id),
                        ('active', '=', True)
                    ], limit=1)
                    
                    if verification:
                        return {
                            'success': True,
                            'device_id': verification.id,
                            'message': 'Device updated' if device else 'Device created'
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'Failed to verify device registration'
                        }
            
            except PSQLError as e:
                _logger.error(f"PostgreSQL error: {str(e)}")
                return {'success': False, 'error': f'Database error: {str(e)}'}
            except Exception as e:
                _logger.error(f"Database operation failed: {str(e)}")
                return {'success': False, 'error': f'Operation failed: {str(e)}'}
                
        except Exception as e:
            _logger.error(f"Unexpected error in register_device: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    @http.route('/api/fcm/devices', type='http', auth='none', csrf=False, methods=['GET'])
    def list_devices(self):
        """
        Lista todos los dispositivos FCM registrados
        """
        try:
            _logger.info("Fetching list of FCM devices")
            
            # Obtener parámetros de consulta
            include_inactive = request.params.get('include_inactive', 'false').lower() == 'true'
            _logger.info(f"Include inactive devices: {include_inactive}")
            
            env = request.env(su=True)
            
            # Construir dominio de búsqueda
            domain = []
            if not include_inactive:
                domain.append(('active', '=', True))
            
            # Realizar búsqueda
            devices = env['fcm.device'].search(domain)
            
            device_list = []
            for device in devices:
                device_list.append({
                    'id': device.id,
                    'name': device.name,
                    'token': device.token,
                    'active': device.active,
                    'creation_date': device.create_date.strftime('%Y-%m-%d %H:%M:%S') if device.create_date else None,
                    'write_date': device.write_date.strftime('%Y-%m-%d %H:%M:%S') if device.write_date else None,
                    'status': 'active' if device.active else 'inactive'
                })
            
            _logger.info(f"Found {len(device_list)} devices")
            
            response_data = {
                'success': True,
                'total_count': len(device_list),
                'devices': device_list
            }
            
            return request.make_response(
                json.dumps(response_data, cls=DateTimeEncoder),
                headers=[('Content-Type', 'application/json')]
            )
            
        except Exception as e:
            _logger.error(f"Error in list_devices: {str(e)}")
            error_response = {
                'success': False,
                'error': str(e),
                'error_type': type(e)._name_
            }
            return request.make_response(
                json.dumps(error_response),
                headers=[('Content-Type', 'application/json')]
            )

    @http.route('/api/fcm/unregister', type='json', auth='none', csrf=False, methods=['POST'])
    def unregister_device(self, **post):
        """
        Elimina o desactiva un dispositivo FCM por token
        """
        try:
            _logger.info("Starting FCM device unregistration process")
            
            data = json.loads(request.httprequest.data)
            token = data.get('token')
            delete_permanent = data.get('delete_permanent', False)
            
            _logger.info(f"Processing unregistration - Token: {token}, Permanent: {delete_permanent}")
            
            if not token:
                return {'success': False, 'error': 'Token is required'}

            env = request.env(su=True)
            
            try:
                with env.cr.savepoint():
                    device = env['fcm.device'].search([('token', '=', token)], limit=1)
                    
                    if not device:
                        return {'success': False, 'error': 'Device not found'}
                    
                    if delete_permanent:
                        _logger.info(f"Permanently deleting device with ID: {device.id}")
                        device.unlink()
                        return {
                            'success': True,
                            'message': 'Device deleted permanently'
                        }
                    else:
                        _logger.info(f"Deactivating device with ID: {device.id}")
                        device.write({'active': False})
                        return {
                            'success': True,
                            'message': 'Device deactivated'
                        }
                    
            except Exception as e:
                _logger.error(f"Database operation failed: {str(e)}")
                return {'success': False, 'error': str(e)}
                
        except Exception as e:
            _logger.error(f"Error in unregister_device: {str(e)}")
            return {'success': False, 'error': str(e)}