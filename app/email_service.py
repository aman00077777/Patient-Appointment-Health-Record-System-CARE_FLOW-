import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import traceback

def send_email(to_email, subject, html_content):
    """
    Sends an email using the SMTP configurations defined in environment variables.
    Fails gracefully and prints warnings if SMTP is not configured.
    """
    mail_server = os.environ.get("MAIL_SERVER")
    mail_port = os.environ.get("MAIL_PORT")
    mail_user = os.environ.get("MAIL_USERNAME")
    mail_pass = os.environ.get("MAIL_PASSWORD")
    mail_sender = os.environ.get("MAIL_DEFAULT_SENDER", mail_user)

    # Validate if credentials are configured and not default
    if not all([mail_server, mail_port, mail_user, mail_pass]) or "your-gmail" in mail_user:
        print(f"[SMTP Simulator] Email reminder would be sent to <{to_email}>.")
        print(f"Subject: {subject}")
        print("SMTP Credentials not set or using defaults. Set MAIL_USERNAME & MAIL_PASSWORD in .env to send real emails.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_sender
        msg["To"] = to_email

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Connect and send
        server = smtplib.SMTP(mail_server, int(mail_port))
        server.starttls()
        server.login(mail_user, mail_pass)
        server.sendmail(mail_sender, to_email, msg.as_string())
        server.quit()
        print(f"[SMTP Success] Reminder email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP Error] Failed to send email to {to_email}: {str(e)}")
        traceback.print_exc()
        return False


def check_and_send_reminders(app):
    """
    Scans the database for appointments happening tomorrow and triggers reminder emails.
    """
    with app.app_context():
        from app.models import Appointment
        
        # Calculate date for tomorrow
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        print(f"[Scheduler] Scanning for appointments on {tomorrow}...")

        appointments = Appointment.query.filter_by(
            appointment_date=tomorrow,
            status='Scheduled'
        ).all()

        if not appointments:
            print(f"[Scheduler] No upcoming appointments found for {tomorrow}.")
            return

        print(f"[Scheduler] Found {len(appointments)} scheduled appointment(s) for tomorrow. Sending reminders...")
        for appt in appointments:
            patient = appt.patient
            doctor = appt.doctor
            
            patient_name = patient.user.name
            patient_email = patient.user.email
            doctor_name = doctor.user.name
            specialization = doctor.specialization
            appt_time = appt.appointment_time.strftime("%I:%M %p")
            fees = doctor.consultation_fee

            subject = f"Appointment Reminder: Dr. {doctor_name} - Tomorrow!"
            
            # Premium styled HTML email reminder
            html_body = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 0; }}
                        .container {{ max-width: 600px; margin: 20px auto; padding: 25px; border: 1px solid #e1e8ed; border-radius: 10px; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); }}
                        .header {{ background: linear-gradient(135deg, #0d6efd, #0dcaf0); padding: 20px; border-radius: 8px 8px 0 0; text-align: center; color: white; }}
                        .header h2 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                        .content {{ padding: 20px 10px; }}
                        .details-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                        .details-table td {{ padding: 12px; border-bottom: 1px solid #edf2f7; }}
                        .details-table td.label {{ font-weight: bold; color: #495057; width: 40%; }}
                        .details-table td.value {{ color: #212529; }}
                        .footer {{ text-align: center; font-size: 12px; color: #888888; border-top: 1px solid #e1e8ed; padding-top: 15px; margin-top: 20px; }}
                        .btn {{ display: inline-block; padding: 10px 20px; color: white; background-color: #0d6efd; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 15px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>Healthcare Appointment Reminder</h2>
                        </div>
                        <div class="content">
                            <p>Dear <strong>{patient_name}</strong>,</p>
                            <p>This is a friendly reminder that you have an upcoming consultation scheduled with us tomorrow. Here are the details of your appointment:</p>
                            
                            <table class="details-table">
                                <tr>
                                    <td class="label">Doctor:</td>
                                    <td class="value">Dr. {doctor_name} ({specialization})</td>
                                </tr>
                                <tr>
                                    <td class="label">Date:</td>
                                    <td class="value">{tomorrow.strftime('%B %d, %Y')} (Tomorrow)</td>
                                </tr>
                                <tr>
                                    <td class="label">Time:</td>
                                    <td class="value">{appt_time}</td>
                                </tr>
                                <tr>
                                    <td class="label">Consultation Fee:</td>
                                    <td class="value">INR {fees:.2f}</td>
                                </tr>
                            </table>
                            
                            <p>If you need to make changes or cancel your booking, please log in to your patient dashboard at least 4 hours before the appointment.</p>
                            <p>Please reach the clinic 10 minutes prior to your slot time. Thank you for choosing our Patient Appointment & Health Record System.</p>
                        </div>
                        <div class="footer">
                            <p>&copy; {datetime.utcnow().year} Medical Healthcare Portal. All rights reserved.</p>
                            <p>This is an automated system email. Please do not reply directly to this message.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            send_email(patient_email, subject, html_body)


def init_scheduler(app):
    """
    Starts the background scheduler and adds the reminder checking job.
    """
    scheduler = BackgroundScheduler()
    # Runs the check every hour to see if tomorrow's reminders need sending
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger="interval",
        hours=1,
        args=[app],
        id="appointment_reminders_job",
        replace_existing=True
    )
    scheduler.start()
    print("[Scheduler] Background scheduler initialized and checking job registered.")
    
    # Run once at startup on a separate thread/process context to avoid blocking the main server
    try:
        import threading
        threading.Thread(target=check_and_send_reminders, args=[app], daemon=True).start()
    except Exception as e:
        print(f"[Scheduler] Initial startup check failed: {e}")
