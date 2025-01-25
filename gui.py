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

class ReceiptAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Receipt Automation")
        self.root.geometry("1000x800")
        
        # Initialize logging
        self.log_file = "automation_log.txt"
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create tabs
        self.main_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.pending_tab = ttk.Frame(self.notebook)
        self.logs_tab = ttk.Frame(self.notebook)  # New logs tab
        
        self.notebook.add(self.main_tab, text='Process Receipts')
        self.notebook.add(self.pending_tab, text='Pending Requests')
        self.notebook.add(self.settings_tab, text='Settings')
        self.notebook.add(self.logs_tab, text='Logs')  # Add logs tab
        
        self.setup_main_tab()
        self.setup_pending_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()  # Setup logs tab
        
        # Load settings
        self.load_settings()
        
        # Initialize automation components
        self.download_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        self.web_automation = WebAutomation(self.download_dir)
        self.email_handler = None  # Will be initialized when processing receipts
        
        self.log_message("Application started")

    def setup_main_tab(self):
        """Setup the main receipt processing tab"""
        # Processing Options
        options_frame = ttk.LabelFrame(self.main_tab, text="Processing Options", padding="10")
        options_frame.pack(fill='x', padx=10, pady=5)
        
        # Process All Button
        ttk.Button(options_frame, text="Process All Unprocessed PDFs", 
                  command=self.process_all_receipts).pack(side='left', padx=5)
        
        # Process by Date
        date_frame = ttk.LabelFrame(options_frame, text="Process by Date", padding="5")
        date_frame.pack(side='left', padx=20)
        
        ttk.Label(date_frame, text="Select Date:").pack(side='left', padx=5)
        self.start_date = DateEntry(date_frame, width=12, background='darkblue',
                                  foreground='white', borderwidth=2,
                                  firstweekday='monday')
        self.start_date.pack(side='left', padx=5)
        
        ttk.Button(date_frame, text="Process Selected Week", 
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
        
    def process_all_receipts(self):
        """Process all unprocessed PDFs"""
        try:
            if not self.check_email_settings():
                return
                
            self.log_message("Starting to process all unprocessed PDFs")
            self.update_status("="*50)
            self.update_status("Processing All Unprocessed PDFs")
            self.update_status("="*50)
            
            # Get all unprocessed PDFs
            pdfs = self.web_automation.search_and_download_pdf()
            
            if not pdfs:
                self.log_message("No unprocessed PDFs found")
                self.update_status("No unprocessed PDFs found")
                return
                
            self.process_pdf_list(pdfs)
            
        except Exception as e:
            self.handle_error(e)
            
    def process_selected_week(self):
        """Process PDFs for selected week"""
        try:
            if not self.check_email_settings():
                return
                
            # Get selected week dates
            start_date = self.start_date.get_date()
            end_date = start_date + timedelta(days=6)
            date_str = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
            
            self.log_message(f"Processing PDFs for week {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            self.update_status("="*50)
            self.update_status(f"Processing PDFs for Week: {start_date.strftime('%Y-%m-%d')} "
                             f"to {end_date.strftime('%Y-%m-%d')}")
            self.update_status("="*50)
            
            # Get PDFs for selected week
            pdfs = self.web_automation.search_and_download_pdf(date_str)
            
            if not pdfs:
                self.log_message("No unprocessed PDFs found for selected week")
                self.update_status("No unprocessed PDFs found for selected week")
                return
                
            self.process_pdf_list(pdfs)
            
        except Exception as e:
            self.handle_error(e)
            
    def process_pdf_list(self, pdf_paths: list):
        """Process a list of PDFs"""
        total = len(pdf_paths)
        processed = 0
        failed = 0
        skipped = 0
        
        for pdf_path in pdf_paths:
            try:
                self.update_status(f"\nProcessing PDF ({processed + 1}/{total}): {os.path.basename(pdf_path)}")
                
                if not PDFProcessor.validate_pdf(pdf_path):
                    raise Exception("Invalid PDF file")
                self.update_status("PDF validation successful!")
                
                invoice_info = PDFProcessor.extract_invoice_info(pdf_path)
                invoice_number = invoice_info.get('invoice_number')
                
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
                    # Request email from internal department
                    self.update_status(f"No email found for invoice {invoice_number}")
                    subject = f"{invoice_number} numaralı kurum için mail adresi bulunamadı."
                    if self.email_handler.request_company_email(invoice_number, subject, pdf_path):
                        self.update_status("Email request sent to internal department")
                        self.update_pending_requests()
                        # Don't mark as processed yet - will be marked when email is received and PDF is sent
                        processed += 1
                    else:
                        raise Exception("Failed to send email request to internal department")
                        
            except Exception as e:
                self.update_status(f"Error processing {os.path.basename(pdf_path)}: {str(e)}")
                failed += 1
                
        self.update_status("\n" + "="*50)
        self.update_status(f"Processing completed: {processed} successful, {skipped} skipped, {failed} failed")
        if failed == 0:
            if skipped > 0:
                messagebox.showinfo("Success", f"Processing completed: {processed} successful, {skipped} skipped (already sent)")
            else:
                messagebox.showinfo("Success", "All PDFs processed successfully!")
        else:
            messagebox.showwarning("Warning", f"Processing completed with {failed} errors")
            
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
        # Controls frame
        controls_frame = ttk.Frame(self.pending_tab, padding="10")
        controls_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Check for Responses", 
                  command=self.check_email_responses).pack(side='left', padx=5)
        
        # Pending requests list
        list_frame = ttk.LabelFrame(self.pending_tab, text="Pending Email Requests", 
                                  padding="10")
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create treeview
        columns = ('Invoice', 'Company', 'Request Time', 'Status')
        self.pending_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            self.pending_tree.heading(col, text=col)
            self.pending_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, 
                                command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=scrollbar.set)
        
        self.pending_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def check_email_responses(self):
        """Check for responses from internal department"""
        if not self.email_handler:
            self.email_handler = EmailHandler(
                self.sender_email.get(),
                self.internal_email.get()
            )
        
        self.log_message("Checking for email responses")
        self.update_status("\nChecking for email responses...")
        response = self.email_handler.check_for_responses()
        
        if response:
            invoice_number = response['invoice_number']
            company_email = response['company_email']
            details = response['request_details']
            
            self.log_message(f"Received response for invoice {invoice_number} (Company email: {company_email})")
            self.update_status(f"Received response for invoice {invoice_number}")
            self.update_status(f"Company email: {company_email}")
            
            # Send receipt to company
            if details.get('pdf_path'):
                pdf_path = details['pdf_path']
                self.log_message(f"Sending receipt to company ({company_email})")
                self.update_status(f"Sending receipt to company ({company_email})...")
                if self.email_handler.send_receipt_to_company(
                    company_email, invoice_number, pdf_path
                ):
                    self.log_message("Receipt sent to company successfully")
                    self.update_status("Receipt sent to company successfully")
                    # Mark PDF as processed only after successful sending
                    self.web_automation.mark_as_processed(pdf_path)
                    # Remove from pending requests
                    if invoice_number in self.email_handler.pending_requests:
                        del self.email_handler.pending_requests[invoice_number]
                    # Update pending requests list
                    self.update_pending_requests()
                else:
                    error_msg = "Failed to send receipt to company"
                    self.log_message(f"ERROR: {error_msg}")
                    self.update_status(error_msg)
        else:
            self.log_message("No new responses found")
            self.update_status("No new responses found")

    def update_pending_requests(self):
        """Update the pending requests treeview"""
        # Clear existing items
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)
        
        if self.email_handler and self.email_handler.pending_requests:
            # Add pending requests
            for invoice, details in self.email_handler.pending_requests.items():
                self.pending_tree.insert('', 'end', values=(
                    invoice,
                    details['company_name'],
                    details['request_time'].strftime('%Y-%m-%d %H:%M'),
                    'Waiting for Response'
                ))
            self.update_status(f"Updated pending requests list: {len(self.email_handler.pending_requests)} items")

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

def main():
    root = tk.Tk()
    app = ReceiptAutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 