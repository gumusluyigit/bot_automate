from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from pdf_processor import PDFProcessor
from database_handler import DatabaseHandler
from email_handler import EmailHandler
import os
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import shutil

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Required for flash messages

# Configuration
PDF_SAMPLES_FOLDER = 'pdf_samples'
DOWNLOADS_FOLDER = 'downloads'
PROCESSED_FOLDER = 'processed'

# Create necessary directories
os.makedirs(PDF_SAMPLES_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Initialize handlers
db_handler = DatabaseHandler()
email_handler = EmailHandler(
    sender_email=os.getenv('SENDER_EMAIL', 'default@example.com'),
    internal_email=os.getenv('INTERNAL_EMAIL', 'internal@example.com')
)

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
        
        # Send email with PDF attachment
        success = email_handler.send_email_directly(
            invoice_number=invoice_number,
            pdf_path=pdf_path,
            company_name=request_info['company_name'],
            email=email_address
        )
        
        if success:
            # Move file to processed folder
            processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(pdf_path))
            shutil.move(pdf_path, processed_path)
            
            # Update database status
            db_handler.mark_as_sent(invoice_number, email_address)
            
            flash('Email sent successfully', 'success')
        else:
            flash('Failed to send email', 'error')
        
    except Exception as e:
        flash(f'Error sending email: {str(e)}', 'error')
    
    return redirect(url_for('pending_requests'))

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '').lower()
    
    # Simple response logic - you can expand this or integrate with a more sophisticated chatbot
    responses = {
        'hello': 'Hello! How can I help you today?',
        'hi': 'Hi there! What can I do for you?',
        'help': 'I can help you with:\n- Uploading PDFs\n- Processing PDFs\n- Sending emails\n- Downloading files',
        'upload': 'You can upload PDFs by clicking the "Upload PDF" button in the navigation menu.',
        'process': 'To process PDFs, go to the "Manual Processing" page and select the files you want to process.',
        'email': 'You can send emails from the "Pending Requests" page by clicking the "Send Email" button next to any request.',
        'download': 'PDFs can be downloaded from the "Pending Requests" page using the download button.',
    }
    
    # Find the most relevant response
    response = 'I\'m not sure how to help with that. Try asking about uploading, processing, or sending PDFs.'
    for key, value in responses.items():
        if key in message:
            response = value
            break
    
    return jsonify({'response': response})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        sender_email = request.form.get('sender_email')
        app_password = request.form.get('app_password')
        internal_email = request.form.get('internal_email')
        
        if not all([sender_email, app_password, internal_email]):
            flash('All fields are required', 'error')
            return redirect(url_for('settings'))
        
        try:
            # Save credentials
            email_handler.sender_email = sender_email
            email_handler.internal_email = internal_email
            success = email_handler.save_credentials(app_password)
            
            if success:
                # Test authentication
                if email_handler.authenticate():
                    flash('Email settings saved and authenticated successfully', 'success')
                    return redirect(url_for('settings'))
                else:
                    flash('Email settings saved but authentication failed. Please check your credentials.', 'error')
            else:
                flash('Failed to save email settings', 'error')
                
        except Exception as e:
            flash(f'Error saving settings: {str(e)}', 'error')
        
    # Load saved credentials
    saved_credentials = {}
    try:
        with open('email_config.json', 'r') as f:
            saved_credentials = json.load(f)
    except:
        pass
        
    return render_template('settings.html',
                         sender_email=email_handler.sender_email,
                         internal_email=email_handler.internal_email,
                         app_password=saved_credentials.get('app_password', ''))

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

if __name__ == '__main__':
    app.run(debug=True, port=5000) 