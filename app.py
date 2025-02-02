from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from pdf_processor import PDFProcessor
from database_handler import DatabaseHandler
from email_handler import EmailHandler
from config_handler import ConfigHandler
import os
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import shutil
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Required for flash messages

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"  # Replace with actual API endpoint

# Initialize handlers
config_handler = ConfigHandler()
db_handler = DatabaseHandler(db_path="invoice_emails.db")

# Load email configuration
email_config = config_handler.get_config()
email_handler = EmailHandler(
    sender_email=email_config['sender_email'],
    internal_email=email_config['internal_email']
)

# If we have saved credentials, set them in the email handler
if email_config['app_password']:
    email_handler.save_credentials(email_config['app_password'])

def generate_response(user_input):
    if not DEEPSEEK_API_KEY:
        # If API is not available, use rule-based responses
        try:
            # Check for database query patterns
            lower_input = user_input.lower()
            
            # Process week-related file processing requests
            if any(keyword in lower_input for keyword in ['hafta', 'pdfleri', 'işle', 'gönder']):
                # Extract date information from the message
                # This is a simple implementation - you might want to use a more sophisticated date parser
                from datetime import datetime, timedelta
                import re
                
                # Try to find date patterns in the message
                today = datetime.now()
                if 'bu hafta' in lower_input:
                    week_start = today - timedelta(days=today.weekday())
                    week_end = week_start + timedelta(days=6)
                elif 'geçen hafta' in lower_input:
                    week_start = today - timedelta(days=today.weekday() + 7)
                    week_end = week_start + timedelta(days=6)
                else:
                    # Try to parse specific dates
                    dates = re.findall(r'\d{2}[./]\d{2}[./]\d{4}', user_input)
                    if len(dates) >= 2:
                        week_start = datetime.strptime(dates[0], '%d/%m/%Y')
                        week_end = datetime.strptime(dates[1], '%d/%m/%Y')
                    else:
                        return "Lütfen işlemek istediğiniz haftayı belirtin. Örnek: 'Bu hafta' veya '01/03/2024-07/03/2024'"
                
                # Format dates for processing
                week_range = f"{week_start.strftime('%Y-%m-%d')},{week_end.strftime('%Y-%m-%d')}"
                
                # Process the files
                from flask import current_app
                with current_app.test_client() as client:
                    response = client.post('/manual-process', data={'selected_week': week_range})
                    result = response.get_json()
                    
                    if result['success']:
                        message_parts = []
                        if result.get('processed_files'):
                            message_parts.append(f"{len(result['processed_files'])} PDF işlendi")
                        if result.get('auto_emailed_files'):
                            message_parts.append(f"{len(result['auto_emailed_files'])} PDF otomatik gönderildi")
                        if result.get('skipped_files'):
                            message_parts.append(f"{len(result['skipped_files'])} PDF atlandı")
                        
                        return ". ".join(message_parts) + "."
                    else:
                        return f"İşlem sırasında bir hata oluştu: {result.get('error', 'Bilinmeyen hata')}"
            
            # Handle email sending requests
            elif 'mail' in lower_input and any(char.isdigit() for char in user_input):
                # Extract invoice number and email address
                import re
                invoice_match = re.search(r'\d+', user_input)
                email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_input)
                
                if invoice_match and email_match:
                    invoice_number = invoice_match.group()
                    email_address = email_match.group()
                    
                    # Get company name for this invoice
                    company_name = db_handler.get_company_name_by_invoice(invoice_number)
                    if not company_name:
                        return "Bu fatura numarası için şirket bilgisi bulunamadı."
                    
                    # Send the email using the existing endpoint
                    from flask import current_app
                    with current_app.test_client() as client:
                        response = client.post('/send-email', data={
                            'invoice_number': invoice_number,
                            'email_address': email_address
                        })
                        
                        # Check if email was sent successfully
                        if 'success' in response.get_data(as_text=True):
                            # Store the email association
                            db_handler.add_company_email(company_name, email_address)
                            return f"Email {email_address} adresine başarıyla gönderildi. Bu email adresi {company_name} şirketi için kaydedildi."
                        else:
                            return "Email gönderimi sırasında bir hata oluştu. Lütfen tekrar deneyin."
                else:
                    return "Fatura numarası veya email adresi bulunamadı. Lütfen tekrar deneyin."
            
            # Handle database queries
            elif any(keyword in lower_input for keyword in ['borç', 'ödeme', 'tarih']):
                # Extract company name or invoice number
                company_name = None
                invoice_number = None
                
                # Try to find invoice number
                import re
                invoice_match = re.search(r'\d+', user_input)
                if invoice_match:
                    invoice_number = invoice_match.group()
                
                # If no invoice number, try to find company name
                if not invoice_number:
                    # This is a simple implementation - you might want to use more sophisticated NLP
                    words = user_input.split()
                    for i, word in enumerate(words):
                        if word.lower() in ['şirket', 'firma', 'kurum']:
                            if i > 0:
                                company_name = words[i-1]
                                break
                
                if company_name or invoice_number:
                    # Query the database
                    if invoice_number:
                        request_info = db_handler.get_request_by_invoice(invoice_number)
                        if request_info:
                            return f"Fatura #{invoice_number}:\nŞirket: {request_info['company_name']}\nBaşlangıç: {request_info['period_start']}\nBitiş: {request_info['period_end']}"
                    else:
                        # Get company information
                        company_info = db_handler.get_company_info(company_name)
                        if company_info:
                            return f"{company_name} için bilgiler:\nSon işlem tarihi: {company_info['last_transaction_date']}\nToplam işlem: {company_info['total_transactions']}"
                    
                    return "Belirtilen şirket veya fatura numarası için bilgi bulunamadı."
                else:
                    return "Lütfen bir şirket adı veya fatura numarası belirtin."
            
            return "Üzgünüm, ne yapmak istediğinizi anlayamadım. Lütfen daha açık bir şekilde belirtin."
            
        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return "İşlem sırasında bir hata oluştu. Lütfen tekrar deneyin."
    else:
        # Use DeepSeek API when available
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messages": [{"role": "user", "content": user_input}],
                "model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 256
            }
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.RequestException as e:
            print(f"API request error: {str(e)}")
            return "I apologize, but I encountered an error while processing your request. Please try again."
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return "I apologize, but I encountered an error while processing your request. Please try again."

# Configuration
PDF_SAMPLES_FOLDER = 'pdf_samples'
DOWNLOADS_FOLDER = 'downloads'
PROCESSED_FOLDER = 'processed'

# Create necessary directories
os.makedirs(PDF_SAMPLES_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Print database status
print("Database initialized successfully")
print(f"Using database at: {db_handler.db_path}")

@app.route('/')
def index():
    # Get recent requests from pending_requests table
    recent_requests = db_handler.get_recent_requests(limit=5)
    return render_template('index.html', recent_requests=recent_requests)

@app.route('/manual-process', methods=['GET', 'POST'])
def manual_process():
    if request.method == 'POST':
        selected_week = request.form.get('selected_week')
        
        if not selected_week:
            return jsonify({'success': False, 'error': 'No week selected'})
        
        try:
            # Parse week range
            week_start, week_end = selected_week.split(',')
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
            
            processed_files = []
            skipped_files = []
            auto_emailed_files = []
            
            # Process all PDFs in the samples folder
            for pdf_name in os.listdir(PDF_SAMPLES_FOLDER):
                pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf_name)
                if not os.path.exists(pdf_path):
                    continue

                # Extract information from PDF
                pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                
                if not pdf_info:
                    continue

                # Convert dates for comparison
                pdf_start = datetime.strptime(pdf_info['period_start'], '%Y-%m-%d')
                pdf_end = datetime.strptime(pdf_info['period_end'], '%Y-%m-%d')
                
                # Check if PDF's date range overlaps with selected week
                if not ((pdf_start <= week_end_date and pdf_end >= week_start_date) or
                        (week_start_date <= pdf_end and week_end_date >= pdf_start)):
                    continue

                # Get company name from filename if not in PDF
                company_name = pdf_info.get('company_name')
                if not company_name:
                    company_name = pdf_name.split('_')[0].replace('_', ' ').title()

                invoice_number = pdf_info['invoice_number']
                # Create a unique filename using invoice number, company name, and period dates
                safe_company_name = secure_filename(company_name)
                period_start_str = pdf_info['period_start'].replace('-', '')
                period_end_str = pdf_info['period_end'].replace('-', '')
                unique_filename = f"{safe_company_name}_{invoice_number}_{period_start_str}_{period_end_str}.pdf"
                
                download_path = os.path.join(DOWNLOADS_FOLDER, unique_filename)
                processed_path = os.path.join(PROCESSED_FOLDER, unique_filename)

                # Skip if file already exists in downloads or processed folder
                if os.path.exists(download_path) or os.path.exists(processed_path):
                    skipped_files.append({
                        'filename': pdf_name,
                        'reason': 'File already exists in downloads or processed folder'
                    })
                    continue

                # Copy file to downloads folder
                shutil.copy2(pdf_path, download_path)

                # Check if we have a matching email for auto-sending
                company_email = db_handler.get_company_email(company_name)
                
                if company_email:
                    try:
                        # Send email automatically
                        email_handler.send_email(
                            to_email=company_email,
                            subject=f'Invoice {invoice_number} for {company_name}',
                            body=f'Please find attached the invoice {invoice_number} for the period {pdf_info["period_start"]} to {pdf_info["period_end"]}.',
                            attachment_path=download_path
                        )
                        
                        # Move to processed folder after successful email
                        shutil.move(download_path, processed_path)
                        
                        auto_emailed_files.append({
                            'filename': pdf_name,
                            'invoice_number': invoice_number,
                            'company_name': company_name,
                            'email': company_email
                        })
                    except Exception as e:
                        print(f"Error sending email for {pdf_name}: {str(e)}")
                        # Keep in downloads folder if email fails
                        processed_files.append({
                            'filename': pdf_name,
                            'invoice_number': invoice_number,
                            'company_name': company_name
                        })
                else:
                    # Add to pending requests if no matching email
                    db_handler.add_pending_request(
                        invoice_number=invoice_number,
                        company_name=company_name,
                        pdf_path=download_path,
                        period_start=pdf_info['period_start'],
                        period_end=pdf_info['period_end']
                    )
                    
                    # Send notification email to internal staff
                    try:
                        # Load email credentials from the correct file
                        if not email_handler._load_credentials():  # Use the built-in method
                            raise Exception("Email settings not configured. Please configure your email settings first.")
                        
                        # Test email configuration
                        if not email_handler.authenticate():
                            raise Exception("Email authentication failed. Please check your credentials in Settings.")
                        
                        # Send the notification email
                        email_handler.send_email_directly(
                            invoice_number=invoice_number,
                            pdf_path=None,  # No attachment needed for notification
                            company_name=company_name,
                            email=email_handler.internal_email,
                            subject=f'Missing Email Address for Invoice {invoice_number}',
                            body=f'{invoice_number} numaralı şirketin mail adresi bulunamadı.\n\n'
                                 f'Bekleyen işlemleri görüntülemek için tıklayın: {request.host_url}pending'
                        )
                        print(f"Notification email sent successfully to {email_handler.internal_email}")
                    except Exception as e:
                        print(f"Error sending notification email: {str(e)}")
                        raise Exception(f"Failed to send notification email: {str(e)}")
                    
                    processed_files.append({
                        'filename': pdf_name,
                        'invoice_number': invoice_number,
                        'company_name': company_name
                    })
            
            # Prepare response message
            message_parts = []
            if processed_files:
                message_parts.append(f"Processed {len(processed_files)} PDFs")
            if auto_emailed_files:
                message_parts.append(f"Automatically emailed {len(auto_emailed_files)} PDFs")
            if skipped_files:
                message_parts.append(f"Skipped {len(skipped_files)} existing PDFs")
            
            message = ". ".join(message_parts) + "."
            
            return jsonify({
                'success': True,
                'message': message,
                'processed_files': processed_files,
                'auto_emailed_files': auto_emailed_files,
                'skipped_files': skipped_files
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    # Get list of PDFs from the samples folder
    pdfs = []
    for pdf in os.listdir(PDF_SAMPLES_FOLDER):
        try:
            pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf)
            pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
            if pdf_info:
                # Get company name from filename if not in PDF
                company_name = pdf_info.get('company_name')
                if not company_name:
                    # Extract company name from filename (before first underscore)
                    company_name = pdf.split('_')[0].replace('_', ' ').title()
                
                pdfs.append({
                    'filename': pdf,
                    'invoice_number': pdf_info['invoice_number'],
                    'company_name': company_name,
                    'period_start': pdf_info['period_start'],
                    'period_end': pdf_info['period_end']
                })
        except Exception as e:
            print(f"Error processing {pdf}: {str(e)}")
            # Try to extract dates from filename as fallback
            try:
                parts = pdf.replace('.pdf', '').split('_')
                if len(parts) >= 2:
                    date_range = parts[1]
                    period_start, period_end = date_range.split('-')
                    pdfs.append({
                        'filename': pdf,
                        'invoice_number': 'N/A',
                        'company_name': parts[0].replace('_', ' ').title(),
                        'period_start': datetime.strptime(period_start, '%Y%m%d').strftime('%Y-%m-%d'),
                        'period_end': datetime.strptime(period_end, '%Y%m%d').strftime('%Y-%m-%d')
                    })
            except Exception as e2:
                print(f"Could not extract dates from filename {pdf}: {str(e2)}")
            continue
            
    return render_template('manual_process.html', pdfs=pdfs)

@app.route('/pending')
def pending_requests():
    # Get requests directly from database instead of scanning PDF folder
    requests = db_handler.get_pending_requests()
    return render_template('pending.html', requests=requests)

@app.route('/download/<invoice_number>')
def download_pdf(invoice_number):
    try:
        # Get request info from database
        request_info = db_handler.get_request_by_invoice(invoice_number)
        if not request_info:
            flash('Invoice not found', 'error')
            return redirect(url_for('pending_requests'))
        
        pdf_path = request_info['pdf_path']
        if not os.path.exists(pdf_path):
            flash('PDF file not found', 'error')
            return redirect(url_for('pending_requests'))
        
        # Use the original filename for download
        original_filename = os.path.basename(pdf_path)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=original_filename
        )
            
    except Exception as e:
        flash(f'Error downloading PDF: {str(e)}', 'error')
        return redirect(url_for('pending_requests'))

@app.route('/send-email', methods=['POST'])
def send_email():
    email_address = request.form.get('email_address')
    invoice_number = request.form.get('invoice_number')
    
    if not email_address or not invoice_number:
        flash('Missing required information', 'error')
        return redirect(url_for('pending_requests'))
    
    try:
        # Get request info from database
        request_info = db_handler.get_request_by_invoice(invoice_number)
        if not request_info:
            flash('Invoice not found', 'error')
            return redirect(url_for('pending_requests'))
        
        pdf_path = request_info['pdf_path']
        if not os.path.exists(pdf_path):
            flash('PDF file not found', 'error')
            return redirect(url_for('pending_requests'))
        
        company_name = request_info['company_name']
        
        # Prepare email content
        subject = f'Invoice {invoice_number} for {company_name}'
        body = f'Please find attached the invoice {invoice_number} for the period {request_info["period_start"]} to {request_info["period_end"]}.'
        
        # Send email with PDF attachment
        success = email_handler.send_email(
            to_email=email_address,
            subject=subject,
            body=body,
            attachments=[pdf_path]
        )
        
        if success:
            try:
                # Move file to processed folder first
                processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(pdf_path))
                shutil.move(pdf_path, processed_path)
                
                # Store the email association and mark as sent
                db_handler.add_company_email(company_name, email_address)
                db_handler.mark_as_sent(invoice_number, email_address)
                
                flash(f'Email sent successfully and saved {email_address} for future use with {company_name}', 'success')
                return redirect(url_for('pending_requests'))
            except Exception as e:
                print(f"Error in post-send processing: {str(e)}")
                flash('Email sent but there was an error updating some information', 'warning')
        else:
            flash('Failed to send email. Please check email settings and try again.', 'error')
        
    except Exception as e:
        print(f"Error in send_email: {str(e)}")
        flash(f'Error sending email: {str(e)}', 'error')
    
    return redirect(url_for('pending_requests'))

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    
    try:
        # Generate response using the model
        response = generate_response(message)
        return jsonify({'response': response})
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return jsonify({'response': 'I apologize, but I encountered an error. Please try again.'})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Handle settings form submission
        sender_email = request.form.get('sender_email')
        app_password = request.form.get('app_password')
        internal_email = request.form.get('internal_email')
        
        if not all([sender_email, app_password, internal_email]):
            flash('All fields are required', 'error')
            return redirect(url_for('settings'))
        
        try:
            # Update email handler
            email_handler.sender_email = sender_email
            email_handler.internal_email = internal_email
            
            # Test authentication with new credentials
            if email_handler.save_credentials(app_password):
                if email_handler.authenticate():
                    # Save configuration only if authentication succeeds
                    config_handler.save_config(
                        sender_email=sender_email,
                        app_password=app_password,
                        internal_email=internal_email
                    )
                    flash('Email settings saved and authenticated successfully', 'success')
                else:
                    flash('Authentication failed with provided credentials', 'error')
            else:
                flash('Failed to save credentials', 'error')
                
        except Exception as e:
            flash(f'Error saving settings: {str(e)}', 'error')
        
        return redirect(url_for('settings'))
    
    # Get current configuration
    email_config = config_handler.get_config()
    
    # Get all companies with their current emails
    companies = db_handler.get_all_companies()
    
    return render_template('settings.html',
        sender_email=email_config['sender_email'],
        app_password=email_config['app_password'],
        internal_email=email_config['internal_email'],
        companies=companies
    )

@app.route('/reset-environment', methods=['POST'])
def reset_environment():
    try:
        # Clear downloads folder
        for file in os.listdir(DOWNLOADS_FOLDER):
            file_path = os.path.join(DOWNLOADS_FOLDER, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

        # Clear processed folder
        for file in os.listdir(PROCESSED_FOLDER):
            file_path = os.path.join(PROCESSED_FOLDER, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

        # Reset database
        db_handler.clear_all_tables()

        flash('Environment reset successfully', 'success')
    except Exception as e:
        flash(f'Error resetting environment: {str(e)}', 'error')

    return redirect(url_for('settings'))

@app.route('/update-company-email', methods=['POST'])
def update_company_email():
    company_name = request.form.get('company_name')
    new_email = request.form.get('new_email')
    old_email = request.form.get('old_email')  # Optional
    
    if not company_name or not new_email:
        flash('Company name and new email are required', 'error')
        return redirect(url_for('settings'))
    
    try:
        success = db_handler.update_company_email(company_name, new_email, old_email)
        if success:
            flash(f'Email for {company_name} updated to {new_email}', 'success')
        else:
            flash('Failed to update email', 'error')
    except Exception as e:
        flash(f'Error updating email: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/company-email-history/<company_name>')
def company_email_history(company_name):
    try:
        history = db_handler.get_company_email_history(company_name)
        return render_template('email_history.html', company_name=company_name, history=history)
    except Exception as e:
        flash(f'Error getting email history: {str(e)}', 'error')
        return redirect(url_for('settings'))

if __name__ == '__main__':
    app.run(debug=True, port=5000) 