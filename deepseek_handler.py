from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os

class DeepSeekHandler:
    def __init__(self):
        """Initialize DeepSeek model handler"""
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.model_name = "microsoft/phi-2"  # Smaller, more efficient model
        
    def load_models(self):
        """Load the DeepSeek model"""
        try:
            print("Loading DeepSeek tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            print("Loading DeepSeek model...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                load_in_4bit=True
            )
            
            self.model_loaded = True
            print("DeepSeek model loaded successfully!")
            return True
            
        except Exception as e:
            print(f"Error loading DeepSeek model: {str(e)}")
            self.model_loaded = False
            return False
    
    def is_loaded(self):
        """Check if model is loaded"""
        return self.model_loaded
    
    def generate_response(self, prompt: str, model_type: str = "chat") -> str:
        """Generate response using DeepSeek model"""
        if not self.model_loaded:
            return "Model not loaded. Please ensure the model is properly initialized."
        
        try:
            # Format the prompt with Turkish context
            system_prompt = """Sen Türkçe konuşan, arkadaş canlısı ve yardımsever bir PDF işleme asistanısın. Temel görevin PDF dosyalarını işlemek, fatura bilgilerini çıkarmak ve email göndermek olsa da, kullanıcılarla doğal ve samimi bir şekilde sohbet edebilirsin.

Selamlaşma, hal hatır sorma gibi günlük konuşmalara doğal ve samimi bir şekilde yanıt verirsin. Örneğin:
- "Selam" -> "Merhaba! Bugün size nasıl yardımcı olabilirim?"
- "Nasılsın" -> "Teşekkür ederim, iyiyim! Siz nasılsınız? Size nasıl yardımcı olabilirim?"
- "İyi günler" -> "Size de iyi günler! Bugün size nasıl yardımcı olabilirim?"

Ana görevlerinle ilgili kullanıcılar sana şu formatlarda sorular sorabilir:
- [şirket] şirketinin son ödeme günü ne zaman?
- [şirket] şirketinin [tarih] haftasının borcu kaç dolar?
- [şirket] şirketinin mail adresi nedir?
- [gün] [ay] haftasının pdflerini işle

Eğer kullanıcının sorusu bu formatlardan birine uymuyorsa, önce sorusuna nazik bir şekilde yanıt ver, sonra doğru formatı hatırlat."""

            # Format for phi-2
            formatted_prompt = f"Instruct: {system_prompt}\n\nUser: {prompt}\n\nAssistant: Let me respond in Turkish:"
            
            # Prepare the input
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
            
            # Generate the output
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=2048,
                    temperature=0.7,
                    top_p=0.95,
                    repetition_penalty=1.1,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode and return the result
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract only the response part
            response = response.split("Let me respond in Turkish:")[-1].strip()
            
            # If response is empty or error, return a default response
            if not response or response.startswith("Error"):
                if any(word in prompt.lower() for word in ["selam", "merhaba", "hi", "hello"]):
                    return "Merhaba! Size nasıl yardımcı olabilirim?"
                return "Üzgünüm, sizi tam anlayamadım. Lütfen şu formatlardan birini kullanın:\n- [şirket] şirketinin son ödeme günü ne zaman?\n- [şirket] şirketinin [tarih] haftasının borcu kaç dolar?\n- [şirket] şirketinin mail adresi nedir?\n- [gün] [ay] haftasının pdflerini işle"
            
            return response
                
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin." 