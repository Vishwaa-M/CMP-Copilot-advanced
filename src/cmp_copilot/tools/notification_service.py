
import os
import smtplib
from email.message import EmailMessage
import logging
from typing import Optional, List
import sys

from dotenv import load_dotenv

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

try:
   
    src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, src_path)
    from cmp_copilot.utils.config_loader import load_yaml_config
except (ImportError, ModuleNotFoundError):
    pass


def send_email(
    recipient_emails: List[str], 
    subject: str, 
    body: str, 
    attachment_path: Optional[str] = None
) -> bool:
    """
    Sends an email with an optional attachment using SMTP credentials.
    """
    # Get SMTP configuration from environment variables
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT")
    sender_email = os.getenv("SMTP_SENDER_EMAIL")
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")

    if not all([smtp_server, smtp_port_str, sender_email, sender_password]):
        logging.error(
            "SMTP configuration is missing. "
            "Please set SMTP_SERVER, SMTP_PORT, SMTP_SENDER_EMAIL, "
            "and SMTP_SENDER_PASSWORD in your .env file."
        )
        return False
    
    try:
        smtp_port = int(smtp_port_str)
    except (ValueError, TypeError):
        logging.error(f"Invalid SMTP_PORT: '{smtp_port_str}'. It must be an integer.")
        return False

    # --- Create the Email Message ---
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipient_emails)
    msg.set_content(body)

    # --- Handle the attachment ---
    if attachment_path:
        if not os.path.exists(attachment_path):
            logging.error(f"Attachment file not found at path: {attachment_path}")
            return False
        
        logging.info(f"Attaching file: {attachment_path}")
        try:
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(attachment_path)
            
            msg.add_attachment(file_data, maintype='text', subtype='html', filename=file_name)
        except Exception as e:
            logging.error(f"Failed to read or attach file: {e}", exc_info=True)
            return False

    logging.info(f"Attempting to send email to {recipient_emails} via {smtp_server}:{smtp_port}")

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        logging.info("Email sent successfully.")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP Authentication Failed. Check your sender email/password.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending email: {e}", exc_info=True)
        return False


# --- Standalone Test Block for REAL EMAIL ---
if __name__ == '__main__':
    logging.info("--- Running Notification Service REAL EMAIL Test ---")

    try:
  
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # 2. Construct the full path to the config file
        config_path = os.path.join(project_root, 'config', 'notification_config.yaml')
        logging.info(f"Attempting to load config from: {config_path}")
        
        notification_config = load_yaml_config(config_path)
        recipients = notification_config.get('manager_recipients')

        if not recipients:
            logging.error("Could not find 'manager_recipients' in config/notification_config.yaml or the file is empty.")
        else:
            TEST_SUBJECT = "CMP Copilot: Real Email Test"
            TEST_BODY = (
                "Hello Team,\n\n"
                "This is a test email from the CMP Copilot Agent to confirm that the "
                "notification service is working correctly.\n\n"
                "This email includes a dummy attachment.\n\n"
                "Regards,\n"
                "CMP Copilot Agent"
            )

            dummy_attachment_path = "real_test_report.html"
            with open(dummy_attachment_path, "w") as f:
                f.write("<h1>Real Test Report</h1><p>This is a real test attachment.</p>")
            
            logging.info(f"Attempting to send a real email to: {recipients}")
            success = send_email(
                recipient_emails=recipients,
                subject=TEST_SUBJECT,
                body=TEST_BODY,
                attachment_path=dummy_attachment_path
            )

            if success:
                logging.info("REAL EMAIL TEST SUCCEEDED. Please check the recipient inboxes.")
            else:
                logging.error("REAL EMAIL TEST FAILED. Please check the logs and your .env SMTP credentials.")

            os.remove(dummy_attachment_path)

    except NameError:
        logging.error("Could not import 'load_yaml_config'. Please ensure 'utils/config_loader.py' exists.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during the test: {e}", exc_info=True)
