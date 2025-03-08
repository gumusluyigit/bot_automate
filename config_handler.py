import json
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class ConfigHandler:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        # Load environment variables
        load_dotenv()
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from environment variables, falling back to file"""
        # Always prioritize environment variables
        config = {
            'sender_email': os.getenv('SENDER_EMAIL') or os.getenv('EMAIL_USER') or '',
            'internal_email': os.getenv('INTERNAL_EMAIL') or '',
            'ms_tenant_id': os.getenv('MS_TENANT_ID') or '',
            'ms_client_id': os.getenv('MS_CLIENT_ID') or '',
            'ms_client_secret': os.getenv('MS_CLIENT_SECRET') or ''
        }
        
        # If environment variables are not set, try loading from file
        if (not config['sender_email'] or not config['ms_tenant_id']) and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    # Only use file values if env vars are not set
                    if not config['sender_email']:
                        config['sender_email'] = file_config.get('sender_email', '')
                    if not config['internal_email']:
                        config['internal_email'] = file_config.get('internal_email', '')
                    if not config['ms_tenant_id']:
                        config['ms_tenant_id'] = file_config.get('ms_tenant_id', '')
                    if not config['ms_client_id']:
                        config['ms_client_id'] = file_config.get('ms_client_id', '')
                    # Note: We don't load client_secret from file for security reasons
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        
        return config

    def save_config(self, sender_email=None, internal_email=None, ms_tenant_id=None, ms_client_id=None, ms_client_secret=None):
        """Save configuration to both environment and file"""
        try:
            # Update only provided values
            if sender_email is not None:
                self.config['sender_email'] = sender_email
                os.environ['SENDER_EMAIL'] = sender_email
            if internal_email is not None:
                self.config['internal_email'] = internal_email
                os.environ['INTERNAL_EMAIL'] = internal_email
            if ms_tenant_id is not None:
                self.config['ms_tenant_id'] = ms_tenant_id
                os.environ['MS_TENANT_ID'] = ms_tenant_id
            if ms_client_id is not None:
                self.config['ms_client_id'] = ms_client_id
                os.environ['MS_CLIENT_ID'] = ms_client_id
            if ms_client_secret is not None:
                # Only update environment variable, not the config object
                os.environ['MS_CLIENT_SECRET'] = ms_client_secret
                # Don't store client_secret in the config object for security
                self.config['ms_client_secret'] = "********"

            # Save non-sensitive config to file as backup
            file_config = {
                'sender_email': self.config['sender_email'],
                'internal_email': self.config['internal_email'],
                'ms_tenant_id': self.config['ms_tenant_id'],
                'ms_client_id': self.config['ms_client_id']
                # Don't save client_secret to file
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(file_config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def get_config(self):
        """Get current configuration"""
        return self.config

    def update_config(self, **kwargs):
        """Update configuration with provided values"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
        return self.save_config(**kwargs) 