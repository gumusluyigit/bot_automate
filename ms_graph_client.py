import msal
import requests
import os
import base64
from datetime import datetime
import json
import time

class MSGraphClient:
    def __init__(self, tenant_id=None, client_id=None, client_secret=None):
        """Initialize the Microsoft Graph client with OAuth credentials"""
        self.tenant_id = tenant_id or os.getenv('MS_TENANT_ID')
        self.client_id = client_id or os.getenv('MS_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('MS_CLIENT_SECRET')
        self.scope = ['https://graph.microsoft.com/.default']
        self.token = None
        self.token_expires = 0
        
    def get_token(self):
        """Get an access token for Microsoft Graph API"""
        # Check if we have a valid token
        if self.token and time.time() < self.token_expires - 300:  # 5 min buffer
            return self.token
            
        # Create MSAL app
        app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
        # Acquire token
        result = app.acquire_token_for_client(scopes=self.scope)
        
        if "access_token" in result:
            self.token = result['access_token']
            self.token_expires = time.time() + result['expires_in']
            return self.token
        else:
            error = result.get("error")
            error_description = result.get("error_description")
            raise Exception(f"Error getting token: {error} - {error_description}")
    
    def send_email(self, sender_email, to_email, subject, body, attachments=None):
        """Send an email using Microsoft Graph API"""
        token = self.get_token()
        
        # Prepare the email message
        email_msg = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ],
                "from": {
                    "emailAddress": {
                        "address": sender_email
                    }
                }
            },
            "saveToSentItems": "true"
        }
        
        # Add attachments if provided
        if attachments:
            if isinstance(attachments, str):
                attachments = [attachments]
                
            email_msg["message"]["attachments"] = []
            
            for attachment_path in attachments:
                if os.path.exists(attachment_path):
                    # Read file and encode as base64
                    with open(attachment_path, "rb") as file:
                        content_bytes = file.read()
                        content_base64 = base64.b64encode(content_bytes).decode()
                    
                    # Add attachment to email
                    attachment = {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(attachment_path),
                        "contentType": "application/pdf",  # Adjust based on file type
                        "contentBytes": content_base64
                    }
                    
                    email_msg["message"]["attachments"].append(attachment)
        
        # Send the email
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            'https://graph.microsoft.com/v1.0/users/' + sender_email + '/sendMail',
            headers=headers,
            data=json.dumps(email_msg)
        )
        
        if response.status_code == 202:  # 202 Accepted
            return True
        else:
            error_msg = response.text
            raise Exception(f"Failed to send email: {response.status_code} - {error_msg}")
    
    def test_connection(self, sender_email):
        """Test the connection to Microsoft Graph API"""
        try:
            token = self.get_token()
            
            # Test if we can access the user's profile
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'https://graph.microsoft.com/v1.0/users/{sender_email}',
                headers=headers
            )
            
            if response.status_code == 200:
                return True, "Connection successful"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, f"Error: {str(e)}" 