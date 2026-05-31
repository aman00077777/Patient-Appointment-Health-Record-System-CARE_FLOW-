from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

# Initialize db instance here; it will be bound in the app factory
db = SQLAlchemy()

def get_current_date():
    return datetime.utcnow().date()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient', 'doctor', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient_profile = db.relationship('Patient', backref='user', uselist=False, cascade="all, delete-orphan")
    doctor_profile = db.relationship('Doctor', backref='user', uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    address = db.Column(db.String(200), nullable=True)

    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade="all, delete-orphan")
    medical_records = db.relationship('MedicalRecord', backref='patient', lazy=True, cascade="all, delete-orphan")
    prescriptions = db.relationship('Prescription', backref='patient', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient {self.user.name if self.user else self.id}>"


class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    consultation_fee = db.Column(db.Float, default=0.0, nullable=False)
    available_hours = db.Column(db.String(100), default="09:00 - 17:00", nullable=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='doctor', lazy=True, cascade="all, delete-orphan")
    medical_records = db.relationship('MedicalRecord', backref='doctor', lazy=True, cascade="all, delete-orphan")
    prescriptions = db.relationship('Prescription', backref='doctor', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Doctor {self.user.name if self.user else self.id} - {self.specialization}>"


class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='Scheduled', nullable=False) # 'Scheduled', 'Completed', 'Cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-one or one-to-many attachments
    prescription = db.relationship('Prescription', backref='appointment', uselist=False, cascade="all, delete-orphan")
    medical_record = db.relationship('MedicalRecord', backref='appointment', uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Appointment P:{self.patient_id} -> D:{self.doctor_id} on {self.appointment_date}>"


class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), unique=True, nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    record_date = db.Column(db.Date, default=get_current_date, nullable=False)
    symptoms = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    treatment_plan = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MedicalRecord P:{self.patient_id} D:{self.doctor_id} - {self.record_date}>"


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    prescription_date = db.Column(db.Date, default=get_current_date, nullable=False)
    medications = db.Column(db.Text, nullable=False) # Semi-colon or newline separated list of drugs
    instructions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Prescription P:{self.patient_id} D:{self.doctor_id} - {self.prescription_date}>"
