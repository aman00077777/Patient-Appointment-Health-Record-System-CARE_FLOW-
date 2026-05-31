from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, TimeField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange
from app.models import User, Doctor

class PatientRegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('', 'Select Gender'), ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    blood_group = SelectField('Blood Group', choices=[
        ('', 'Select Blood Group'),
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-')
    ], validators=[DataRequired()])
    address = TextAreaField('Residential Address', validators=[DataRequired(), Length(max=200)])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email address is already registered. Please choose another one.')


class PatientLoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class DoctorLoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class AdminLoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class BookAppointmentForm(FlaskForm):
    doctor = SelectField('Select Doctor', coerce=int, validators=[DataRequired()])
    appointment_date = DateField('Appointment Date', validators=[DataRequired()])
    appointment_time = SelectField('Preferred Time Slot', choices=[
        ('', 'Select Time Slot'),
        ('09:00:00', '09:00 AM'),
        ('09:30:00', '09:30 AM'),
        ('10:00:00', '10:00 AM'),
        ('10:30:00', '10:30 AM'),
        ('11:00:00', '11:00 AM'),
        ('11:30:00', '11:30 AM'),
        ('12:00:00', '12:00 PM'),
        ('12:30:00', '12:30 PM'),
        ('14:00:00', '02:00 PM'),
        ('14:30:00', '02:30 PM'),
        ('15:00:00', '03:00 PM'),
        ('15:30:00', '03:30 PM'),
        ('16:00:00', '04:00 PM'),
        ('16:30:00', '04:30 PM')
    ], validators=[DataRequired()])
    submit = SubmitField('Book Appointment')


class DoctorCreationForm(FlaskForm):
    name = StringField('Doctor Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=100)])
    specialization = SelectField('Specialization', choices=[
        ('', 'Select Specialization'),
        ('General Physician', 'General Physician'),
        ('Cardiologist', 'Cardiologist'),
        ('Dermatologist', 'Dermatologist'),
        ('Pediatrician', 'Pediatrician'),
        ('Neurologist', 'Neurologist'),
        ('Orthopedic', 'Orthopedic'),
        ('Gynecologist', 'Gynecologist'),
        ('Psychiatrist', 'Psychiatrist')
    ], validators=[DataRequired()])
    license_number = StringField('Medical License Number', validators=[DataRequired(), Length(max=50)])
    consultation_fee = FloatField('Consultation Fee (INR)', validators=[DataRequired(), NumberRange(min=0)])
    available_hours = StringField('Available Hours', default="09:00 - 17:00", validators=[DataRequired()])
    submit = SubmitField('Add Doctor')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email address is already in use by another user.')

    def validate_license_number(self, license_number):
        doctor = Doctor.query.filter_by(license_number=license_number.data).first()
        if doctor:
            raise ValidationError('This license number is already registered.')


class PrescriptionForm(FlaskForm):
    symptoms = TextAreaField('Symptoms & Complaints', validators=[DataRequired()])
    diagnosis = TextAreaField('Diagnosis / Clinical Assessment', validators=[DataRequired()])
    treatment_plan = TextAreaField('Treatment Plan & Advice')
    medications = TextAreaField('Medications', validators=[DataRequired()], 
                                render_kw={"rows": 5, "placeholder": "Example:\nParacetamol - 500mg - 1-0-1 - 5 days\nAmoxicillin - 250mg - 1-1-1 - 7 days"})
    instructions = TextAreaField('Special Instructions / Notes')
    submit = SubmitField('Submit Diagnosis & Prescription')
