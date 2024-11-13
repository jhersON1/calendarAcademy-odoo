from odoo import models, fields, api
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import json
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)

# Variable global para controlar la inicialización de Firebase
_firebase_app = None

class FCMDevice(models.Model):
    _name = 'fcm.device'
    _description = 'FCM Device Token'

    name = fields.Char(string='Device Name')
    token = fields.Char(string='FCM Token', required=True)
    user_id = fields.Many2one('res.users', string='User')
    active = fields.Boolean(default=True)
    last_used = fields.Datetime(string='Last Used', readonly=True)

    _sql_constraints = [
        ('token_unique', 'unique(token)', 'Token must be unique!')
    ]

    @api.model
    def create(self, vals):
        """Override create to add logging"""
        _logger.info(f"Creating new FCM device with values: {vals}")
        record = super(FCMDevice, self).create(vals)
        _logger.info(f"FCM device created successfully with ID: {record.id}")
        return record

    def write(self, vals):
        """Override write to add logging"""
        _logger.info(f"Updating FCM device {self.ids} with values: {vals}")
        result = super(FCMDevice, self).write(vals)
        _logger.info(f"FCM device {self.ids} updated successfully")
        return result

class FCMNotification(models.Model):
    _name = 'fcm.notification'
    _description = 'FCM Notification Manager'

    @api.model
    def initialize_firebase(self):
        """Initialize Firebase with detailed logging"""
        global _firebase_app
        try:
            _logger.info("Starting Firebase initialization process...")
            
            if _firebase_app:
                _logger.info("Firebase already initialized, reusing existing instance")
                return True

            # Log current directory and environment
            current_dir = os.getcwd()
            _logger.info(f"Current working directory: {current_dir}")
            _logger.info(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'Not set')}")

            # Obtener la ruta del módulo
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _logger.info(f"Module path: {module_path}")
            
            # Construir la ruta al archivo de configuración
            firebase_config_path = os.path.join(module_path, 'event', 'firebase-admin.json')
            _logger.info(f"Attempting to load Firebase config from: {firebase_config_path}")

            # Verificar existencia del archivo
            if not os.path.exists(firebase_config_path):
                _logger.error(f"Firebase configuration file not found at: {firebase_config_path}")
                raise FileNotFoundError(f"Firebase configuration file not found at: {firebase_config_path}")

            # Verificar permisos del archivo
            _logger.info(f"Checking file permissions for: {firebase_config_path}")
            try:
                with open(firebase_config_path, 'r') as f:
                    _logger.info("Successfully opened configuration file")
                    config_content = f.read()
                    _logger.info(f"Configuration file size: {len(config_content)} bytes")
            except Exception as e:
                _logger.error(f"Error reading configuration file: {str(e)}")
                raise

            # Inicializar Firebase
            _logger.info("Creating Firebase credentials...")
            cred = credentials.Certificate(firebase_config_path)
            
            _logger.info("Initializing Firebase app...")
            _firebase_app = firebase_admin.initialize_app(cred)
            
            _logger.info(f"Firebase initialized successfully. App name: {_firebase_app.name}")
            return True

        except Exception as e:
            _logger.error(f"Firebase initialization failed: {str(e)}")
            _logger.error(f"Exception type: {type(e)}")
            _logger.error(f"Exception args: {e.args}")
            raise

    @api.model
    def send_notification(self, title, body, data=None):
        """Send FCM notification with detailed logging"""
        try:
            _logger.info(f"Preparing to send notification - Title: {title}, Body: {body}")
            
            # Initialize Firebase
            _logger.info("Calling initialize_firebase()...")
            self.initialize_firebase()
            
            # Prepare data
            if data is None:
                data = {}
            
            # Log original data
            _logger.info(f"Original data: {data}")
            
            # Convert all values to string and validate
            processed_data = {}
            for k, v in data.items():
                try:
                    processed_data[str(k)] = str(v) if v is not None else ''
                    _logger.debug(f"Processed data field - Key: {k}, Value: {v}, Type: {type(v)}")
                except Exception as e:
                    _logger.warning(f"Error processing data field {k}: {str(e)}")
                    processed_data[str(k)] = ''

            _logger.info(f"Processed data: {processed_data}")

            # Get active devices
            _logger.info("Searching for active FCM devices...")
            devices = self.env['fcm.device'].search([('active', '=', True)])
            _logger.info(f"Found {len(devices)} active devices")
            
            # Extract tokens
            tokens = devices.mapped('token')
            _logger.info(f"Number of FCM tokens: {len(tokens)}")
            
            if not tokens:
                _logger.warning("No active FCM tokens found")
                return False

            # Create message
            _logger.info("Creating FCM message...")
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=processed_data,
                tokens=tokens,
            )
            
            # Send message
            _logger.info("Sending FCM message...")
            response = messaging.send_each_for_multicast(message)
            
            # Log response details
            _logger.info(f"Message sent. Success count: {response.success_count}, Failure count: {response.failure_count}")
            
            # Handle invalid tokens
            if response.failure_count > 0:
                _logger.info(f"Processing {response.failure_count} failed messages...")
                for idx, result in enumerate(response.responses):
                    if not result.success:
                        invalid_token = tokens[idx]
                        _logger.info(f"Processing invalid token: {invalid_token}")
                        
                        device = self.env['fcm.device'].search([('token', '=', invalid_token)], limit=1)
                        if device:
                            _logger.info(f"Deactivating device with token: {invalid_token}")
                            device.write({
                                'active': False,
                                'last_used': datetime.now()
                            })
                            _logger.info(f"Device deactivated successfully")
            
            return True
            
        except Exception as e:
            _logger.error(f"Error sending FCM notification: {str(e)}")
            _logger.error(f"Exception type: {type(e)}")
            _logger.error(f"Exception args: {e.args}")
            if hasattr(e, '_traceback_'):
                import traceback
                _logger.error(f"Traceback: {''.join(traceback.format_tb(e.traceback_))}")
            return False