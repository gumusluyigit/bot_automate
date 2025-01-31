import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry  # For date picker
from datetime import datetime, timedelta
import os
import json
from pdf_processor import PDFProcessor
from web_automation import WebAutomation
from O365 import Account
from email_handler import EmailHandler
import shutil
from database import init_db
from chatbot import Chatbot
import re

class ReceiptAutomationGUI:
    def __init__(self, root):
        """Initialize the GUI"""
        self.root = root
        self.root.title("Receipt Automation")
        self.root.geometry("1000x800")
        
        # Initialize variables
        self.sender_email = tk.StringVar()
        self.internal_email = tk.StringVar()
        self.app_password = tk.StringVar()
        self.week_var = tk.StringVar()
        self.is_processing = False
        
        # Setup download directory
        self.download_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Load config
        self.load_config()
        
        # Setup logging
        self.log_file = "automation_log.txt"
        
        # Initialize components
        self.setup_gui()
        
        # Always create an EmailHandler for database access
        self.email_handler = EmailHandler(
            self.sender_email.get() or "temp@example.com",
            self.internal_email.get() or "temp@example.com"
        )
        
        # Initialize web automation
        self.web_automation = WebAutomation(self.download_dir)
        self.web_automation.email_handler = self.email_handler
            
        # Force initial update of pending requests
        self.update_pending_requests_tab()
        
        self.log_message("Application started")

    def setup_gui(self):
        """Setup the GUI components"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create tabs
        self.main_tab = ttk.Frame(self.notebook)
        self.pending_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.logs_tab = ttk.Frame(self.notebook)
        self.chatbot_tab = ttk.Frame(self.notebook)  # Add chat tab
        
        self.notebook.add(self.main_tab, text='Main')
        self.notebook.add(self.pending_tab, text='Pending Requests')
        self.notebook.add(self.settings_tab, text='Settings')
        self.notebook.add(self.logs_tab, text='Logs')
        self.notebook.add(self.chatbot_tab, text='Chat')  # Add chat tab
        
        # Setup each tab
        self.setup_main_tab()
        self.setup_pending_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()
        self.setup_chat_tab()  # Setup chat tab
        
        # Setup auto-refresh for pending requests
        self.setup_auto_refresh()

    def setup_main_tab(self):
        """Setup the main receipt processing tab"""
        # Processing Options
        options_frame = ttk.LabelFrame(self.main_tab, text="Processing Options", padding="10")
        options_frame.pack(fill='x', padx=10, pady=5)
        
        # Demo Reset Button
        reset_frame = ttk.Frame(options_frame)
        reset_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(reset_frame, text="Reset Environment for Demo", 
                  command=self.reset_environment).pack(side='right', padx=5)
        
        # Weekly Processing Frame
        weekly_frame = ttk.LabelFrame(options_frame, text="Weekly Processing", padding="5")
        weekly_frame.pack(fill='x', padx=5, pady=5)
        
        # Last Week Button
        ttk.Button(weekly_frame, text="Process Last Week's Receipts", 
                  command=self.process_last_week).pack(side='left', padx=5)
        
        # Custom Week Frame
        custom_frame = ttk.LabelFrame(weekly_frame, text="Custom Week", padding="5")
        custom_frame.pack(side='left', padx=20)
        
        # Week selection
        ttk.Label(custom_frame, text="Select Week:").pack(side='left', padx=5)
        self.week_var = tk.StringVar()
        weeks = self._get_recent_weeks()
        week_dropdown = ttk.Combobox(custom_frame, textvariable=self.week_var, 
                                   values=[week[0] for week in weeks], width=50,
                                   state='readonly')  # Make dropdown readonly
        week_dropdown.pack(side='left', padx=5)
        
        ttk.Button(custom_frame, text="Process Selected Week", 
                  command=self.process_selected_week).pack(side='left', padx=5)
        
        # Status Display
        status_frame = ttk.LabelFrame(self.main_tab, text="Status", padding="10")
        status_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Status text with scrollbar
        self.status_text = tk.Text(status_frame, height=20, width=80, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, 
                                command=self.status_text.yview)
        
        self.status_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.status_text['yscrollcommand'] = scrollbar.set
        self.status_text.config(state=tk.DISABLED)
        
    def _get_recent_weeks(self):
        """Generate list of recent weeks for dropdown"""
        weeks = []
        today = datetime.now()
        current_year = today.year
        
        # Turkish month names
        turkish_months = {
            1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
            5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
            9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
        }
        
        # Start from 12 weeks ago
        for i in range(12, -1, -1):
            # Get Monday of each week
            monday = today - timedelta(days=today.weekday() + 7 * i)
            sunday = monday + timedelta(days=6)
            
            # Format dates with Turkish months
            monday_str = f"{monday.day} {turkish_months[monday.month]} {monday.year}"
            sunday_str = f"{sunday.day} {turkish_months[sunday.month]} {sunday.year}"
            
            # Store both display string and actual dates
            week_str = f"{monday_str} - {sunday_str}"
            
            # Store as tuple with display string and actual dates for processing
            weeks.append((week_str, monday, sunday))
            
        return weeks
        
    def process_last_week(self):
        """Process PDFs from last week"""
        try:
            if self.is_processing:
                messagebox.showwarning("Warning", "Please wait for the current processing to complete before selecting a new date range.")
                return
                
            if not self.check_email_settings():
                return
                
            # Get last week's date range
            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            
            self.is_processing = True
            self.update_processing_state()
            
            self.log_message(f"Processing PDFs for last week ({last_monday.strftime('%d %B %Y')} to {last_sunday.strftime('%d %B %Y')})")
            self.update_status("="*50)
            self.update_status(f"Processing Last Week's PDFs: {last_monday.strftime('%d %B %Y')} "
                             f"to {last_sunday.strftime('%d %B %Y')}")
            self.update_status("="*50)
            
            # Get PDFs for last week
            pdfs, skipped = self.web_automation.search_and_download_pdf(target_week=(last_monday, last_sunday))
            
            if not pdfs and not skipped:
                self.log_message("No PDFs found for the specified week")
                self.update_status("No PDFs found for the specified week")
                self.is_processing = False
                self.update_processing_state()
                return
                
            if skipped:
                self.update_status("\nSkipped PDFs:")
                for pdf_name, reason in skipped:
                    self.update_status(f"- {pdf_name}: {reason}")
                
            if pdfs:
                self.process_pdf_list(pdfs)
            else:
                self.update_status("\nNo new PDFs to process")
                self.is_processing = False
                self.update_processing_state()
            
        except Exception as e:
            self.handle_error(e)
            self.is_processing = False
            self.update_processing_state()
            
    def process_selected_week(self):
        """Process PDFs for the selected week"""
        try:
            if self.is_processing:
                return
            
            # Get selected week
            selected_week = self.week_var.get()
            if not selected_week:
                messagebox.showerror("Error", "Please select a week first")
                return
            
            # Turkish month names mapping
            turkish_months = {
                'Ocak': '01', 'Şubat': '02', 'Mart': '03', 'Nisan': '04',
                'Mayıs': '05', 'Haziran': '06', 'Temmuz': '07', 'Ağustos': '08',
                'Eylül': '09', 'Ekim': '10', 'Kasım': '11', 'Aralık': '12'
            }
            
            # Parse week string to get start and end dates
            week_match = re.match(r'(\d{1,2}) ([A-Za-zşğüçöıİ]+) (\d{4}) - (\d{1,2}) ([A-Za-zşğüçöıİ]+) (\d{4})', selected_week)
            if not week_match:
                messagebox.showerror("Error", "Invalid week format")
                return
            
            start_day, start_month_tr, start_year, end_day, end_month_tr, end_year = week_match.groups()
            
            # Convert Turkish month names to numbers
            if start_month_tr not in turkish_months or end_month_tr not in turkish_months:
                messagebox.showerror("Error", "Invalid month name")
                return
            
            # Create date strings in the format YYYY-MM-DD
            start_date_str = f"{start_year}-{turkish_months[start_month_tr]}-{int(start_day):02d}"
            end_date_str = f"{end_year}-{turkish_months[end_month_tr]}-{int(end_day):02d}"
            
            # Parse dates
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid date format: {str(e)}")
                return
            
            # Update status
            self.is_processing = True
            self.update_processing_state()
            
            # Log the start of processing
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.log_message(f"\n{timestamp}: ==================================================")
            self.log_message(f"{timestamp}: Processing PDFs for Week: {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}")
            self.log_message(f"{timestamp}: ==================================================")
            
            # Search and download PDFs
            downloaded_pdfs, skipped_pdfs = self.web_automation.search_and_download_pdf((start_date, end_date))
            
            if not downloaded_pdfs and not skipped_pdfs:
                message = f"No PDFs found for the week of {start_date.strftime('%d %B %Y')}"
                self.log_message(f"{timestamp}: {message}")
                self.update_status(message)
                return
            
            # Log found PDFs
            self.log_message(f"{timestamp}: Found {len(downloaded_pdfs) + len(skipped_pdfs)} PDF(s) within target week\n")
            self.update_status(f"\nFound {len(downloaded_pdfs) + len(skipped_pdfs)} PDF(s) within target week\n")
            
            # Process downloaded PDFs
            successful = 0
            failed = 0
            skipped = len(skipped_pdfs)
            
            for i, pdf_path in enumerate(downloaded_pdfs, 1):
                try:
                    filename = os.path.basename(pdf_path)
                    self.log_message(f"{timestamp}: Processing PDF ({i}/{len(downloaded_pdfs)}): {filename}")
                    self.update_status(f"Processing PDF ({i}/{len(downloaded_pdfs)}): {filename}")
                    
                    # Validate PDF
                    if not PDFProcessor.validate_pdf(pdf_path):
                        self.log_message(f"{timestamp}: PDF validation failed: {filename}")
                        self.update_status(f"PDF validation failed: {filename}")
                        failed += 1
                        continue
                        
                    self.log_message(f"{timestamp}: PDF validation successful!")
                    self.update_status("PDF validation successful!")
                    
                    # Extract company name and check if it's already in pending requests or processed
                    company_name = os.path.splitext(filename)[0].split('_')[0]
                    
                    # Check if this file is already in pending requests
                    if self.email_handler.is_invoice_pending(company_name):
                        error_msg = f"Skipping {filename} - Already in pending requests"
                        self.log_message(f"{timestamp}: {error_msg}")
                        self.update_status(error_msg)
                        skipped += 1
                        continue
                    
                    # Check if this file was already processed (email sent)
                    if self.email_handler.check_if_sent(company_name):
                        error_msg = f"Skipping {filename} - Email already sent"
                        self.log_message(f"{timestamp}: {error_msg}")
                        self.update_status(error_msg)
                        skipped += 1
                        continue
                    
                    # Check if we have an email address for this company
                    company_email = self.email_handler.get_email_from_database(company_name)
                    
                    if company_email:
                        # If we have an email, send it directly
                        if self.email_handler.send_receipt_to_company(company_email, company_name, pdf_path):
                            self.log_message(f"{timestamp}: Successfully sent email to {company_email}")
                            self.update_status(f"Successfully sent email to {company_email}")
                            # Only move to processed after successful email sending
                            self.web_automation.mark_as_processed(pdf_path)
                            successful += 1
                        else:
                            error_msg = f"Failed to send email to {company_email}"
                            self.log_message(f"{timestamp}: {error_msg}")
                            self.update_status(error_msg)
                            failed += 1
                    else:
                        # If no email found, add to pending requests
                        if self.email_handler.add_to_pending(invoice_number=company_name, company_name=company_name, 
                                                           pdf_path=pdf_path, period_start=start_date, period_end=end_date):
                            self.log_message(f"{timestamp}: Added to pending requests")
                            self.update_status("Added to pending requests")
                            successful += 1
                            # Do NOT move to processed folder - keep in downloads until email is sent
                        else:
                            error_msg = f"Error processing {filename}: Failed to add to pending requests"
                            self.log_message(f"{timestamp}: {error_msg}")
                            self.update_status(error_msg)
                            failed += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {os.path.basename(pdf_path)}: {str(e)}"
                    self.log_message(f"{timestamp}: {error_msg}")
                    self.update_status(error_msg)
                    failed += 1
            
            # Log skipped PDFs
            if skipped_pdfs:
                self.log_message(f"\n{timestamp}: Skipped PDFs (already processed):")
                self.update_status("\nSkipped PDFs (already processed):")
                for pdf_path in skipped_pdfs:
                    filename = os.path.basename(pdf_path)
                    self.log_message(f"{timestamp}: - {filename}")
                    self.update_status(f"- {filename}")
            
            # Update status with final counts
            self.log_message(f"\n{timestamp}: ==================================================")
            self.update_status("\n==================================================")
            summary = f"Processing completed: {successful} successful, {skipped} skipped, {failed} failed"
            self.log_message(f"{timestamp}: {summary}")
            
            # Update status display with bullet points
            self.update_status("\nProcessing Summary:")
            self.update_status(f"• Successfully processed: {successful}")
            self.update_status(f"• Already processed (skipped): {skipped}")
            self.update_status(f"• Failed to process: {failed}")
            
            # Update pending requests tab
            self.update_pending_requests_tab()
            
        except Exception as e:
            self.handle_error(e)
        finally:
            self.is_processing = False
            self.update_processing_state()
            
    def process_pdf_list(self, pdf_paths: list):
        """Process a list of PDFs"""
        try:
            total = len(pdf_paths)
            processed = 0
            failed = 0
            skipped = 0
            
            # Show total PDFs found
            self.update_status(f"Found {total} PDF(s) within target week\n")
            
            for pdf_path in pdf_paths:
                try:
                    pdf_name = os.path.basename(pdf_path)
                    self.update_status(f"Processing PDF ({processed + skipped + failed + 1}/{total}): {pdf_name}")
                    
                    if not os.path.exists(pdf_path):
                        raise Exception("PDF file not found - it may have been removed")
                        
                    if not PDFProcessor.validate_pdf(pdf_path):
                        raise Exception("Invalid PDF file")
                    self.update_status("PDF validation successful!")
                    
                    try:
                        invoice_info = PDFProcessor.extract_invoice_info(pdf_path)
                    except Exception as e:
                        self.update_status(f"Error extracting information from PDF: {str(e)}")
                        failed += 1
                        continue
                        
                    invoice_number = invoice_info.get('invoice_number')
                    company_name = invoice_info.get('company_name', 'Unknown Company')
                    period_start = invoice_info.get('period_start')
                    period_end = invoice_info.get('period_end')
                    
                    if not invoice_number:
                        raise Exception("Could not extract invoice number from PDF")
                    
                    # Check if invoice is already in pending requests using database
                    if self.email_handler.is_invoice_pending(invoice_number):
                        self.update_status(f"Skipping {pdf_name} - Invoice {invoice_number} is already in pending requests")
                        skipped += 1
                        continue
                    
                    # Check if receipt was already sent
                    if self.email_handler.check_if_sent(invoice_number):
                        self.update_status(f"Skipping {pdf_name} - Receipt for invoice {invoice_number} was already sent")
                        skipped += 1
                        continue
                    
                    # Check database for email address
                    company_email = self.email_handler.get_email_from_database(invoice_number)
                    
                    if company_email:
                        # Send receipt directly if we have the email
                        if self.email_handler.send_receipt_to_company(company_email, invoice_number, pdf_path):
                            self.update_status(f"Sent receipt to {company_email}")
                            # Move file to processed folder after successful email sending
                            if self.web_automation.mark_as_processed(pdf_path):
                                self.update_status(f"Moved {pdf_name} to processed folder")
                            processed += 1
                        else:
                            raise Exception(f"Failed to send receipt to {company_email}")
                    else:
                        # Add to pending requests and request email from internal department
                        if self.email_handler.add_to_pending(invoice_number, company_name, pdf_path, period_start, period_end):
                            self.update_status(f"Added invoice {invoice_number} to pending requests")
                            if self.email_handler.request_company_email(invoice_number, f"Email needed for invoice {invoice_number}", pdf_path):
                                self.update_status("Sent email request to internal department")
                                processed += 1
                                # Update pending requests tab
                                self.update_pending_requests_tab()
                            else:
                                raise Exception("Failed to send email request to internal department")
                        else:
                            raise Exception("Failed to add to pending requests")
                    
                except Exception as e:
                    self.update_status(f"Error processing {pdf_name}: {str(e)}")
                    failed += 1
                    
            self.update_status("\n" + "="*50)
            self.update_status(f"Processing completed: {processed} successful, {skipped} skipped, {failed} failed")
            
            # Final update of pending requests tab
            self.update_pending_requests_tab()
            
            self.is_processing = False
            self.update_processing_state()
            
        except Exception as e:
            self.handle_error(e)
            self.is_processing = False
            self.update_processing_state()
            
    def check_email_settings(self) -> bool:
        """Check if email settings are configured"""
        if not self.sender_email.get() or not self.internal_email.get():
            messagebox.showerror("Error", "Please configure email settings first!")
            self.notebook.select(2)  # Switch to settings tab
            return False
            
        # Update email handler with current settings
        self.email_handler.sender_email = self.sender_email.get()
        self.email_handler.internal_email = self.internal_email.get()
        return True
        
    def handle_error(self, error: Exception):
        """Handle and display errors"""
        error_message = f"Error: {str(error)}"
        self.log_message(f"ERROR: {error_message}")
        self.update_status(f"\nERROR: {error_message}")
        messagebox.showerror("Error", error_message)

    def setup_settings_tab(self):
        """Setup the settings tab"""
        # Email Settings Frame
        email_frame = ttk.LabelFrame(self.settings_tab, text="Email Settings", padding="10")
        email_frame.pack(fill='x', padx=10, pady=5)
        
        # Sender Email
        sender_frame = ttk.Frame(email_frame)
        sender_frame.pack(fill='x', pady=5)
        ttk.Label(sender_frame, text="Sender Email:").pack(side='left', padx=5)
        ttk.Entry(sender_frame, textvariable=self.sender_email, width=40).pack(side='left', padx=5)
        
        # Internal Email
        internal_frame = ttk.Frame(email_frame)
        internal_frame.pack(fill='x', pady=5)
        ttk.Label(internal_frame, text="Internal Email:").pack(side='left', padx=5)
        ttk.Entry(internal_frame, textvariable=self.internal_email, width=40).pack(side='left', padx=5)
        
        # Gmail App Password
        password_frame = ttk.Frame(email_frame)
        password_frame.pack(fill='x', pady=5)
        ttk.Label(password_frame, text="Gmail App Password:").pack(side='left', padx=5)
        password_entry = ttk.Entry(password_frame, textvariable=self.app_password, show="*", width=40)
        password_entry.pack(side='left', padx=5)
        
        # Buttons Frame
        buttons_frame = ttk.Frame(email_frame)
        buttons_frame.pack(fill='x', pady=10)
        
        # Save Settings Button
        ttk.Button(buttons_frame, text="Save Settings", 
                  command=self.save_settings).pack(side='left', padx=5)
        
        # Test Settings Button
        ttk.Button(buttons_frame, text="Test Settings", 
                  command=self.test_email_settings).pack(side='left', padx=5)
                  
    def save_settings(self):
        """Save and apply email settings"""
        try:
            if self.save_config():
                # Initialize or update email handler
                self.email_handler = EmailHandler(
                    self.sender_email.get(),
                    self.internal_email.get()
                )
                if self.app_password.get():
                    self.email_handler.save_credentials(self.app_password.get())
                
                self.log_message("Settings saved successfully")
                messagebox.showinfo("Success", "Settings saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save settings")
        except Exception as e:
            error_msg = f"Failed to save settings: {str(e)}"
            self.log_message(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

    def load_config(self):
        """Load email configuration from file"""
        try:
            if os.path.exists('email_config.json'):
                with open('email_config.json', 'r') as f:
                    config = json.load(f)
                    self.sender_email.set(config.get('sender_email', ''))
                    self.internal_email.set(config.get('internal_email', ''))
                    self.app_password.set(config.get('app_password', ''))
        except Exception as e:
            self.log_message(f"Error loading config: {str(e)}")
            
    def save_config(self):
        """Save email configuration to file"""
        try:
            config = {
                'sender_email': self.sender_email.get(),
                'internal_email': self.internal_email.get(),
                'app_password': self.app_password.get()
            }
            with open('email_config.json', 'w') as f:
                json.dump(config, f)
            return True
        except Exception as e:
            self.log_message(f"Error saving config: {str(e)}")
            return False

    def test_email_settings(self):
        """Test email settings"""
        try:
            if not self.app_password.get():
                self.log_message("ERROR: Gmail App Password not provided")
                messagebox.showerror("Error", "Please enter your Gmail App Password!")
                return
                
            if not self.email_handler:
                self.email_handler = EmailHandler(
                    self.sender_email.get(),
                    self.internal_email.get()
                )
                self.email_handler.save_credentials(self.app_password.get())
            
            if self.email_handler.authenticate():
                self.log_message("Gmail authentication successful")
                messagebox.showinfo("Success", "Gmail authentication successful!")
            else:
                self.log_message("ERROR: Failed to authenticate with Gmail")
                messagebox.showerror("Error", "Failed to authenticate with Gmail")
        except Exception as e:
            error_msg = f"Failed to test settings: {str(e)}"
            self.log_message(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

    def update_status(self, message):
        """Update the status display with a new message"""
        try:
            # Get current timestamp
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Format the message
            if message.startswith('=='):
                # Section separator
                formatted_message = f"\n{message}\n"
            elif message.startswith('•'):
                # Bullet point
                formatted_message = f"{timestamp}: {message}\n"
            elif message.startswith('-'):
                # List item
                formatted_message = f"{timestamp}:   {message}\n"
            else:
                # Normal message
                formatted_message = f"{timestamp}: {message}\n"
            
            # Update status text widget
            if hasattr(self, 'status_text'):
                self.status_text.configure(state='normal')
                self.status_text.insert('end', formatted_message)
                self.status_text.see('end')
                self.status_text.configure(state='disabled')
                
            # Force GUI update
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error updating status: {str(e)}")

    def setup_pending_tab(self):
        """Setup the pending requests tab"""
        # Create treeview for pending requests
        columns = ('Invoice', 'Company', 'Request Time', 'PDF Path', 'Status')
        self.pending_tree = ttk.Treeview(self.pending_tab, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            self.pending_tree.heading(col, text=col)
            self.pending_tree.column(col, width=100)  # Adjust width as needed
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.pending_tab, orient='vertical', command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=scrollbar.set)
        
        # Email entry and send button
        email_frame = ttk.Frame(self.pending_tab)
        ttk.Label(email_frame, text="Email:").pack(side='left', padx=5)
        self.pending_email_entry = ttk.Entry(email_frame, width=40)
        self.pending_email_entry.pack(side='left', padx=5)
        ttk.Button(email_frame, text="Send", command=self.send_pending_email).pack(side='left', padx=5)
        
        # Pack everything
        self.pending_tree.pack(fill='both', expand=True, padx=10, pady=5)
        scrollbar.pack(side='right', fill='y')
        email_frame.pack(fill='x', padx=10, pady=5)
        
    def update_pending_requests_tab(self):
        """Update the pending requests tab with current data"""
        try:
            # Store current selection
            selected_items = []
            for item_id in self.pending_tree.selection():
                item = self.pending_tree.item(item_id)
                selected_items.append(item['values'][0])  # Store invoice number
            
            # Use existing email handler to get pending requests
            pending_requests = self.email_handler.get_pending_requests()
            
            # Clear existing items
            for item in self.pending_tree.get_children():
                self.pending_tree.delete(item)
                
            # Add pending requests to treeview and restore selection
            for request in pending_requests:
                invoice_number, company_name, request_time, pdf_path, status, email, period_start, period_end = request
                item_id = self.pending_tree.insert('', 'end', values=(
                    invoice_number,
                    company_name,
                    request_time,
                    pdf_path,
                    status
                ))
                # Restore selection if this was previously selected
                if invoice_number in selected_items:
                    self.pending_tree.selection_add(item_id)
                    
        except Exception as e:
            self.log_message(f"Error updating pending requests tab: {str(e)}")
            
    def send_pending_email(self):
        """Send email for selected pending request"""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a pending request first.")
            return
            
        item = self.pending_tree.item(selection[0])
        invoice_number = item['values'][0]
        pdf_path = item['values'][3]
        
        # Get email from entry
        email = self.pending_email_entry.get().strip()
        if not email:
            messagebox.showwarning("No Email", "Please enter an email address.")
            return
            
        # Update email in database
        if not self.email_handler.update_email(invoice_number, email):
            messagebox.showerror("Error", "Failed to update email address.")
            return
            
        # Send email
        subject = f"Invoice {invoice_number}"
        body = f"Please find attached invoice {invoice_number}."
        if self.email_handler.send_email(email, subject, body, [pdf_path]):
            # Move file to processed folder after successful email sending
            if self.web_automation.mark_as_processed(pdf_path):
                self.update_status(f"Moved {os.path.basename(pdf_path)} to processed folder")
            
            # Mark the request as sent in the database
            self.email_handler.mark_as_sent(invoice_number, email, "sent")
            
            # Clear the email entry
            self.pending_email_entry.delete(0, tk.END)
            
            messagebox.showinfo("Success", f"Email sent successfully to {email}")
            
            # Update the pending requests display
            self.update_pending_requests_tab()
        else:
            messagebox.showerror("Error", "Failed to send email.")
            
    def setup_auto_refresh(self):
        """Setup automatic refresh of pending requests tab"""
        def refresh():
            # Only update if we're on the pending tab and no item is being edited
            if (self.notebook.select() == str(self.pending_tab) and 
                not self.pending_email_entry.focus_get()):  # Don't refresh if user is entering email
                self.update_pending_requests_tab()
            # Schedule next refresh
            self.root.after(1000, refresh)  # Refresh every second for better responsiveness
            
        # Start the refresh cycle immediately
        refresh()

    def setup_logs_tab(self):
        """Setup the logs tab"""
        # Controls frame
        controls_frame = ttk.Frame(self.logs_tab, padding="10")
        controls_frame.pack(fill='x', padx=10, pady=5)
        
        # Clear logs button
        ttk.Button(controls_frame, text="Clear Logs", 
                  command=self.clear_logs).pack(side='left', padx=5)
        
        # Export logs button
        ttk.Button(controls_frame, text="Export Logs", 
                  command=self.export_logs).pack(side='left', padx=5)
        
        # Logs display
        logs_frame = ttk.LabelFrame(self.logs_tab, text="Activity Logs", padding="10")
        logs_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Logs text with scrollbar
        self.logs_text = tk.Text(logs_frame, height=30, width=100, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, 
                                command=self.logs_text.yview)
        
        self.logs_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.logs_text['yscrollcommand'] = scrollbar.set
        self.logs_text.config(state=tk.DISABLED)
        
        # Load existing logs
        self.load_logs()
        
    def log_message(self, message: str):
        """Log a message to both file and logs tab"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}\n"
        
        # Write to file
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        # Update logs display
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.see(tk.END)
        self.logs_text.config(state=tk.DISABLED)
        
    def load_logs(self):
        """Load existing logs from file"""
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                logs = f.read()
                self.logs_text.config(state=tk.NORMAL)
                self.logs_text.delete('1.0', tk.END)
                self.logs_text.insert(tk.END, logs)
                self.logs_text.config(state=tk.DISABLED)
                
    def clear_logs(self):
        """Clear all logs"""
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear all logs?"):
            # Clear file
            with open(self.log_file, 'w') as f:
                f.write("")
            
            # Clear display
            self.logs_text.config(state=tk.NORMAL)
            self.logs_text.delete('1.0', tk.END)
            self.logs_text.config(state=tk.DISABLED)
            
            self.log_message("Logs cleared")
            
    def export_logs(self):
        """Export logs to a timestamped file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = f"logs_export_{timestamp}.txt"
        
        try:
            shutil.copy2(self.log_file, export_file)
            self.log_message(f"Logs exported to {export_file}")
            messagebox.showinfo("Success", f"Logs exported to {export_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {str(e)}")

    def reset_environment(self):
        """Reset the environment for demonstration"""
        try:
            if self.web_automation.reset_for_demo():
                # Create a fresh EmailHandler instance
                temp_handler = EmailHandler(
                    self.sender_email.get() or "temp@example.com",
                    self.internal_email.get() or "temp@example.com"
                )
                
                # Clear the database tables
                temp_handler.db.clear_all_tables()
                
                # Reinitialize email handler with current or temporary settings
                self.email_handler = EmailHandler(
                    self.sender_email.get() or "temp@example.com",
                    self.internal_email.get() or "temp@example.com"
                )
                
                # Update web automation with new email handler
                self.web_automation.email_handler = self.email_handler
                
                # Update the pending requests tab
                self.update_pending_requests_tab()
                
                self.update_status("\nEnvironment reset successfully. Ready for demo!")
                messagebox.showinfo("Success", "Environment has been reset successfully!")
            else:
                messagebox.showerror("Error", "Failed to reset environment. Check the logs for details.")
        except Exception as e:
            self.handle_error(e)

    def update_processing_state(self):
        """Update UI elements based on processing state"""
        state = 'disabled' if self.is_processing else 'normal'
        for child in self.main_tab.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, (ttk.Button, ttk.Combobox)):
                        widget.configure(state=state)

    def setup_chat_tab(self):
        """Setup the chat interface tab"""
        # Create main chat frame
        chat_frame = ttk.Frame(self.chatbot_tab)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create chat display area
        self.chat_display = tk.Text(chat_frame, wrap=tk.WORD, height=20, width=50)
        self.chat_display.pack(fill='both', expand=True, padx=5, pady=5)
        self.chat_display.config(state='disabled')
        
        # Create input frame
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', padx=5, pady=5)
        
        # Create input field
        self.chat_input = ttk.Entry(input_frame)
        self.chat_input.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.chat_input.bind('<Return>', self.send_message)
        
        # Create send button
        send_button = ttk.Button(input_frame, text='Send', command=self.send_message)
        send_button.pack(side='right')
        
        # Create clear button
        clear_button = ttk.Button(chat_frame, text='Clear Chat', command=self.clear_chat)
        clear_button.pack(pady=5)
        
        # Initialize chatbot when tab is selected
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        
    def on_tab_change(self, event):
        """Initialize chatbot when chat tab is selected"""
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")
        
        if tab_text == "Chat" and not hasattr(self, 'chatbot'):
            self.initialize_chatbot()
            
    def initialize_chatbot(self):
        """Initialize the chatbot"""
        self.update_chat_display("Initializing chatbot... Please wait...\n")
        self.chatbot = Chatbot()
        self.chatbot.set_gui(self)  # Pass GUI reference to chatbot
        self.update_chat_display("Chatbot is ready! You can start chatting.\n")
        self.update_chat_display("Merhaba! Size nasıl yardımcı olabilirim?\n\n")
        
    def send_message(self, event=None):
        """Send a message to the chatbot and display the response"""
        if not hasattr(self, 'chatbot'):
            self.update_chat_display("Please wait for the chatbot to initialize...\n")
            return
            
        user_message = self.chat_input.get().strip()
        if not user_message:
            return
            
        # Clear input field
        self.chat_input.delete(0, tk.END)
        
        # Display user message
        self.update_chat_display(f"You: {user_message}\n")
        
        # Get and display bot response
        try:
            response = self.chatbot.get_response(user_message)
            self.update_chat_display(f"Bot: {response}\n")
        except Exception as e:
            self.update_chat_display(f"Error: Could not get response from chatbot. {str(e)}\n")
            
    def update_chat_display(self, message):
        """Update the chat display with a new message"""
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, message)
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
        
    def clear_chat(self):
        """Clear the chat display and reset the chatbot"""
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state='disabled')
        if hasattr(self, 'chatbot'):
            self.chatbot.reset_chat()
        self.update_chat_display("Chat cleared. You can start a new conversation.\n")

def main():
    root = tk.Tk()
    app = ReceiptAutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 