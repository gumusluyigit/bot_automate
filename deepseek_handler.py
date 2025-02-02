import requests
import os
from dotenv import load_dotenv

class DeepSeekHandler:
    def __init__(self):
        """Initialize DeepSeek API handler"""
        load_dotenv()  # Load API key from .env file
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_url = 'https://api.deepseek.com/v1/chat/completions'
        self.is_api_configured = bool(self.api_key)
        
        if not self.is_api_configured:
            print("Warning: DEEPSEEK_API_KEY not found in .env file")
    
    def load_models(self):
        """Check if API is configured"""
        return self.is_api_configured
    
    def is_loaded(self):
        """Check if API is configured"""
        return self.is_api_configured
    
    def generate_response(self, prompt: str, model_type: str = "chat") -> str:
        """Generate response using DeepSeek API"""
        if not self.is_api_configured:
            return "API key not configured. Please set DEEPSEEK_API_KEY in .env file."
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'deepseek-chat' if model_type == "chat" else 'deepseek-base',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"API request failed with status code {response.status_code}: {response.text}")
                return f"API request failed: {response.text}"
                
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return f"Error: {str(e)}" 