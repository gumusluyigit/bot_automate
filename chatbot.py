import os
from pdf_processor import PDFProcessor
from datetime import datetime, timedelta
import re
from email_handler import EmailHandler
from rapidfuzz import fuzz, process

class Chatbot:
    def __init__(self, gui=None):
        self.gui = gui
        
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
        
        # Common command patterns with variations
        self.command_patterns = [
            "işle", "isle", "islemek", "process", "proccess",
            "fatura", "fturalar", "faturalar",
            "pdf", "pdfs", "pdfler", "pdfları",
            "dosya", "dosyalar", "dosyalari",
            "belge", "belgeler", "belgeleri",
            "hafta", "haftanın", "haftasının",
            "geçen", "gecen", "gçn",
            "arası", "arasında", "arasnda"
        ]
        
        self.processed_dir = 'processed'
        self.samples_dir = 'pdf_samples'
        
        # Common responses for basic interactions
        self.responses = {
            'greeting': "Merhaba! Size nasıl yardımcı olabilirim?",
            'how_are_you': "İyiyim, teşekkür ederim! Size nasıl yardımcı olabilirim?",
            'help': ("Size PDF işleme konusunda yardımcı olabilirim. Örnek komutlar:\n\n"
                    "- 'Geçen haftanın faturalarını işle'\n"
                    "- '15 Ocak 2025 haftasının PDFlerini işle'\n"
                    "- 'Bu haftanın belgelerini işle'\n"
                    "- '15/01/2025 - 21/01/2025 arası PDFleri işle'"),
            'thanks': "Rica ederim! Başka bir konuda yardımcı olabilir miyim?",
            'goodbye': "Görüşmek üzere! Başka bir işleminiz olursa yardımcı olmaktan memnuniyet duyarım.",
            'status': "Durum bilgisini kontrol ediyorum...",
            'error': "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."
        }

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
        """Extract date range from text with typo tolerance"""
        text = text.lower()
        
        # Common typo variations for date-related words
        date_keywords = {
            "geçen hafta": ["geçen hfta", "gecen hafta", "gçn hafta", "geçn hfta"],
            "bu hafta": ["bu hfta", "b hafta", "bu hfata"],
            "önceki hafta": ["onceki hafta", "öncki hfta", "oncki hafta"],
            "arası": ["arasi", "aras", "arasinda", "arasnda"],
            "haftası": ["haftasi", "haftasnn", "hftası", "hftasi"]
        }
        
        # Fix common typos in the text
        for correct_form, variations in date_keywords.items():
            # Use fuzzy matching to find the best match among variations
            result = process.extractOne(text, variations + [correct_form], scorer=fuzz.partial_ratio)
            if result and result[1] > 80:
                text = text.replace(result[0], correct_form)
        
        # Check for "last week" or "previous week" with fuzzy matching
        if any(fuzz.partial_ratio(word, text) > 80 for word in ["geçen hafta", "önceki hafta"]):
            today = datetime.now()
            monday = today - timedelta(days=today.weekday() + 7)
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        # Check for "this week" with fuzzy matching
        if any(fuzz.partial_ratio("bu hafta", part) > 80 for part in text.split()):
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        # Check for "X haftası" format with fuzzy matching
        hafta_pattern = r'(\d{1,2}\s+[a-zışğüçö]+\s+\d{4})\s*h[af]*t[aı]s[ıi]'
        hafta_match = re.search(hafta_pattern, text)
        if hafta_match:
            date_str = hafta_match.group(1)
            start_date = self.parse_date(date_str)
            if start_date:
                if start_date.weekday() != 0:
                    start_date = start_date - timedelta(days=start_date.weekday())
                end_date = start_date + timedelta(days=6)
                return start_date, end_date
            
        # Look for date range with separator (with fuzzy matching for separators)
        separators = [" - ", " ile ", " arası ", " arasındaki ", " dan ", " den "]
        for sep in separators:
            if any(fuzz.partial_ratio(sep.strip(), part) > 80 for part in text.split()):
                parts = text.split(sep)
                if len(parts) == 2:
                    start_date = self.parse_date(parts[0])
                    end_date = self.parse_date(parts[1])
                    if start_date and end_date:
                        return start_date, end_date
        
        # Try to find a single date
        date = self.parse_date(text)
        if date:
            monday = date - timedelta(days=date.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
            
        return None, None
        
    def _format_date_turkish(self, date):
        """Format a date in Turkish"""
        turkish_month_names = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
            5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
            9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        return f"{date.day} {turkish_month_names[date.month]} {date.year}"

    def process_command(self, text):
        """Process commands related to PDF processing with typo tolerance"""
        text = text.lower().strip()
        
        # Known command templates
        command_templates = [
            "geçen haftanın faturalarını işle",
            "geçen hafta pdfleri işle",
            "bu haftanın belgelerini işle",
            "bu hafta pdfleri işle",
            "haftasının pdflerini işle",
            "arası pdfleri işle"
        ]
        
        # First, try to match the overall command structure
        result = process.extractOne(text, command_templates, scorer=fuzz.partial_ratio)
        if not result or result[1] <= 75:  # If no good match found, return None to fall back to help message
            return None
            
        # Extract date range with typo tolerance
        start_date, end_date = self.extract_date_range(text)
        if not start_date or not end_date:
            return ("Tarih aralığını anlayamadım. İşte bazı örnek kullanımlar:\n\n" + \
                   "- 'Geçen haftanın faturalarını işle'\n" + \
                   "- '15 Ocak 2025 - 21 Ocak 2025 arası faturaları process et'\n" + \
                   "- '15 Ocak 2025 haftasının PDFlerini işle'\n" + \
                   "- 'Bu haftanın belgelerini işle'\n" + \
                   "- '15/01/2025 - 21/01/2025 arası PDFleri işle'")
        
        # Format date range for messages in Turkish
        date_range = f"{self._format_date_turkish(start_date)} - {self._format_date_turkish(end_date)}"
        
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
            self.gui.log_message(f"Processing PDFs for week {date_range}")
            self.gui.update_status("="*50)
            self.gui.update_status(f"Processing PDFs for Week: {date_range}")
            self.gui.update_status("="*50)
            
            # Get PDFs for the date range
            pdfs, skipped = self.gui.web_automation.search_and_download_pdf(target_week=(start_date, end_date))
            
            if not pdfs and not skipped:
                self.gui.log_message(f"No PDFs found for {date_range}")
                self.gui.update_status(f"No PDFs found for {date_range}")
                self.gui.is_processing = False
                self.gui.update_processing_state()
                return f"{date_range} aralığında hiç PDF bulunamadı."
                
            skipped_count = len(skipped) if skipped else 0
            skipped_message = ""
            
            if skipped:
                self.gui.update_status("\nSkipped PDFs:")
                skipped_message = "\n\nAtlanan PDFler:"
                for pdf_name, reason in skipped:
                    self.gui.update_status(f"- {pdf_name}: {reason}")
                    skipped_message += f"\n- {pdf_name}: {reason}"
            
            if pdfs:
                # Process the PDFs
                self.gui.process_pdf_list(pdfs)
                return f"{date_range} aralığında {len(pdfs)} PDF işlendi.{skipped_message}\nDetaylar için durum panelini kontrol edin."
            else:
                self.gui.is_processing = False
                self.gui.update_processing_state()
                if skipped:
                    return f"{date_range} aralığında işlenecek yeni PDF bulunamadı.{skipped_message}"
                else:
                    return f"{date_range} aralığında hiç PDF bulunamadı."
            
        except Exception as e:
            self.gui.handle_error(e)
            self.gui.is_processing = False
            self.gui.update_processing_state()
            return f"PDF işleme sırasında bir hata oluştu: {str(e)}"
        
    def get_response(self, text):
        """Main entry point for getting responses"""
        if not text:
            return self.responses['greeting']
            
        text = text.lower().strip()
        
        # Check for basic interactions first
        if self._is_greeting(text):
            return self._handle_greeting(text)
        elif self._is_thanks(text):
            return self.responses['thanks']
        elif self._is_goodbye(text):
            return self.responses['goodbye']
        elif self._is_help(text):
            return self.responses['help']
        elif self._is_status_request(text):
            return self._get_status_info()
            
        # If no basic interaction matches, try to process as a command
        command_response = self.process_command(text)
        if command_response is not None:
            return command_response
            
        # If nothing matches, return help message
        return self.responses['help']
        
    def _is_greeting(self, text):
        """Check if the message is a greeting using fuzzy matching"""
        greetings = ["hi", "hello", "merhaba", "selam", "hey", "how are you", "nasılsın"]
        result = process.extractOne(text, greetings)
        return result[1] > 80 if result else False
        
    def _handle_greeting(self, text):
        """Handle greeting messages"""
        if "how are you" in text or "nasılsın" in text:
            return self.responses['how_are_you']
        return self.responses['greeting']
        
    def _is_thanks(self, text):
        """Check if the message is expressing thanks using fuzzy matching"""
        thanks_words = ["teşekkür", "tesekkur", "thanks", "thank you", "sağol", "sagol", "tşk"]
        result = process.extractOne(text, thanks_words)
        return result[1] > 80 if result else False
        
    def _is_goodbye(self, text):
        """Check if the message is a goodbye using fuzzy matching"""
        goodbye_words = ["güle güle", "hoşça kal", "görüşürüz", "bye", "goodbye", "see you", "bb", "by"]
        result = process.extractOne(text, goodbye_words)
        return result[1] > 80 if result else False
        
    def _is_help(self, text):
        """Check if the message is asking for help using fuzzy matching"""
        help_words = ["help", "yardım", "nasıl", "örnek", "komut", "yrdm"]
        result = process.extractOne(text, help_words)
        return result[1] > 80 if result else False
        
    def _is_status_request(self, text):
        """Check if the message is asking for status using fuzzy matching"""
        status_words = ["status", "durum", "rapor", "report", "drm"]
        result = process.extractOne(text, status_words)
        return result[1] > 80 if result else False

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

    def process_message(self, text):
        """Main entry point for processing user messages"""
        if not text:
            return "Merhaba! Size nasıl yardımcı olabilirim?"
            
        text = text.lower().strip()
        
        # Handle greetings
        if self._is_greeting(text):
            return self._handle_greeting(text)
            
        # Handle PDF processing commands
        pdf_response = self.process_command(text)
        if pdf_response is not None:
            return pdf_response
            
        # Handle general queries
        return ("Size PDF işleme konusunda yardımcı olabilirim. Örnek komutlar:\n\n"
               "- 'Geçen haftanın faturalarını işle'\n"
               "- '15 Ocak 2025 haftasının PDFlerini işle'\n"
               "- 'Bu haftanın belgelerini işle'\n"
               "- '15/01/2025 - 21/01/2025 arası PDFleri işle'") 