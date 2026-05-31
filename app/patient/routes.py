import io
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, logout_user, current_user, login_required
from app import db, bcrypt
from app.patient import patient_bp
from app.models import User, Patient, Doctor, Appointment, Prescription, MedicalRecord
from app.forms import PatientRegisterForm, PatientLoginForm, BookAppointmentForm

# ReportLab imports for Prescription PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Helper to check if current user is indeed a patient
def patient_only(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'patient':
            flash("Unauthorized access. This area is reserved for Patients.", "danger")
            return redirect(url_for('patient.patient_login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@patient_bp.route('/register', methods=['GET', 'POST'])
def patient_register():
    if current_user.is_authenticated:
        return redirect(url_for('main_index'))
    
    form = PatientRegisterForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        # 1. Create Base User
        user = User(
            email=form.email.data.strip(),
            password_hash=hashed_pw,
            name=form.name.data.strip(),
            role='patient'
        )
        db.session.add(user)
        db.session.flush() # Flushing to get user.id

        # 2. Create Patient Profile
        patient = Patient(
            user_id=user.id,
            phone=form.phone.data.strip(),
            date_of_birth=form.date_of_birth.data,
            gender=form.gender.data,
            blood_group=form.blood_group.data,
            address=form.address.data.strip()
        )
        db.session.add(patient)
        db.session.commit()

        login_user(user)
        flash("Your account has been successfully created. Welcome to CareFlow Portal!", "success")
        return redirect(url_for('patient.patient_dashboard'))
        
    return render_template('patient/register.html', form=form)


@patient_bp.route('/login', methods=['GET', 'POST'])
def patient_login():
    if current_user.is_authenticated:
        if current_user.role == 'patient':
            return redirect(url_for('patient.patient_dashboard'))
        logout_user() # Clean logout if another user is logged in
        
    form = PatientLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip(), role='patient').first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('patient.patient_dashboard'))
        else:
            flash("Login failed. Please verify your email and password.", "danger")
            
    return render_template('patient/login.html', form=form)


@patient_bp.route('/logout')
@login_required
def patient_logout():
    logout_user()
    flash("You have logged out successfully.", "success")
    return redirect(url_for('main_index'))


@patient_bp.route('/dashboard')
@login_required
@patient_only
def patient_dashboard():
    patient = current_user.patient_profile
    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for('main_index'))
        
    # Fetch categorized appointments
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    scheduled = [a for a in appointments if a.status == 'Scheduled']
    completed = [a for a in appointments if a.status == 'Completed']
    cancelled = [a for a in appointments if a.status == 'Cancelled']

    # Fetch medical history and prescriptions
    records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(MedicalRecord.record_date.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.prescription_date.desc()).all()

    # Calculate age helper
    age = None
    if patient.date_of_birth:
        age = datetime.utcnow().date().year - patient.date_of_birth.year

    return render_template('patient/dashboard.html', 
                           patient=patient, 
                           age=age,
                           scheduled=scheduled, 
                           completed=completed, 
                           cancelled=cancelled,
                           records=records,
                           prescriptions=prescriptions)


@patient_bp.route('/book', methods=['GET', 'POST'])
@login_required
@patient_only
def book_appt():
    patient = current_user.patient_profile
    form = BookAppointmentForm()
    
    # Populate doctors choice dynamically
    doctors = Doctor.query.all()
    form.doctor.choices = [(doc.id, f"Dr. {doc.user.name} ({doc.specialization}) - Fees: INR {doc.consultation_fee}") for doc in doctors]

    if form.validate_on_submit():
        doctor_id = form.doctor.data
        appt_date = form.appointment_date.data
        appt_time_str = form.appointment_time.data
        
        # Prevent booking in the past
        if appt_date < datetime.utcnow().date():
            flash("You cannot book an appointment for a past date.", "danger")
            return render_template('patient/book.html', form=form)

        # Parse string time to Time object
        appt_time = datetime.strptime(appt_time_str, "%H:%M:%S").time()

        # Double Booking check: Is this doctor already booked at this exact date and time?
        already_booked = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status='Scheduled'
        ).first()

        if already_booked:
            flash("This time slot is already booked for this doctor. Please pick another time slot or date.", "warning")
            return render_template('patient/book.html', form=form)

        # Create Appointment
        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status='Scheduled'
        )
        db.session.add(appt)
        db.session.commit()
        
        flash("Your appointment has been successfully scheduled!", "success")
        return redirect(url_for('patient.patient_dashboard'))

    return render_template('patient/book.html', form=form)


@patient_bp.route('/appointment/cancel/<int:appt_id>', methods=['POST'])
@login_required
@patient_only
def cancel_appt(appt_id):
    patient = current_user.patient_profile
    appt = Appointment.query.get_or_404(appt_id)

    # Security check: Ensure patient owns this appointment
    if appt.patient_id != patient.id:
        flash("You are not authorized to cancel this appointment.", "danger")
        return redirect(url_for('patient.patient_dashboard'))

    # Business rule: Can only cancel 'Scheduled' appointments
    if appt.status != 'Scheduled':
        flash("This appointment cannot be cancelled because it is already marked as " + appt.status + ".", "warning")
        return redirect(url_for('patient.patient_dashboard'))

    appt.status = 'Cancelled'
    db.session.commit()
    flash("Your appointment has been successfully cancelled.", "success")
    return redirect(url_for('patient.patient_dashboard'))


@patient_bp.route('/prescription/<int:presc_id>/pdf')
@login_required
def download_prescription(presc_id):
    prescription = Prescription.query.get_or_404(presc_id)
    
    # Security: Ensure Patient or Doctor connected to this prescription is viewing it
    if current_user.role == 'patient' and prescription.patient_id != current_user.patient_profile.id:
        flash("Access Denied.", "danger")
        return redirect(url_for('patient.patient_dashboard'))
    elif current_user.role == 'doctor' and prescription.doctor_id != current_user.doctor_profile.id:
        flash("Access Denied.", "danger")
        return redirect(url_for('doctor.doctor_dashboard'))

    patient = prescription.patient
    doctor = prescription.doctor

    # Create byte stream buffer
    buffer = io.BytesIO()

    # Build prescription PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom styles definitions for premium appearance
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#0f766e'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=12,
        spaceAfter=6
    )

    normal_style = ParagraphStyle(
        'MainBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#1e293b')
    )

    bold_label = ParagraphStyle(
        'BoldLabel',
        parent=normal_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Hospital Header Block
    story.append(Paragraph("CareFlow Medical Clinic", title_style))
    story.append(Paragraph("123 Healthcare Boulevard, Tech City | Email: support@careflow.com | Phone: +91 98765 43210", subtitle_style))
    story.append(Spacer(1, 0.1 * inch))

    # Decorative Horizontal Line separator
    hr_table = Table([[""]], colWidths=[532])
    hr_table.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 2.5, colors.HexColor('#0f766e')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(hr_table)
    story.append(Spacer(1, 0.2 * inch))

    # 2. Patient & Doctor Details Info Block
    details_data = [
        [
            Paragraph("PATIENT DETAILS", bold_label), 
            Paragraph("DOCTOR DETAILS", bold_label)
        ],
        [
            Paragraph(f"<b>Name:</b> {patient.user.name}", normal_style),
            Paragraph(f"<b>Name:</b> Dr. {doctor.user.name}", normal_style)
        ],
        [
            Paragraph(f"<b>Age / Gender:</b> {datetime.utcnow().date().year - patient.date_of_birth.year if patient.date_of_birth else 'N/A'} / {patient.gender}", normal_style),
            Paragraph(f"<b>Specialization:</b> {doctor.specialization}", normal_style)
        ],
        [
            Paragraph(f"<b>Blood Group:</b> {patient.blood_group}", normal_style),
            Paragraph(f"<b>License No:</b> {doctor.license_number}", normal_style)
        ],
        [
            Paragraph(f"<b>Date:</b> {prescription.prescription_date.strftime('%B %d, %Y')}", normal_style),
            Paragraph(f"<b>Rx ID:</b> RX-{prescription.id:04d}", normal_style)
        ]
    ]

    details_table = Table(details_data, colWidths=[266, 266])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#f8fafc')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (1,0), 1, colors.HexColor('#cbd5e1')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 0.25 * inch))

    # 3. Diagnosis & Symptoms Section
    story.append(Paragraph("Clinical Diagnosis", h2_style))
    appt = prescription.appointment
    symptoms_text = appt.medical_record.symptoms if appt.medical_record else "No symptoms notes provided."
    diagnosis_text = appt.medical_record.diagnosis if appt.medical_record else "Clinical evaluation completed."

    diagnosis_data = [
        [Paragraph("<b>Reported Symptoms:</b>", bold_label), Paragraph(symptoms_text, normal_style)],
        [Paragraph("<b>Clinical Diagnosis:</b>", bold_label), Paragraph(diagnosis_text, normal_style)]
    ]
    diag_table = Table(diagnosis_data, colWidths=[140, 392])
    diag_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 0.25 * inch))

    # 4. Rx Medications Table Section
    story.append(Paragraph("<font size=16 color='#0f766e'><b>Rx</b></font> (Prescribed Medications)", h2_style))
    
    meds_headers = [
        Paragraph("<b>Medication Name</b>", bold_label),
        Paragraph("<b>Dosage</b>", bold_label),
        Paragraph("<b>Frequency</b>", bold_label),
        Paragraph("<b>Duration</b>", bold_label)
    ]
    
    meds_rows = [meds_headers]
    
    # Parse medications content
    # Format expected: Medicine - Dosage - Frequency - Duration
    raw_meds = prescription.medications.split('\n')
    for m in raw_meds:
        if not m.strip():
            continue
        parts = m.split('-')
        # If parts don't equal 4, put the whole string in first column
        if len(parts) >= 4:
            row_data = [
                Paragraph(parts[0].strip(), normal_style),
                Paragraph(parts[1].strip(), normal_style),
                Paragraph(parts[2].strip(), normal_style),
                Paragraph(parts[3].strip(), normal_style)
            ]
        else:
            row_data = [
                Paragraph(m.strip(), normal_style),
                Paragraph("-", normal_style),
                Paragraph("-", normal_style),
                Paragraph("-", normal_style)
            ]
        meds_rows.append(row_data)

    meds_table = Table(meds_rows, colWidths=[200, 100, 116, 116])
    meds_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    # Quick fix for text header color in table
    for i in range(4):
        meds_rows[0][i].style.textColor = colors.white
        
    story.append(meds_table)
    story.append(Spacer(1, 0.25 * inch))

    # 5. Instructions Section
    if prescription.instructions:
        story.append(Paragraph("Special Instructions & Advice", h2_style))
        story.append(Paragraph(prescription.instructions, normal_style))
        story.append(Spacer(1, 0.3 * inch))

    # 6. Signature Block
    sig_data = [
        ["", ""],
        ["", Paragraph("____________________________", bold_label)],
        ["", Paragraph(f"Dr. {doctor.user.name}", bold_label)],
        ["", Paragraph(doctor.specialization, normal_style)],
    ]
    sig_table = Table(sig_data, colWidths=[320, 212])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether([sig_table]))

    # Build PDF doc
    doc.build(story)

    # Return stream as downloadable attachment
    buffer.seek(0)
    filename = f"prescription_RX_{prescription.id:04d}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )
