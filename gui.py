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
        self.root = root
        self.root.title("Receipt Automation")
        self.root.geometry("1000x800")
        
        # Initialize logging
        self.log_file = "automation_log.txt"
        
        # Add processing state tracking
        self.is_processing = False
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create main tab
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text='Main')
        
        # Create chat tab
        self.chatbot_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chatbot_tab, text='Chat')
        
        # Create settings tab
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text='Settings')
        
        # Create pending tab
        self.pending_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.pending_tab, text='Pending Requests')
        
        # Create logs tab
        self.logs_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_tab, text='Logs')
        
        self.setup_main_tab()
        self.setup_pending_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()
        self.setup_chat_tab()
        
        # Load settings
        self.load_settings()
        
        # Initialize automation components
        self.download_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        self.web_automation = WebAutomation(self.download_dir)
        self.email_handler = None  # Will be initialized when processing receipts
        self.chatbot = None  # Will be initialized when chat tab is selected
        
        self.log_message("Application started")

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
            pdfs = self.web_automation.search_and_download_pdf(target_week=(last_monday, last_sunday))
            
            if not pdfs:
                self.log_message("No unprocessed PDFs found for the specified week")
                self.update_status("No unprocessed PDFs found for the specified week")
                self.is_processing = False
                self.update_processing_state()
                return
                
            self.process_pdf_list(pdfs)
            
        except Exception as e:
            self.handle_error(e)
            self.is_processing = False
            self.update_processing_state()
            
    def process_selected_week(self):
        """Process PDFs for selected week"""
        try:
            if self.is_processing:
                messagebox.showwarning("Warning", "Please wait for the current processing to complete before selecting a new date range.")
                return
                
            if not self.check_email_settings():
                return
                
            if not self.week_var.get():
                messagebox.showerror("Error", "Please select a week first!")
                return
                
            # Find the selected week's dates from our stored weeks
            selected_display = self.week_var.get()
            weeks = self._get_recent_weeks()
            selected_dates = None
            
            for week_display, start_date, end_date in weeks:
                if week_display == selected_display:
                    selected_dates = (start_date, end_date)
                    break
            
            if not selected_dates:
                messagebox.showerror("Error", "Could not determine selected week's dates!")
                return
                
            start_date, end_date = selected_dates
            
            self.is_processing = True
            self.update_processing_state()
            
            self.log_message(f"Processing PDFs for week {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}")
            self.update_status("="*50)
            self.update_status(f"Processing PDFs for Week: {start_date.strftime('%d %B %Y')} "
                             f"to {end_date.strftime('%d %B %Y')}")
            self.update_status("="*50)
            
            # Get PDFs for selected week
            pdfs = self.web_automation.search_and_download_pdf(target_week=(start_date, end_date))
            
            if not pdfs:
                self.log_message("No unprocessed PDFs found for the specified week")
                self.update_status("No unprocessed PDFs found for the specified week")
                self.is_processing = False
                self.update_processing_state()
                return
                
            self.process_pdf_list(pdfs)
            
        except Exception as e:
            self.handle_error(e)
            self.is_processing = False
            self.update_processing_state()
            
    def process_pdf_list(self, pdf_paths: list):
        """Process a list of PDFs"""
        try:
            total = len(pdf_paths)
            processed = 0
            failed = 0
            skipped = 0
            
            for pdf_path in pdf_paths:
                try:
                    self.update_status(f"\nProcessing PDF ({processed + 1}/{total}): {os.path.basename(pdf_path)}")
                    
                    if not os.path.exists(pdf_path):
                        raise Exception("PDF file not found - it may have been removed")
                        
                    if not PDFProcessor.validate_pdf(pdf_path):
                        raise Exception("Invalid PDF file")
                    self.update_status("PDF validation successful!")
                    
                    invoice_info = PDFProcessor.extract_invoice_info(pdf_path)
                    invoice_number = invoice_info.get('invoice_number')
                    company_name = invoice_info.get('company_name', 'Unknown Company')
                    
                    if not invoice_number:
                        raise Exception("Could not extract invoice number from PDF")
                    
                    # Check if receipt was already sent
                    if self.email_handler.check_if_sent(invoice_number):
                        self.update_status(f"Receipt for invoice {invoice_number} was already sent - skipping")
                        skipped += 1
                        continue
                    
                    # Check database for email address
                    company_email = self.email_handler.get_email_from_database(invoice_number)
                    
                    if company_email:
                        # Send PDF directly to company
                        self.update_status(f"Found email address: {company_email}")
                        if self.email_handler.send_receipt_to_company(company_email, invoice_number, pdf_path):
                            self.update_status(f"Successfully sent PDF to {company_email}")
                            self.web_automation.mark_as_processed(pdf_path)
                            processed += 1
                        else:
                            raise Exception(f"Failed to send PDF to {company_email}")
                    else:
                        # Add to pending requests
                        self.update_status(f"No email found for invoice {invoice_number}")
                        self.email_handler.pending_requests[invoice_number] = {
                            'company_name': company_name,
                            'request_time': datetime.now(),
                            'pdf_path': pdf_path
                        }
                        self.update_status("Added to pending requests")
                        self.update_pending_requests()
                        processed += 1
                            
                except Exception as e:
                    self.update_status(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")
                    failed += 1
                    continue
                    
            self.update_status("\n" + "="*50)
            self.update_status(f"Processing completed: {processed} successful, {skipped} skipped, {failed} failed")
            if failed == 0:
                if skipped > 0:
                    messagebox.showinfo("Success", f"Processing completed: {processed} successful, {skipped} skipped (already sent)")
                else:
                    messagebox.showinfo("Success", "All PDFs processed successfully!")
            else:
                messagebox.showwarning("Warning", f"Processing completed with {failed} errors")
            
        finally:
            self.is_processing = False
            self.update_processing_state()
            
    def check_email_settings(self) -> bool:
        """Check if email settings are configured"""
        if not self.sender_email.get() or not self.internal_email.get():
            messagebox.showerror("Error", "Please configure email settings first!")
            self.notebook.select(2)  # Switch to settings tab
            return False
            
        # Initialize email handler if not already done
        if not self.email_handler:
            self.email_handler = EmailHandler(
                self.sender_email.get(),
                self.internal_email.get()
            )
        return True
        
    def handle_error(self, error: Exception):
        """Handle and display errors"""
        error_message = f"Error: {str(error)}"
        self.log_message(f"ERROR: {error_message}")
        self.update_status(f"\nERROR: {error_message}")
        messagebox.showerror("Error", error_message)

    def setup_settings_tab(self):
        """Setup the settings tab"""
        # Email Settings
        email_frame = ttk.LabelFrame(self.settings_tab, text="Gmail Settings", padding="10")
        email_frame.pack(fill='x', padx=10, pady=5)
        
        # Sender Email
        ttk.Label(email_frame, text="Gmail Address:").grid(row=0, column=0, 
                                                         sticky='w', padx=5, pady=2)
        self.sender_email = ttk.Entry(email_frame, width=40)
        self.sender_email.grid(row=0, column=1, padx=5, pady=2)
        
        # App Password
        ttk.Label(email_frame, text="App Password:").grid(row=1, column=0, 
                                                        sticky='w', padx=5, pady=2)
        self.app_password = ttk.Entry(email_frame, width=40, show='*')
        self.app_password.grid(row=1, column=1, padx=5, pady=2)
        
        # Help text for App Password
        help_text = ("Note: You need to generate an App Password for your Gmail account.\n"
                    "1. Go to Google Account settings\n"
                    "2. Enable 2-Step Verification if not enabled\n"
                    "3. Go to Security > App passwords\n"
                    "4. Generate a new App password for 'Mail'")
        help_label = ttk.Label(email_frame, text=help_text, wraplength=400)
        help_label.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # Internal Department Email
        ttk.Label(email_frame, text="Internal Dept Email:").grid(row=3, column=0, 
                                                               sticky='w', padx=5, pady=2)
        self.internal_email = ttk.Entry(email_frame, width=40)
        self.internal_email.grid(row=3, column=1, padx=5, pady=2)
        
        # Test Email Button
        ttk.Button(email_frame, text="Test Email Settings", 
                  command=self.test_email_settings).grid(row=4, column=0, 
                                                       columnspan=2, pady=10)
        
        # Save Settings Button
        ttk.Button(self.settings_tab, text="Save Settings", 
                  command=self.save_settings).pack(pady=10)

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    settings = json.load(f)
                    self.sender_email.insert(0, settings.get('sender_email', ''))
                    self.internal_email.insert(0, settings.get('internal_email', ''))
            
            # Load Gmail password if it exists
            if os.path.exists('gmail_config.json'):
                with open('gmail_config.json', 'r') as f:
                    credentials = json.load(f)
                    self.app_password.insert(0, credentials.get('app_password', ''))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load settings: {str(e)}")

    def save_settings(self):
        """Save settings to file"""
        try:
            # Save email settings
            settings = {
                'sender_email': self.sender_email.get(),
                'internal_email': self.internal_email.get()
            }
            with open('settings.json', 'w') as f:
                json.dump(settings, f)
            
            # Save Gmail password
            if self.app_password.get():
                if not self.email_handler:
                    self.email_handler = EmailHandler(
                        self.sender_email.get(),
                        self.internal_email.get()
                    )
                self.email_handler.save_credentials(self.app_password.get())
            
            self.log_message("Settings saved successfully")
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            error_msg = f"Failed to save settings: {str(e)}"
            self.log_message(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

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
        """Update status text widget with new message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_message = f"{timestamp}: {message}"
        
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, status_message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update()
        
        # Also log the message
        self.log_message(message)

    def setup_pending_tab(self):
        """Setup the pending requests tab"""
        # Main frame
        main_frame = ttk.Frame(self.pending_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Pending requests list
        list_frame = ttk.LabelFrame(main_frame, text="Pending Email Requests", padding="10")
        list_frame.pack(fill='both', expand=True)
        
        # Create canvas and scrollable frame for better control
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Headers
        ttk.Label(scrollable_frame, text="Invoice", width=15).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Company", width=20).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Request Time", width=20).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Email", width=30).grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Action", width=10).grid(row=0, column=4, padx=5, pady=5)
        
        # Store frame reference for updates
        self.pending_frame = scrollable_frame
        self.pending_entries = {}
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def update_pending_requests(self):
        """Update the pending requests display"""
        # Clear existing entries
        for widget in self.pending_frame.winfo_children()[5:]:  # Skip headers
            widget.destroy()
        self.pending_entries.clear()
        
        # Add pending requests
        if self.email_handler and self.email_handler.pending_requests:
            row = 1
            for invoice, details in self.email_handler.pending_requests.items():
                # Invoice number
                ttk.Label(self.pending_frame, text=invoice, width=15).grid(
                    row=row, column=0, padx=5, pady=5)
                
                # Company name
                ttk.Label(self.pending_frame, text=details['company_name'], width=20).grid(
                    row=row, column=1, padx=5, pady=5)
                
                # Request time
                ttk.Label(self.pending_frame, 
                         text=details['request_time'].strftime('%Y-%m-%d %H:%M'),
                         width=20).grid(row=row, column=2, padx=5, pady=5)
                
                # Email entry
                email_entry = ttk.Entry(self.pending_frame, width=35)
                email_entry.grid(row=row, column=3, padx=5, pady=5)
                
                # Button frame for send and dismiss buttons
                button_frame = ttk.Frame(self.pending_frame)
                button_frame.grid(row=row, column=4, padx=5, pady=5)
                
                # Send button
                send_button = ttk.Button(button_frame, text="Send",
                                       command=lambda i=invoice, e=email_entry: 
                                       self.send_pending_receipt(i, e))
                send_button.pack(side='left', padx=(0, 2))
                
                # Dismiss button (red X)
                dismiss_button = tk.Button(button_frame, text="✕", fg='red', 
                                         command=lambda i=invoice: self.dismiss_request(i),
                                         width=2, font=('Arial', 8, 'bold'))
                dismiss_button.pack(side='left')
                
                # Store references
                self.pending_entries[invoice] = {
                    'entry': email_entry,
                    'send_button': send_button,
                    'dismiss_button': dismiss_button
                }
                
                row += 1
            
            self.update_status(f"Updated pending requests list: {len(self.email_handler.pending_requests)} items")
            
    def send_pending_receipt(self, invoice_number: str, email_entry: ttk.Entry):
        """Send receipt to company using manually entered email"""
        email = email_entry.get().strip()
        if not email:
            messagebox.showerror("Error", "Please enter an email address.")
            return
            
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            messagebox.showerror("Error", "Please enter a valid email address.")
            return
            
        try:
            details = self.email_handler.pending_requests.get(invoice_number)
            if not details:
                messagebox.showerror("Error", "Request details not found.")
                return
                
            pdf_path = details.get('pdf_path')
            if not pdf_path or not os.path.exists(pdf_path):
                messagebox.showerror("Error", "PDF file not found.")
                return
                
            # Send receipt to company
            self.log_message(f"Sending receipt for invoice {invoice_number} to {email}")
            self.update_status(f"Sending receipt to company ({email})...")
            
            if self.email_handler.send_receipt_to_company(email, invoice_number, pdf_path):
                self.log_message("Receipt sent successfully")
                self.update_status("Receipt sent successfully")
                
                # Mark PDF as processed
                self.web_automation.mark_as_processed(pdf_path)
                
                # Remove from pending requests
                if invoice_number in self.email_handler.pending_requests:
                    del self.email_handler.pending_requests[invoice_number]
                    
                # Update display
                self.update_pending_requests()
                messagebox.showinfo("Success", f"Receipt sent successfully to {email}")
            else:
                raise Exception("Failed to send receipt")
                
        except Exception as e:
            error_msg = f"Error sending receipt: {str(e)}"
            self.log_message(f"ERROR: {error_msg}")
            self.update_status(error_msg)
            messagebox.showerror("Error", error_msg)

    def dismiss_request(self, invoice_number: str):
        """Dismiss a pending request"""
        if messagebox.askyesno("Confirm Dismiss", 
                             f"Are you sure you want to dismiss the request for invoice {invoice_number}?"):
            try:
                # Remove from pending requests
                if invoice_number in self.email_handler.pending_requests:
                    del self.email_handler.pending_requests[invoice_number]
                    
                # Update display
                self.update_pending_requests()
                self.log_message(f"Dismissed request for invoice {invoice_number}")
                self.update_status(f"Dismissed request for invoice {invoice_number}")
            except Exception as e:
                error_msg = f"Error dismissing request: {str(e)}"
                self.log_message(f"ERROR: {error_msg}")
                self.update_status(error_msg)
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
                # Clear any pending requests
                if self.email_handler:
                    self.email_handler.pending_requests = {}
                    self.update_pending_requests()
                
                # Reinitialize email handler
                self.email_handler = None
                
                self.update_status("\nEnvironment reset successfully. Ready for demo!")
                messagebox.showinfo("Success", "Environment has been reset successfully!")
            else:
                messagebox.showerror("Error", "Failed to reset environment. Check the logs for details.")
        except Exception as e:
            self.handle_error(e)

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
        
        if tab_text == "Chat" and self.chatbot is None:
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
        if self.chatbot is None:
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
        if self.chatbot:
            self.chatbot.reset_chat()
        self.update_chat_display("Chat cleared. You can start a new conversation.\n")

    def update_processing_state(self):
        """Update UI elements based on processing state"""
        state = 'disabled' if self.is_processing else 'normal'
        for child in self.main_tab.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, (ttk.Button, ttk.Combobox)):
                        widget.configure(state=state)

def main():
    root = tk.Tk()
    app = ReceiptAutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 