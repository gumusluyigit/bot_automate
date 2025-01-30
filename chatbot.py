import os
from pdf_processor import PDFProcessor
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime, timedelta
import re
from email_handler import EmailHandler

class Chatbot:
    def __init__(self):
        self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
        self.chat_history_ids = None
        self.gui = None  # Will be set by GUI
        
        # Turkish month names and their variations
        self.turkish_months = {
            'ocak': 1, 'oca': 1, '01': 1, '1': 1,
            'şubat': 2, 'sub': 2, '02': 2, '2': 2,
            'mart': 3, 'mar': 3, '03': 3, '3': 3,
            'nisan': 4, 'nis': 4, '04': 4, '4': 4,
            'mayıs': 5, 'may': 5, '05': 5, '5': 5,
            'haziran': 6, 'haz': 6, '06': 6, '6': 6,
            'temmuz': 7, 'tem': 7, '07': 7, '7': 7,
            'ağustos': 8, 'agu': 8, 'agustos': 8, '08': 8, '8': 8,
            'eylül': 9, 'eyl': 9, 'eylul': 9, '09': 9, '9': 9,
            'ekim': 10, 'eki': 10, '10': 10,
            'kasım': 11, 'kas': 11, 'kasim': 11, '11': 11,
            'aralık': 12, 'ara': 12, 'aralik': 12, '12': 12
        }
        
        print("Initializing chatbot... This may take a moment.")
        self.processed_dir = 'processed'
        self.samples_dir = 'pdf_samples'
        print("Chatbot initialized!")

    def set_gui(self, gui):
        """Set the GUI reference for callback functions"""
        self.gui = gui
        
    def parse_date(self, date_str):
        """Parse a date string in various Turkish formats"""
        # Remove extra spaces and convert to lowercase
        date_str = ' '.join(date_str.lower().split())
        
        # Try to match different date formats
        patterns = [
            # 15 ocak 2025
            r'(\d{1,2})\s*([a-zışğüçö]+)\s*(\d{4})',
            # ocak 15 2025
            r'([a-zışğüçö]+)\s*(\d{1,2})\s*(\d{4})',
            # 15/01/2025 or 15.01.2025
            r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if groups[1] in self.turkish_months:  # day month year
                    day, month_str, year = groups
                    month = self.turkish_months[month_str]
                elif groups[0] in self.turkish_months:  # month day year
                    month_str, day, year = groups
                    month = self.turkish_months[month_str]
                else:  # numeric format
                    day, month, year = groups
                    month = int(month)
                
                try:
                    return datetime(int(year), month, int(day))
                except ValueError:
                    return None
        
        return None
        
    def extract_date_range(self, text):
        """Extract date range from text"""
        text = text.lower()
        
        # Check for "last week" or "previous week"
        if "geçen hafta" in text or "önceki hafta" in text:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday() + 7)
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        # Check for "this week"
        if "bu hafta" in text:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        # Check for "X haftası" format (week of X)
        hafta_match = re.search(r'(\d{1,2}\s+[a-zışğüçö]+\s+\d{4})\s*haftas[ıi]', text)
        if hafta_match:
            date_str = hafta_match.group(1)
            start_date = self.parse_date(date_str)
            if start_date:
                # If the given date is not Monday, find the Monday of that week
                if start_date.weekday() != 0:
                    start_date = start_date - timedelta(days=start_date.weekday())
                end_date = start_date + timedelta(days=6)
                return start_date, end_date
            
        # Look for date range with separator
        separators = [" - ", " ile ", " arası ", " arasındaki ", " dan ", " den "]
        for sep in separators:
            if sep in text:
                parts = text.split(sep)
                if len(parts) == 2:
                    start_date = self.parse_date(parts[0])
                    end_date = self.parse_date(parts[1])
                    if start_date and end_date:
                        return start_date, end_date
        
        # Try to find a single date (will use whole week)
        date = self.parse_date(text)
        if date:
            # If a single date is found, use its week
            monday = date - timedelta(days=date.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        return None, None
        
    def process_command(self, text):
        """Process commands related to PDF processing"""
        text = text.lower()
        
        # Check if this is a PDF processing request
        process_keywords = ["işle", "isle", "process", "fatura", "pdf", "dosya", "belgeler"]
        is_process_request = any(keyword in text for keyword in process_keywords)
        
        if not is_process_request:
            return None
            
        # Extract date range
        start_date, end_date = self.extract_date_range(text)
        if not start_date or not end_date:
            return ("Tarih aralığını anlayamadım. İşte bazı örnek kullanımlar:\n\n" + \
                   "- 'Geçen haftanın faturalarını işle'\n" + \
                   "- '15 Ocak 2025 - 21 Ocak 2025 arası faturaları process et'\n" + \
                   "- '15 Ocak 2025 haftasının PDFlerini işle'\n" + \
                   "- 'Bu haftanın belgelerini işle'\n" + \
                   "- '15/01/2025 - 21/01/2025 arası PDFleri işle'")
        
        # Check if GUI reference exists
        if not self.gui:
            return "PDF işleme fonksiyonu şu anda kullanılamıyor."
            
        # Check email settings first
        if not self.gui.check_email_settings():
            return "Lütfen önce email ayarlarını yapılandırın. Ayarlar sekmesinden email adreslerini giriniz."
            
        # Process PDFs for the date range
        try:
            if self.gui.is_processing:
                return "Şu anda başka bir işlem devam ediyor. Lütfen tamamlanmasını bekleyin."
                
            self.gui.is_processing = True
            self.gui.update_processing_state()
            
            # Initialize email handler if needed
            if not self.gui.email_handler:
                self.gui.email_handler = EmailHandler(
                    self.gui.sender_email.get(),
                    self.gui.internal_email.get()
                )
            
            # Log the operation
            self.gui.log_message(f"Processing PDFs for week {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}")
            self.gui.update_status("="*50)
            self.gui.update_status(f"Processing PDFs for Week: {start_date.strftime('%d %B %Y')} "
                                f"to {end_date.strftime('%d %B %Y')}")
            self.gui.update_status("="*50)
            
            # Get PDFs for the date range
            pdfs = self.gui.web_automation.search_and_download_pdf(target_week=(start_date, end_date))
            
            if not pdfs:
                self.gui.log_message("No unprocessed PDFs found for the specified week")
                self.gui.update_status("No unprocessed PDFs found for the specified week")
                self.gui.is_processing = False
                self.gui.update_processing_state()
                return "Bu tarih aralığında işlenmemiş PDF bulunamadı."
                
            # Process the PDFs
            self.gui.process_pdf_list(pdfs)
            return "PDF işleme tamamlandı. Detaylar için durum panelini kontrol edin."
            
        except Exception as e:
            self.gui.handle_error(e)
            self.gui.is_processing = False
            self.gui.update_processing_state()
            return f"PDF işleme sırasında bir hata oluştu: {str(e)}"
        
    def get_response(self, user_input):
        """Get response from the chatbot"""
        # First try to process as a command
        command_response = self.process_command(user_input)
        if command_response:
            return command_response
            
        # If not a command, use DialoGPT for general conversation
        new_user_input_ids = self.tokenizer.encode(user_input + self.tokenizer.eos_token, return_tensors='pt')
        
        if self.chat_history_ids is not None:
            bot_input_ids = torch.cat([self.chat_history_ids, new_user_input_ids], dim=-1)
        else:
            bot_input_ids = new_user_input_ids
            
        self.chat_history_ids = self.model.generate(
            bot_input_ids,
            max_length=1000,
            pad_token_id=self.tokenizer.eos_token_id,
            no_repeat_ngram_size=3,
            do_sample=True,
            top_k=100,
            top_p=0.7,
            temperature=0.8
        )
        
        response = self.tokenizer.decode(self.chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
        return response
        
    def reset_chat(self):
        """Reset the chat history"""
        self.chat_history_ids = None

    def _get_invoice_info(self, query: str) -> str:
        """Get information about a specific invoice"""
        # Extract invoice number
        invoice_num = ''.join(char for char in query if char.isdigit())
        if not invoice_num:
            return "Could not find an invoice number in your query. Please provide an invoice number."

        try:
            # Search through processed PDFs
            for file in os.listdir(self.processed_dir):
                if file.endswith('.pdf'):
                    pdf_path = os.path.join(self.processed_dir, file)
                    info = PDFProcessor.extract_invoice_info(pdf_path)
                    if info and info.get('invoice_number') == invoice_num:
                        return (f"Invoice #{invoice_num}:\n"
                               f"Company: {info.get('company_name', 'N/A')}\n"
                               f"Period: {info.get('period_start').strftime('%Y-%m-%d')} to "
                               f"{info.get('period_end').strftime('%Y-%m-%d')}\n"
                               f"Status: Processed")

            # Check unprocessed PDFs
            for file in os.listdir(self.samples_dir):
                if file.endswith('.pdf'):
                    pdf_path = os.path.join(self.samples_dir, file)
                    info = PDFProcessor.extract_invoice_info(pdf_path)
                    if info and info.get('invoice_number') == invoice_num:
                        return (f"Invoice #{invoice_num}:\n"
                               f"Company: {info.get('company_name', 'N/A')}\n"
                               f"Period: {info.get('period_start').strftime('%Y-%m-%d')} to "
                               f"{info.get('period_end').strftime('%Y-%m-%d')}\n"
                               f"Status: Pending")

            return f"Could not find information for invoice #{invoice_num}"

        except Exception as e:
            return f"Error retrieving invoice information: {str(e)}"

    def _get_company_info(self, query: str) -> str:
        """Get information about a company's invoices"""
        try:
            # Extract company name - if "rovex" is specifically mentioned, use that
            company_name = "rovex" if "rovex" in query else None
            
            if not company_name:
                # Try to extract company name after "company" or "for"
                words = query.split()
                for i, word in enumerate(words):
                    if word in ['company', 'for'] and i + 1 < len(words):
                        company_name = words[i + 1]
                        break

            if not company_name:
                return "Could not identify the company name in your query. Please specify the company name."

            invoices = []
            # Search through all PDFs
            for directory in [self.processed_dir, self.samples_dir]:
                if os.path.exists(directory):
                    for file in os.listdir(directory):
                        if file.endswith('.pdf'):
                            pdf_path = os.path.join(directory, file)
                            info = PDFProcessor.extract_invoice_info(pdf_path)
                            if info and company_name.lower() in info.get('company_name', '').lower():
                                status = "Processed" if directory == self.processed_dir else "Pending"
                                invoices.append({
                                    'number': info.get('invoice_number'),
                                    'period_start': info.get('period_start'),
                                    'period_end': info.get('period_end'),
                                    'due_date': info.get('due_date'),
                                    'status': status
                                })

            if invoices:
                response = f"Found {len(invoices)} invoice(s) for {company_name}:\n\n"
                for inv in invoices:
                    response += (f"Invoice #{inv['number']}\n"
                               f"Period: {inv['period_start'].strftime('%Y-%m-%d')} to "
                               f"{inv['period_end'].strftime('%Y-%m-%d')}\n"
                               f"Due Date: {inv['due_date'].strftime('%Y-%m-%d') if inv['due_date'] else 'N/A'}\n"
                               f"Status: {inv['status']}\n\n")
                return response

            return f"No invoices found for company '{company_name}'"

        except Exception as e:
            return f"Error retrieving company information: {str(e)}"

    def _get_due_date_info(self, query: str) -> str:
        """Get due date information for an invoice or company"""
        try:
            # Check for invoice number
            invoice_num = ''.join(char for char in query if char.isdigit())
            if invoice_num:
                return self._get_invoice_info(invoice_num)  # This will include due date
            
            # Check for company name
            if 'rovex' in query:
                return self._get_company_info('rovex')  # This will include due dates
            
            return "Please specify an invoice number or company name to check due dates."
            
        except Exception as e:
            return f"Error retrieving due date information: {str(e)}"

    def _get_status_info(self) -> str:
        """Get general processing status"""
        try:
            processed_count = len([f for f in os.listdir(self.processed_dir) if f.endswith('.pdf')])
            pending_count = len([f for f in os.listdir(self.samples_dir) if f.endswith('.pdf')])
            
            return (f"Current Status:\n"
                   f"- Processed PDFs: {processed_count}\n"
                   f"- Pending PDFs: {pending_count}\n"
                   f"- Total PDFs: {processed_count + pending_count}")
                   
        except Exception as e:
            return f"Error retrieving status information: {str(e)}" 