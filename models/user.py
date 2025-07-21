from models.db import get_connection
from werkzeug.security import generate_password_hash

class User:
    def __init__(self, id=None, name=None, email=None, password=None, role=None,
                 created_at=None, is_approved=False, proof_path=None, business_name=None):
        self.id = id
        self.name = name
        self.email = email
        self.password = password  # hashed password stored
        self.role = role
        self.created_at = created_at
        self.is_approved = is_approved
        self.proof_path = proof_path
        self.business_name = business_name

    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
        # Hash password if not hashed yet (simple check: length or add flag in constructor)
        hashed_password = generate_password_hash(self.password)
        cursor.execute(
            """
            INSERT INTO user_account (name, email, password, role, is_approved, proof_path, business_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (self.name, self.email, hashed_password, self.role, self.is_approved, self.proof_path, self.business_name)
        )
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def find_by_email(email):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_account WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            return User(
                id=user_data['id'],
                name=user_data['name'],
                email=user_data['email'],
                password=user_data['password'],
                role=user_data['role'],
                created_at=user_data.get('created_at'),
                is_approved=user_data['is_approved'],
                proof_path=user_data.get('proof_path'),
                business_name=user_data.get('business_name'),
            )
        else:
            return None
