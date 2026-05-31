import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Ensure database tables are created
        db.create_all()
        
        # Add or update default admin
        from app.models import User
        from app import bcrypt
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            admin_user = User()
            admin_user.role = 'admin'
            admin_user.name = 'System Administrator'
            db.session.add(admin_user)
            
        admin_user.email = 'aman20061203@gmail.com'
        admin_user.password_hash = bcrypt.generate_password_hash('Aman@2006').decode('utf-8')
        db.session.commit()
        print("Default admin account set: aman20061203@gmail.com / Aman@2006")

        # Seed mock doctors if none exist in the system
        from app.models import Doctor
        doctor_exists = Doctor.query.first()
        if not doctor_exists:
            from app import bcrypt
            
            mock_doctors = [
                {
                    'name': 'Satish Kumar',
                    'email': 'satish@gmail.com',
                    'specialization': 'Cardiologist',
                    'license_number': 'MC-10492',
                    'fee': 800.0,
                    'hours': '09:00 - 17:00'
                },
                {
                    'name': 'Ananya Sen',
                    'email': 'ananya@gmail.com',
                    'specialization': 'Dermatologist',
                    'license_number': 'MC-29402',
                    'fee': 600.0,
                    'hours': '10:00 - 18:00'
                },
                {
                    'name': 'Vikram Rathore',
                    'email': 'vikram@gmail.com',
                    'specialization': 'Neurologist',
                    'license_number': 'MC-48592',
                    'fee': 1000.0,
                    'hours': '09:00 - 16:00'
                },
                {
                    'name': 'Shalini Verma',
                    'email': 'shalini@gmail.com',
                    'specialization': 'Pediatrician',
                    'license_number': 'MC-82910',
                    'fee': 500.0,
                    'hours': '08:00 - 15:00'
                },
                {
                    'name': 'Rajesh Patil',
                    'email': 'rajesh@gmail.com',
                    'specialization': 'Orthopedic',
                    'license_number': 'MC-73821',
                    'fee': 700.0,
                    'hours': '11:00 - 19:00'
                }
            ]
            
            for md in mock_doctors:
                # Create user
                doc_user = User()
                doc_user.email = md['email']
                doc_user.password_hash = bcrypt.generate_password_hash('Doctor@123').decode('utf-8')
                doc_user.name = md['name']
                doc_user.role = 'doctor'
                db.session.add(doc_user)
                db.session.flush()
                
                # Create doctor profile
                doc_profile = Doctor()
                doc_profile.user_id = doc_user.id
                doc_profile.specialization = md['specialization']
                doc_profile.license_number = md['license_number']
                doc_profile.consultation_fee = md['fee']
                doc_profile.available_hours = md['hours']
                db.session.add(doc_profile)
                
            db.session.commit()
            print("Successfully seeded default medical team in system database.")

        # Ensure all existing doctors use the normal emails and the password Doctor@123
        from app import bcrypt
        all_doctors = Doctor.query.all()
        for doc in all_doctors:
            first_name = doc.user.name.split()[0].lower()
            doc.user.email = f"{first_name}@gmail.com"
            doc.user.password_hash = bcrypt.generate_password_hash('Doctor@123').decode('utf-8')
        db.session.commit()
        print("Updated all active doctor credentials back to normal emails.")

    # Run Flask server
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
