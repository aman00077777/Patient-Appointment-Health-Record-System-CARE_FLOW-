from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db, bcrypt
from app.doctor import doctor_bp
from app.models import User, Doctor, Patient, Appointment, MedicalRecord, Prescription
from app.forms import DoctorLoginForm, PrescriptionForm

# Helper to check if current user is indeed a doctor
def doctor_only(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash("Unauthorized access. This area is reserved for Physicians.", "danger")
            return redirect(url_for('doctor.doctor_login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@doctor_bp.route('/login', methods=['GET', 'POST'])
def doctor_login():
    if current_user.is_authenticated:
        if current_user.role == 'doctor':
            return redirect(url_for('doctor.doctor_dashboard'))
        logout_user() # Clean logout if another user is logged in

    form = DoctorLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip(), role='doctor').first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash(f"Welcome back, Dr. {user.name}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('doctor.doctor_dashboard'))
        else:
            flash("Login failed. Please verify your physician email and credentials.", "danger")
            
    return render_template('doctor/login.html', form=form)


@doctor_bp.route('/logout')
@login_required
def doctor_logout():
    logout_user()
    flash("Physician panel closed. You have logged out successfully.", "success")
    return redirect(url_for('main_index'))


@doctor_bp.route('/dashboard')
@login_required
@doctor_only
def doctor_dashboard():
    doctor = current_user.doctor_profile
    if not doctor:
        flash("Physician profile not found.", "danger")
        return redirect(url_for('main_index'))
        
    # Fetch active scheduled and completed appointments
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()
    scheduled = [a for a in appointments if a.status == 'Scheduled']
    completed = [a for a in appointments if a.status == 'Completed']

    # Date summary today helper
    today = datetime.utcnow().date()
    today_scheduled = [a for a in scheduled if a.appointment_date == today]

    return render_template('doctor/dashboard.html',
                           doctor=doctor,
                           scheduled=scheduled,
                           completed=completed,
                           today_scheduled=today_scheduled)


@doctor_bp.route('/patient/<int:patient_id>/history')
@login_required
@doctor_only
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(MedicalRecord.record_date.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.prescription_date.desc()).all()
    
    # Calculate age helper
    age = None
    if patient.date_of_birth:
        age = datetime.utcnow().date().year - patient.date_of_birth.year

    return render_template('doctor/patient_history.html',
                           patient=patient,
                           age=age,
                           records=records,
                           prescriptions=prescriptions)


@doctor_bp.route('/appointment/<int:appt_id>/prescribe', methods=['GET', 'POST'])
@login_required
@doctor_only
def prescribe(appt_id):
    doctor = current_user.doctor_profile
    appt = Appointment.query.get_or_404(appt_id)

    # Security check: Ensure this doctor owns the appointment
    if appt.doctor_id != doctor.id:
        flash("You are not authorized to write prescriptions for this appointment.", "danger")
        return redirect(url_for('doctor.doctor_dashboard'))

    # Can only prescribe for 'Scheduled' or 'Completed' (in case editing is needed)
    if appt.status == 'Cancelled':
        flash("Cannot write a prescription for a cancelled appointment.", "warning")
        return redirect(url_for('doctor.doctor_dashboard'))

    form = PrescriptionForm()
    
    # Calculate patient age
    age = None
    if appt.patient.date_of_birth:
        age = datetime.utcnow().date().year - appt.patient.date_of_birth.year
    
    # Pre-populate if already completed/prescribed
    if request.method == 'GET' and appt.status == 'Completed':
        record = appt.medical_record
        presc = appt.prescription
        if record and presc:
            form.symptoms.data = record.symptoms
            form.diagnosis.data = record.diagnosis
            form.treatment_plan.data = record.treatment_plan
            form.medications.data = presc.medications
            form.instructions.data = presc.instructions

    if form.validate_on_submit():
        # 1. Update/Add Medical Diagnosis Record
        record = MedicalRecord.query.filter_by(appointment_id=appt.id).first()
        if not record:
            record = MedicalRecord()
            record.appointment_id = appt.id
            record.patient_id = appt.patient_id
            record.doctor_id = doctor.id
            db.session.add(record)
            
        record.symptoms = form.symptoms.data.strip()
        record.diagnosis = form.diagnosis.data.strip()
        record.treatment_plan = form.treatment_plan.data.strip()
        
        # 2. Update/Add Prescription
        presc = Prescription.query.filter_by(appointment_id=appt.id).first()
        if not presc:
            presc = Prescription()
            presc.appointment_id = appt.id
            presc.patient_id = appt.patient_id
            presc.doctor_id = doctor.id
            db.session.add(presc)
            
        presc.medications = form.medications.data.strip()
        presc.instructions = form.instructions.data.strip()

        # 3. Mark appointment status as 'Completed'
        appt.status = 'Completed'
        db.session.commit()

        flash(f"Prescription and diagnosis for {appt.patient.user.name} have been saved successfully!", "success")
        return redirect(url_for('doctor.doctor_dashboard'))

    return render_template('doctor/prescription.html', appt=appt, form=form, age=age)
