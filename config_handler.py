import json
import os

class ConfigHandler:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        return {
            'sender_email': '',
            'app_password': '',
            'internal_email': ''
        }

    def save_config(self, sender_email=None, app_password=None, internal_email=None):
        """Save configuration to file"""
        try:
            # Update only provided values
            if sender_email is not None:
                self.config['sender_email'] = sender_email
            if app_password is not None:
                self.config['app_password'] = app_password
            if internal_email is not None:
                self.config['internal_email'] = internal_email

            # Save to file
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
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