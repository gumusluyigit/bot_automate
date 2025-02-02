import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
import sqlite3
import glob

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
        
        # Setup download directory using a fixed path
        self.download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Setup database directory
        db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db')
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, 'pending_requests.db')
        
        # Setup log file
        self.log_file = "automation_log.txt"
        
        # Load config
        self.load_config()
        
        # Initialize chatbot
        self.chatbot = Chatbot(self)
        
        # Create EmailHandler first
        self.email_handler = EmailHandler(
            self.sender_email.get() or "temp@example.com",
            self.internal_email.get() or "temp@example.com",
            db_path=self.db_path
        )
        
        # Initialize web automation
        self.web_automation = WebAutomation(self.download_dir)
        self.web_automation.email_handler = self.email_handler
        
        # Initialize GUI components
        self.setup_gui()
        
        # Update pending requests tab
        self.update_pending_requests_tab()
        
        # Initial status message
        self.log_message("Application started")

    def setup_gui(self):
        """Setup the main GUI components"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create tabs
        self.chat_tab = ttk.Frame(self.notebook)
        self.main_tab = ttk.Frame(self.notebook)
        self.pending_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.logs_tab = ttk.Frame(self.notebook)
        
        # Add tabs in the desired order
        self.notebook.add(self.chat_tab, text='Chat')
        self.notebook.add(self.main_tab, text='Main')
        self.notebook.add(self.pending_tab, text='Pending Requests')
        self.notebook.add(self.settings_tab, text='Settings')
        self.notebook.add(self.logs_tab, text='Logs')
        
        # Setup each tab
        self.setup_chat_tab()  # Setup chat tab first
        self.setup_main_tab()
        self.setup_pending_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()
        
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
                  command=self.process_pdfs).pack(side='left', padx=5)
        
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
        
    def _get_recent_weeks(self) -> list:
        """Get a list of recent weeks for the dropdown"""
        weeks = []
        today = datetime.now()
        
        # Get the Monday of the current week
        current_monday = today - timedelta(days=today.weekday())
        
        # Turkish month names
        turkish_months = {
            1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
            5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
            9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
        }
        
        # Generate weeks (current week and previous 11 weeks)
        for i in range(12):
            week_start = current_monday - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            
            # Format dates in Turkish
            week_str = (f"{week_start.day} {turkish_months[week_start.month]} {week_start.year} - "
                       f"{week_end.day} {turkish_months[week_end.month]} {week_end.year}")
            
            weeks.append((week_str, week_start, week_end))
            
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
            
            self.update_status(f"Processing PDFs for last week ({last_monday.strftime('%d %B %Y')} to {last_sunday.strftime('%d %B %Y')})")
            self.update_status("="*50)
            self.update_status(f"Processing Last Week's PDFs: {last_monday.strftime('%d %B %Y')} "
                             f"to {last_sunday.strftime('%d %B %Y')}")
            self.update_status("="*50)
            
            # Get PDFs for last week
            pdfs, skipped = self.web_automation.search_and_download_pdf(target_week=(last_monday, last_sunday))
            
            if not pdfs and not skipped:
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
            
    def process_pdfs(self):
        """Process PDFs for the selected week"""
        if self.is_processing:
            return
            
        self.is_processing = True
        self.update_status("Starting PDF processing...")
        
        try:
            # Get selected week
            selected_week = self.week_var.get()
            if not selected_week:
                self.update_status("Please select a week first")
                return
                
            # Download PDFs
            downloaded_pdfs, skipped_pdfs = self.web_automation.download_pdfs_for_week(selected_week)
            self.update_status(f"\nFound PDFs for target week\n")
            
            successful_count = 0
            failed_count = 0
            auto_sent_count = 0
            
            # Process each downloaded PDF
            for pdf_path in downloaded_pdfs:
                filename = os.path.basename(pdf_path)
                self.update_status(f"Processing PDF: {filename}")
                
                try:
                    # Extract details from PDF using PDFProcessor
                    pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                    if not pdf_info:
                        raise Exception("Failed to extract PDF information")
                        
                    company_name = self.web_automation.extract_company_name(filename)
                    if not company_name:
                        raise Exception("Failed to extract company name")
                    
                    # Store invoice details with actual PDF data
                    self.email_handler.store_invoice_details(
                        invoice_number=pdf_info['invoice_number'],
                        company_name=company_name,
                        period_start=pdf_info['period_start'],
                        period_end=pdf_info['period_end'],
                        due_date=pdf_info['due_date'],
                        amount_due=pdf_info['amount_due'],
                        currency=pdf_info['currency'],
                        pdf_path=pdf_path
                    )
                    
                    # Check if we have an email for this invoice
                    email, stored_company = self.email_handler.get_email_for_invoice(pdf_info['invoice_number'])
                    
                    if email:
                        # Send email directly if we have a stored email
                        if self.email_handler.send_email_directly(pdf_info['invoice_number'], pdf_path, company_name, email):
                            self.update_status(f"✓ Automatically sent {filename} to {email}")
                            auto_sent_count += 1
                            successful_count += 1
                            # Move to processed folder only after successful email send
                            os.makedirs('processed', exist_ok=True)
                            self.web_automation.mark_as_processed(pdf_path)
                        else:
                            self.update_status(f"✗ Failed to send {filename} automatically to {email}")
                            failed_count += 1
                    else:
                        # Add to pending requests if no email found
                        if self.email_handler.add_to_pending(
                            invoice_number=pdf_info['invoice_number'],
                            company_name=company_name,
                            pdf_path=pdf_path,
                            period_start=pdf_info['period_start'],
                            period_end=pdf_info['period_end']
                        ):
                            self.update_status(f"✓ Added {filename} to pending requests")
                            successful_count += 1
                        else:
                            self.update_status(f"✗ Failed to process {filename}")
                            failed_count += 1
                            
                except Exception as e:
                    self.update_status(f"Error processing {filename}: {str(e)}")
                    failed_count += 1
                    
            # Show skipped PDFs
            if skipped_pdfs:
                self.update_status("\nSkipped PDFs (already processed):")
                for filename in skipped_pdfs:
                    self.update_status(f"  - {filename}")
                    
            # Show final summary
            self.update_status(f"\nProcessing complete:")
            self.update_status(f"- {successful_count} PDF(s) processed successfully")
            self.update_status(f"  • {auto_sent_count} sent automatically")
            self.update_status(f"  • {successful_count - auto_sent_count} added to pending requests")
            self.update_status(f"- {len(skipped_pdfs)} PDF(s) skipped (already processed)")
            self.update_status(f"- {failed_count} PDF(s) failed")
            
            # Update pending requests display
            self.update_pending_requests_tab()
            
        except Exception as e:
            self.update_status(f"Error during processing: {str(e)}")
        finally:
            self.is_processing = False

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
        sender_entry = ttk.Entry(sender_frame, textvariable=self.sender_email, width=40)
        sender_entry.pack(side='left', padx=5)
        
        # Internal Email
        internal_frame = ttk.Frame(email_frame)
        internal_frame.pack(fill='x', pady=5)
        ttk.Label(internal_frame, text="Internal Email:").pack(side='left', padx=5)
        internal_entry = ttk.Entry(internal_frame, textvariable=self.internal_email, width=40)
        internal_entry.pack(side='left', padx=5)
        
        # App Password
        password_frame = ttk.Frame(email_frame)
        password_frame.pack(fill='x', pady=5)
        ttk.Label(password_frame, text="App Password:").pack(side='left', padx=5)
        password_entry = ttk.Entry(password_frame, textvariable=self.app_password, show="*", width=40)
        password_entry.pack(side='left', padx=5)
        
        # Buttons Frame
        button_frame = ttk.Frame(email_frame)
        button_frame.pack(fill='x', pady=10)
        
        # Save Settings Button
        ttk.Button(button_frame, text="Save Settings", 
                  command=self.save_settings).pack(side='left', padx=5)
        
        # Test Connection Button
        ttk.Button(button_frame, text="Test Connection", 
                  command=self.test_connection).pack(side='left', padx=5)

    def save_settings(self):
        """Save email settings"""
        if not all([self.sender_email.get(), self.internal_email.get(), self.app_password.get()]):
            messagebox.showwarning("Warning", "Please fill in all email settings")
            return
            
        try:
            # Save to config file
            config = {
                'sender_email': self.sender_email.get(),
                'internal_email': self.internal_email.get()
            }
            
            with open('config.json', 'w') as f:
                json.dump(config, f)
                
            # Save app password
            if not self.email_handler.save_credentials(self.app_password.get()):
                raise Exception("Failed to save credentials")
                
            # Update email handler
            self.email_handler.sender_email = self.sender_email.get()
            self.email_handler.internal_email = self.internal_email.get()
            
            messagebox.showinfo("Success", "Settings saved successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def test_connection(self):
        """Test email connection"""
        if not all([self.sender_email.get(), self.app_password.get()]):
            messagebox.showwarning(
                "Warning", 
                "Please fill in both sender email and app password"
            )
            return
            
        try:
            # Update email handler with current settings
            self.email_handler.sender_email = self.sender_email.get()
            if not self.email_handler.save_credentials(self.app_password.get()):
                raise Exception("Failed to save credentials")
                
            # Test authentication
            if self.email_handler.authenticate():
                messagebox.showinfo(
                    "Success", 
                    "Connection test successful!\n\nYour Gmail settings are correctly configured."
                )
            else:
                raise Exception("Authentication failed")
                
        except Exception as e:
            error_msg = str(e)
            messagebox.showerror(
                "Gmail Authentication Error",
                f"Connection test failed:\n\n{error_msg}\n\n"
                "If you need help generating an App Password:\n"
                "1. Go to your Google Account settings\n"
                "2. Search for 'App Passwords'\n"
                "3. You may need to enable 2-Step Verification first\n"
                "4. Generate a new App Password for 'Mail'"
            )
            
            # Log the error for debugging
            self.log_message(f"Gmail authentication error: {error_msg}")

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    self.sender_email.set(config.get('sender_email', ''))
                    self.internal_email.set(config.get('internal_email', ''))
        except Exception as e:
            print(f"Error loading config: {str(e)}")

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
        # Create main frame
        main_frame = ttk.Frame(self.pending_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview with scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=5)
        
        self.pending_tree = ttk.Treeview(tree_frame, columns=('Invoice', 'Company', 'Period'), 
                                       show='headings', selectmode='browse')
        
        # Configure columns
        self.pending_tree.heading('Invoice', text='Invoice Number')
        self.pending_tree.heading('Company', text='Company Name')
        self.pending_tree.heading('Period', text='Period')
        
        self.pending_tree.column('Invoice', width=150)
        self.pending_tree.column('Company', width=150)
        self.pending_tree.column('Period', width=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, 
                                command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=scrollbar.set)
        
        self.pending_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Email entry frame
        email_frame = ttk.LabelFrame(main_frame, text="Send Email", padding="10")
        email_frame.pack(fill='x', pady=5)
        
        # Email entry
        ttk.Label(email_frame, text="Email:").pack(side='left', padx=5)
        self.pending_email_entry = ttk.Entry(email_frame, width=40)
        self.pending_email_entry.pack(side='left', padx=5)
        
        # Send button
        self.send_button = ttk.Button(email_frame, text="Send", 
                                    command=self.send_pending_email)
        self.send_button.pack(side='left', padx=5)
        
        # Bind selection event
        self.pending_tree.bind('<<TreeviewSelect>>', self.on_pending_select)
        
        # Initial update
        self.update_pending_requests_tab()

    def update_pending_requests_tab(self):
        """Update the pending requests treeview"""
        try:
            # Clear existing items
            for item in self.pending_tree.get_children():
                self.pending_tree.delete(item)
            
            # Get pending requests
            pending_requests = self.email_handler.get_pending_requests()
            
            # Add to treeview
            for request in pending_requests:
                invoice_number, company_name, pdf_path, start_date, end_date, status = request
                period = f"{start_date} - {end_date}" if start_date and end_date else "N/A"
                self.pending_tree.insert('', 'end', values=(invoice_number, company_name, period))
                
        except Exception as e:
            self.update_status(f"Error updating pending requests tab: {str(e)}")

    def on_pending_select(self, event):
        """Handle selection in pending requests treeview"""
        selection = self.pending_tree.selection()
        if not selection:
            return
            
        # Get selected item
        item = self.pending_tree.item(selection[0])
        invoice_number = item['values'][0]
        
        # Clear and disable email entry if no selection
        if not invoice_number:
            self.pending_email_entry.delete(0, tk.END)
            self.pending_email_entry.config(state='disabled')
            self.send_button.config(state='disabled')
            return
            
        # Enable email entry and send button
        self.pending_email_entry.config(state='normal')
        self.send_button.config(state='normal')
        
        # Clear previous email
        self.pending_email_entry.delete(0, tk.END)

    def send_pending_email(self):
        """Send email for selected pending request"""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a request first")
            return
            
        # Get selected item
        item = self.pending_tree.item(selection[0])
        invoice_number = item['values'][0]
        company_name = item['values'][1]
        
        # Get email
        email = self.pending_email_entry.get().strip()
        if not email:
            messagebox.showwarning("Warning", "Please enter an email address")
            return
            
        try:
            # Get PDF path from pending requests
            pdf_path = self.email_handler.get_pdf_path_for_invoice(invoice_number)
            if not pdf_path:
                raise Exception("PDF file not found")
                
            # Send email
            if self.email_handler.mark_as_sent(invoice_number, email):
                # Move to processed folder after successful send
                os.makedirs('processed', exist_ok=True)
                self.web_automation.mark_as_processed(pdf_path)
                
                self.update_status(f"Successfully sent email for {company_name}")
                self.pending_email_entry.delete(0, tk.END)
                self.update_pending_requests_tab()
            else:
                raise Exception("Failed to send email")
                
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            self.update_status(error_msg)
            messagebox.showerror("Error", error_msg)

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

    def setup_chat_tab(self):
        """Setup the chat interface tab"""
        # Chat display area
        chat_frame = ttk.Frame(self.chat_tab)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Chat history with scrollbar
        self.chat_display = tk.Text(chat_frame, height=20, width=80, wrap=tk.WORD)
        chat_scrollbar = ttk.Scrollbar(chat_frame, orient=tk.VERTICAL, 
                                     command=self.chat_display.yview)
        
        self.chat_display.pack(side='left', fill='both', expand=True)
        chat_scrollbar.pack(side='right', fill='y')
        
        self.chat_display['yscrollcommand'] = chat_scrollbar.set
        self.chat_display.config(state=tk.DISABLED)
        
        # Input area
        input_frame = ttk.Frame(self.chat_tab)
        input_frame.pack(fill='x', padx=10, pady=5)
        
        self.chat_input = ttk.Entry(input_frame)
        self.chat_input.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        send_button = ttk.Button(input_frame, text="Send", command=self.handle_chat_input)
        send_button.pack(side='right')
        
        # Bind Enter key to send message
        self.chat_input.bind('<Return>', lambda e: self.handle_chat_input())
        
        # Add initial message
        self.add_chat_message("Bot", "Merhaba! Size nasıl yardımcı olabilirim?")

    def add_chat_message(self, sender: str, message: str):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime('%H:%M')
        self.chat_display.insert(tk.END, f"\n[{timestamp}] {sender}: {message}")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def handle_chat_input(self):
        """Process user chat input"""
        message = self.chat_input.get().strip()
        if not message:
            return
            
        # Clear input
        self.chat_input.delete(0, tk.END)
        
        # Add user message to chat
        self.add_chat_message("You", message)
        
        # Process the message
        response = self.process_chat_query(message.lower())
        
        # Add bot response to chat
        self.add_chat_message("Bot", response)

    def get_closest_future_date(self, day: int, month: int) -> datetime:
        """Get the closest future date for a given day and month"""
        current_date = datetime.now()
        current_year = current_date.year
        
        # Try current year
        target_date = datetime(current_year, month, day)
        
        # If the date has passed, try next year
        if target_date < current_date:
            target_date = datetime(current_year + 1, month, day)
            
        return target_date

    def parse_turkish_date(self, date_str: str) -> tuple:
        """Parse a Turkish date string and return (day, month, year)"""
        print(f"Parsing Turkish date: {date_str}")
        # Turkish month names mapping
        turkish_months = {
            'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4,
            'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8,
            'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
        }
        
        parts = date_str.strip().lower().split()
        print(f"Date parts: {parts}")
        
        # Extract day and month
        day = int(parts[0])
        month = turkish_months[parts[1]]
        
        # Use 2025 for January dates, 2024 for others (to match our sample PDFs)
        if len(parts) > 2:
            year = int(parts[2])
        else:
            year = 2025 if month == 1 else 2024
            
        print(f"Parsed date - Day: {day}, Month: {month}, Year: {year}")
        return day, month, year

    def process_chat_query(self, query: str) -> str:
        """Process chat queries and return appropriate responses"""
        try:
            query = query.lower().strip()
            
            # Common Turkish variations and typos
            amount_keywords = ['borcu', 'borç', 'borc', 'borçu', 'borcu', 'tutar', 'tutarı', 'tutari', 'ödeme']
            email_keywords = ['mail', 'email', 'e-mail', 'eposta', 'e-posta', 'elektronik posta']
            due_date_keywords = ['son ödeme', 'son odeme', 'vade', 'ödeme günü', 'odeme gunu']
            week_keywords = ['hafta', 'haftası', 'haftasının', 'haftasindaki', 'haftasında', 'haftasi', 'haftasini']
            pdf_keywords = ['pdf', 'pdfleri', 'pdflerini', 'dosya', 'dosyaları', 'dosyalarini', 'işle', 'isle']
            
            # Check if this is a PDF processing command
            if any(keyword in query for keyword in pdf_keywords) and any(keyword in query for keyword in week_keywords):
                # Extract date from query
                date_str = None
                for word in week_keywords:
                    if word in query:
                        parts = query.split(word)[0].strip().split()
                        if parts:
                            date_str = ' '.join(parts[-2:] if len(parts) >= 2 else parts)
                        break
                
                if date_str:
                    print(f"Processing PDFs for date: {date_str}")
                    # Download PDFs for the week
                    downloaded_pdfs, skipped_pdfs = self.web_automation.download_pdfs_for_week(date_str)
                    
                    if not downloaded_pdfs and not skipped_pdfs:
                        return "Belirtilen hafta için PDF bulunamadı."
                    
                    # Process the downloaded PDFs
                    successful_count = 0
                    failed_count = 0
                    auto_sent_count = 0
                    
                    for pdf_path in downloaded_pdfs:
                        try:
                            filename = os.path.basename(pdf_path)
                            invoice_number = self.web_automation.extract_invoice_number(filename)
                            company_name = self.web_automation.extract_company_name(filename)
                            start_date, end_date = self.web_automation.extract_date_range(filename)
                            
                            if not all([invoice_number, company_name, start_date, end_date]):
                                raise Exception("Failed to extract required information")
                            
                            # Extract additional details
                            pdf_details = self.web_automation.extract_pdf_details(pdf_path)
                            
                            # Store invoice details
                            self.email_handler.store_invoice_details(
                                invoice_number=invoice_number,
                                company_name=company_name,
                                period_start=start_date,
                                period_end=end_date,
                                due_date=pdf_details.get('due_date'),
                                amount_due=pdf_details.get('amount_due'),
                                currency=pdf_details.get('currency', 'USD'),
                                pdf_path=pdf_path
                            )
                            
                            # Check if we have an email for this invoice
                            email, stored_company = self.email_handler.get_email_for_invoice(invoice_number)
                            if email:
                                if self.email_handler.send_email_directly(invoice_number, pdf_path, company_name, email):
                                    auto_sent_count += 1
                                    successful_count += 1
                            else:
                                if self.email_handler.add_to_pending(
                                    invoice_number=invoice_number,
                                    company_name=company_name,
                                    pdf_path=pdf_path,
                                    period_start=start_date,
                                    period_end=end_date
                                ):
                                    successful_count += 1
                                
                        except Exception as e:
                            print(f"Error processing {pdf_path}: {str(e)}")
                            failed_count += 1
                    
                    # Update pending requests display
                    self.update_pending_requests_tab()
                    
                    # Return summary message
                    return (
                        f"İşlem tamamlandı:\n"
                        f"- {successful_count} PDF başarıyla işlendi\n"
                        f"  • {auto_sent_count} otomatik gönderildi\n"
                        f"  • {successful_count - auto_sent_count} bekleyen isteklere eklendi\n"
                        f"- {len(skipped_pdfs)} PDF atlandı (zaten işlenmiş)\n"
                        f"- {failed_count} PDF başarısız oldu"
                    )
                
                return "Tarih bilgisini anlayamadım. Lütfen '6 Ocak haftası' gibi bir format kullanın."
            
            # Extract company name (for other queries)
            if 'şirketinin' in query:
                company_name = query.split('şirketinin')[0].strip()
            elif 'sirketinin' in query:
                company_name = query.split('sirketinin')[0].strip()
            else:
                # Only require company name for non-PDF processing queries
                if any(keyword in query for keyword in (amount_keywords + email_keywords + due_date_keywords)):
                    return "Üzgünüm, şirket adını anlayamadım. Lütfen '[şirket] şirketinin ...' formatında sorun."
            
            # Check for due date query
            if any(keyword in query for keyword in due_date_keywords):
                due_date = self.email_handler.get_company_due_date(company_name)
                if due_date:
                    return f"{company_name} şirketinin son ödeme tarihi: {due_date}"
                return f"{company_name} şirketi için son ödeme tarihi bulunamadı."
            
            # Check for amount due query
            if any(keyword in query for keyword in amount_keywords):
                # Extract date from query by finding week-related words
                query_parts = query.split('şirketinin' if 'şirketinin' in query else 'sirketinin')[1]
                
                # Find the week-related word and get the date part
                for word in week_keywords:
                    if word in query_parts:
                        date_str = query_parts.split(word)[0].strip()
                        break
                else:
                    return "Üzgünüm, tarih bilgisini anlayamadım. Lütfen '[şirket] şirketinin [tarih] haftasının borcu' formatında sorun."
                
                # Parse the date
                day, month, year = self.parse_turkish_date(date_str)
                
                # Format dates
                start_date = f"{year}-{month:02d}-{day:02d}"
                end_dt = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=6)
                end_date = end_dt.strftime('%Y-%m-%d')
                
                print(f"Checking amount due for {company_name} between {start_date} and {end_date}")
                
                # First, try to get the amount from the database
                amount, currency = self.email_handler.get_company_amount_due(company_name, start_date, end_date)
                if amount is not None:
                    # Get the actual invoice period from the database
                    actual_period = self.email_handler.get_invoice_period(company_name, start_date, end_date)
                    if actual_period:
                        start_date, end_date = actual_period
                    return f"{company_name} şirketinin {start_date} - {end_date} dönemi için borcu: {amount} {currency}"
                
                print(f"No amount found in database, trying to process PDFs...")
                # If no amount found in the database, try processing PDFs
                downloaded_pdfs, _ = self.web_automation.download_pdfs_for_week(date_str)
                
                if downloaded_pdfs:
                    for pdf_path in downloaded_pdfs:
                        try:
                            # Extract details from PDF using PDFProcessor
                            pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                            if pdf_info:
                                # Store in database with actual PDF data
                                self.email_handler.store_invoice_details(
                                    invoice_number=pdf_info.get('invoice_number'),
                                    company_name=company_name,
                                    period_start=pdf_info.get('period_start'),
                                    period_end=pdf_info.get('period_end'),
                                    due_date=pdf_info.get('due_date'),
                                    amount_due=pdf_info.get('amount_due'),
                                    currency=pdf_info.get('currency', 'USD'),
                                    pdf_path=pdf_path
                                )
                                print(f"Stored invoice details: {pdf_info}")
                                
                        except Exception as e:
                            print(f"Error processing PDF {pdf_path}: {str(e)}")
                            continue
                    
                    # Try getting the amount one more time
                    amount, currency = self.email_handler.get_company_amount_due(company_name, start_date, end_date)
                    if amount is not None:
                        # Get the actual invoice period from the database
                        actual_period = self.email_handler.get_invoice_period(company_name, start_date, end_date)
                        if actual_period:
                            start_date, end_date = actual_period
                        return f"{company_name} şirketinin {start_date} - {end_date} dönemi için borcu: {amount} {currency}"
                
                return f"{company_name} şirketi için belirtilen dönemde borç bilgisi bulunamadı."
            
            # Check for processing week request
            if any(w_key in query for w_key in week_keywords) and any(p_key in query for p_key in pdf_keywords):
                # Extract the date part
                for word in week_keywords:
                    if word in query:
                        date_str = query.split(word)[0].strip().split('şirketinin')[-1].strip()
                        break
                
                print(f"Processing PDFs for date: {date_str}")
                
                # Download PDFs for the week
                downloaded_pdfs, skipped_pdfs = self.web_automation.download_pdfs_for_week(date_str)
                
                if not downloaded_pdfs and not skipped_pdfs:
                    return "Belirtilen hafta için PDF bulunamadı."
                
                # Process the downloaded PDFs
                successful_count = 0
                failed_count = 0
                auto_sent_count = 0
                
                for pdf_path in downloaded_pdfs:
                    try:
                        filename = os.path.basename(pdf_path)
                        invoice_number = self.web_automation.extract_invoice_number(filename)
                        company_name = self.web_automation.extract_company_name(filename)
                        start_date, end_date = self.web_automation.extract_date_range(filename)
                        
                        if not all([invoice_number, company_name, start_date, end_date]):
                            raise Exception("Failed to extract required information")
                        
                        # Extract additional details
                        pdf_details = self.web_automation.extract_pdf_details(pdf_path)
                        
                        # Store invoice details
                        self.email_handler.store_invoice_details(
                            invoice_number=invoice_number,
                            company_name=company_name,
                            period_start=start_date,
                            period_end=end_date,
                            due_date=pdf_details.get('due_date'),
                            amount_due=pdf_details.get('amount_due'),
                            currency=pdf_details.get('currency', 'USD'),
                            pdf_path=pdf_path
                        )
                        
                        # Check if we have an email for this invoice
                        email, stored_company = self.email_handler.get_email_for_invoice(invoice_number)
                        
                        if email:
                            if self.email_handler.send_email_directly(invoice_number, pdf_path, company_name, email):
                                auto_sent_count += 1
                                successful_count += 1
                        else:
                            if self.email_handler.add_to_pending(
                                invoice_number=invoice_number,
                                company_name=company_name,
                                pdf_path=pdf_path,
                                period_start=start_date,
                                period_end=end_date
                            ):
                                successful_count += 1
                            
                    except Exception as e:
                        print(f"Error processing {pdf_path}: {str(e)}")
                        failed_count += 1
                
                # Update pending requests display
                self.update_pending_requests_tab()
                
                # Return summary message
                return (
                    f"İşlem tamamlandı:\n"
                    f"- {successful_count} PDF başarıyla işlendi\n"
                    f"  • {auto_sent_count} otomatik gönderildi\n"
                    f"  • {successful_count - auto_sent_count} bekleyen isteklere eklendi\n"
                    f"- {len(skipped_pdfs)} PDF atlandı (zaten işlenmiş)\n"
                    f"- {failed_count} PDF başarısız oldu"
                )
            
            # Check for email query
            if any(keyword in query for keyword in email_keywords):
                email = self.email_handler.get_company_email(company_name)
                if email:
                    return f"{company_name} şirketinin email adresi: {email}"
                return f"{company_name} şirketi için email adresi bulunamadı."
            
            return "Üzgünüm, sorunuzu anlayamadım. Lütfen şu şekilde sorun:\n" + \
                   "- [şirket] şirketinin son ödeme günü ne zaman?\n" + \
                   "- [şirket] şirketinin [tarih] haftasının borcu kaç dolar?\n" + \
                   "- [şirket] şirketinin mail adresi nedir?\n" + \
                   "- [gün] [ay] haftasının pdflerini işle"
                   
        except Exception as e:
            return f"Üzgünüm, bir hata oluştu: {str(e)}"

    def update_processing_state(self):
        """Update UI elements based on processing state"""
        state = 'disabled' if self.is_processing else 'normal'
        for child in self.main_tab.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, (ttk.Button, ttk.Combobox)):
                        widget.configure(state=state)

    def reset_environment(self):
        """Reset the environment for demonstration"""
        if not messagebox.askyesno("Confirm Reset", 
                                 "This will clear all pending requests and reset the environment. Continue?"):
            return
            
        try:
            # Clear downloads directory
            for file in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    self.update_status(f"Error deleting {file}: {str(e)}")

            # Reset database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Drop all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
            
            conn.commit()
            conn.close()
            
            # Reinitialize database
            self.email_handler.init_db()
            
            # Update UI
            self.update_pending_requests_tab()
            self.update_status("\nEnvironment reset successfully!")
            messagebox.showinfo("Success", "Environment has been reset successfully!")
            
        except Exception as e:
            error_msg = f"Failed to reset environment: {str(e)}"
            self.update_status(f"\nError: {error_msg}")
            messagebox.showerror("Error", error_msg)

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
        if hasattr(self, 'logs_text'):
            self.logs_text.config(state=tk.NORMAL)
            self.logs_text.insert(tk.END, log_entry)
            self.logs_text.see(tk.END)
            self.logs_text.config(state=tk.DISABLED)
        
        # Also update status display
        self.update_status(message)

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

    def download_pdfs_for_week(self, week_str: str) -> tuple:
        """Download PDFs for a specific week"""
        try:
            print(f"Processing week string: {week_str}")
            # Parse week string to get start and end dates
            # Format: "1 Ocak 2024 - 7 Ocak 2024"
            turkish_months = {
                'ocak': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
                'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
                'eylül': '09', 'ekim': '10', 'kasım': '11', 'aralık': '12'
            }
            
            # Split into start and end dates
            start_str, end_str = week_str.split(' - ')
            print(f"Split dates - Start: {start_str}, End: {end_str}")
            
            start_parts = start_str.split()
            end_parts = end_str.split()
            print(f"Date parts - Start: {start_parts}, End: {end_parts}")
            
            # Create date strings in YYYY-MM-DD format
            start_date = f"{start_parts[2]}-{turkish_months[start_parts[1].lower()]}-{int(start_parts[0]):02d}"
            end_date = f"{end_parts[2]}-{turkish_months[end_parts[1].lower()]}-{int(end_parts[0]):02d}"
            print(f"Formatted dates - Start: {start_date}, End: {end_date}")
            
            # Call the existing search_and_download_pdf method
            return self.web_automation.search_and_download_pdf((start_date, end_date))
        except Exception as e:
            print(f"Error downloading PDFs for week: {str(e)}")
            return [], []

def main():
    root = tk.Tk()
    app = ReceiptAutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 