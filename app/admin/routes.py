import io
import json
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, logout_user, current_user, login_required
from app import db, bcrypt
from app.admin import admin_bp
from app.models import User, Patient, Doctor, Appointment
from app.forms import AdminLoginForm, DoctorCreationForm

# Plotly imports for administrative dashboard charts
import plotly
import plotly.graph_objs as go
from sqlalchemy import func

# ReportLab imports for admin system reports PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Helper to check if current user is indeed an admin
def admin_only(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Unauthorized access. This area is reserved for Administrators.", "danger")
            return redirect(url_for('admin.admin_login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin_dashboard'))
        logout_user() # Clean logout if another user is logged in

    form = AdminLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip(), role='admin').first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash("Administrative portal accessed successfully.", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('admin.admin_dashboard'))
        else:
            flash("Authentication failed. Please verify admin email and key credentials.", "danger")
            
    return render_template('admin/login.html', form=form)


@admin_bp.route('/logout')
@login_required
def admin_logout():
    logout_user()
    flash("Admin portal closed. You have logged out successfully.", "success")
    return redirect(url_for('main_index'))


@admin_bp.route('/dashboard')
@login_required
@admin_only
def admin_dashboard():
    # 1. Base Statistics Metrics
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    
    appointments = Appointment.query.all()
    appt_scheduled = len([a for a in appointments if a.status == 'Scheduled'])
    appt_completed = len([a for a in appointments if a.status == 'Completed'])
    appt_cancelled = len([a for a in appointments if a.status == 'Cancelled'])
    total_appointments = len(appointments)

    # 2. Plotly Chart 1: Appointment Volume Trends (Last 7 Days)
    today = datetime.utcnow().date()
    date_labels = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    
    # Query database counts grouped by date
    # Supporting standard SQLAlchemy query compatible with both SQLite and Postgres
    appt_by_date = db.session.query(
        func.date(Appointment.appointment_date).label('date'),
        func.count(Appointment.id).label('count')
    ).group_by(func.date(Appointment.appointment_date)).all()
    
    appt_date_dict = {str(d[0]): d[1] for d in appt_by_date if d[0] is not None}
    counts = [appt_date_dict.get(date, 0) for date in date_labels]

    # Style Plotly Line Chart
    trace1 = go.Scatter(
        x=date_labels,
        y=counts,
        mode='lines+markers',
        name='Appointments',
        line=dict(color='#0f766e', width=4),
        marker=dict(size=8, color='#1e40af'),
        fill='tozeroy',
        fillcolor='rgba(15, 118, 110, 0.05)'
    )
    
    layout1 = go.Layout(
        title=dict(text='Weekly Consultation Roster Trends', font=dict(family='Outfit, sans-serif', size=16, color='#0f766e')),
        xaxis=dict(title='Appointment Date', gridcolor='#f1f5f9'),
        yaxis=dict(title='Total Bookings', gridcolor='#f1f5f9', tickformat=',d'),
        margin=dict(l=40, r=40, t=40, b=40),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    fig1 = go.Figure(data=[trace1], layout=layout1)
    chart_json1 = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)

    # 3. Plotly Chart 2: Doctor Specialization Ratios
    spec_query = db.session.query(
        Doctor.specialization,
        func.count(Doctor.id)
    ).group_by(Doctor.specialization).all()

    spec_labels = [s[0] for s in spec_query]
    spec_counts = [s[1] for s in spec_query]

    if not spec_labels:
        spec_labels = ["No Specializations"]
        spec_counts = [1]

    # Style Pie Chart
    trace2 = go.Pie(
        labels=spec_labels,
        values=spec_counts,
        hole=0.4,
        marker=dict(colors=['#0f766e', '#1e40af', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'])
    )
    
    layout2 = go.Layout(
        title=dict(text='Consultant Specialization Share', font=dict(family='Outfit, sans-serif', size=16, color='#0f766e')),
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation='h', y=-0.1)
    )
    fig2 = go.Figure(data=[trace2], layout=layout2)
    chart_json2 = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)

    # Recent Appointments listing for preview
    recent_appts = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_patients=total_patients,
                           total_doctors=total_doctors,
                           appt_scheduled=appt_scheduled,
                           appt_completed=appt_completed,
                           appt_cancelled=appt_cancelled,
                           total_appointments=total_appointments,
                           chart_json1=chart_json1,
                           chart_json2=chart_json2,
                           recent_appts=recent_appts)


@admin_bp.route('/doctors', methods=['GET', 'POST'])
@login_required
@admin_only
def manage_doctors():
    form = DoctorCreationForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        # 1. Create doctor base User
        user = User(
            email=form.email.data.strip(),
            password_hash=hashed_pw,
            name=form.name.data.strip(),
            role='doctor'
        )
        db.session.add(user)
        db.session.flush() # Flushing to get user.id

        # 2. Create associated Doctor profile
        doctor = Doctor(
            user_id=user.id,
            specialization=form.specialization.data,
            license_number=form.license_number.data.strip(),
            consultation_fee=form.consultation_fee.data,
            available_hours=form.available_hours.data.strip()
        )
        db.session.add(doctor)
        db.session.commit()

        flash(f"Successfully onboarded Dr. {form.name.data} as consulting specialist!", "success")
        return redirect(url_for('admin.manage_doctors'))

    # Fetch list of existing doctors
    doctors = Doctor.query.order_by(Doctor.id.desc()).all()
    return render_template('admin/manage_doctors.html', form=form, doctors=doctors)


@admin_bp.route('/report/pdf')
@login_required
@admin_only
def download_patient_report():
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    appointments = Appointment.query.all()

    buffer = io.BytesIO()

    # Setup Document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor('#0f766e'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=15,
        spaceAfter=8
    )

    normal_style = ParagraphStyle(
        'MainBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )

    bold_label = ParagraphStyle(
        'BoldLabel',
        parent=normal_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Hospital Header Block
    story.append(Paragraph("CareFlow Medical Clinic System Report", title_style))
    story.append(Paragraph(f"Clinic Administrative System Health Summary | Export Date: {datetime.utcnow().strftime('%B %d, %Y')}", subtitle_style))
    story.append(Spacer(1, 0.05 * inch))

    # Divider
    hr_table = Table([[""]], colWidths=[532])
    hr_table.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 2.5, colors.HexColor('#0f766e')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(hr_table)
    story.append(Spacer(1, 0.15 * inch))

    # 2. General Portal Statistics Grid
    comp_rate = (len([a for a in appointments if a.status == 'Completed']) / len(appointments) * 100) if appointments else 0.0
    
    stats_data = [
        [
            Paragraph("System Metric", bold_label),
            Paragraph("Total Registered Count", bold_label),
            Paragraph("Percentage Share / Performance", bold_label)
        ],
        [
            Paragraph("Registered Patient Accounts", normal_style),
            Paragraph(f"{len(patients)}", normal_style),
            Paragraph("100%", normal_style)
        ],
        [
            Paragraph("Consulting Onboarded Doctors", normal_style),
            Paragraph(f"{len(doctors)}", normal_style),
            Paragraph(f"{len(doctors)} active specialties", normal_style)
        ],
        [
            Paragraph("Consolidated Clinic Bookings", normal_style),
            Paragraph(f"{len(appointments)}", normal_style),
            Paragraph(f"Completion Rate: {comp_rate:.1f}%", normal_style)
        ]
    ]

    stats_table = Table(stats_data, colWidths=[200, 150, 182])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(Paragraph("I. Portal Operational Statistics Overview", h2_style))
    story.append(stats_table)
    story.append(Spacer(1, 0.2 * inch))

    # 3. Patient Detailed Database Grid
    story.append(Paragraph("II. Complete Patient Registrations Roster", h2_style))

    patient_headers = [
        Paragraph("<b>Patient Name</b>", bold_label),
        Paragraph("<b>Phone</b>", bold_label),
        Paragraph("<b>DOB</b>", bold_label),
        Paragraph("<b>Blood</b>", bold_label),
        Paragraph("<b>Gender</b>", bold_label),
        Paragraph("<b>Visits Count</b>", bold_label)
    ]
    patient_rows = [patient_headers]

    for p in patients:
        visits = len(p.appointments)
        dob_str = p.date_of_birth.strftime('%Y-%m-%d') if p.date_of_birth else 'N/A'
        
        row = [
            Paragraph(p.user.name, normal_style),
            Paragraph(p.phone or 'N/A', normal_style),
            Paragraph(dob_str, normal_style),
            Paragraph(p.blood_group, normal_style),
            Paragraph(p.gender, normal_style),
            Paragraph(f"{visits} visit(s)", normal_style)
        ]
        patient_rows.append(row)

    patient_table = Table(patient_rows, colWidths=[130, 90, 80, 50, 70, 112])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    for i in range(6):
        patient_rows[0][i].style.textColor = colors.white

    story.append(patient_table)
    story.append(Spacer(1, 0.3 * inch))

    # 4. Signature Sign Off Block
    sig_data = [
        ["", ""],
        ["", Paragraph("____________________________", bold_label)],
        ["", Paragraph("System Administrator Signature", bold_label)],
        ["", Paragraph("CareFlow Operations Hub", normal_style)],
    ]
    sig_table = Table(sig_data, colWidths=[320, 212])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))
    story.append(KeepTogether([sig_table]))

    # Build PDF doc
    doc.build(story)

    # Return stream as downloadable attachment
    buffer.seek(0)
    filename = f"CareFlow_System_Report_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )
