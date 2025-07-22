from models.db import get_connection 

class User:
    def __init__(self, id, name, email, password, role, is_approved, created_at=None, proof_path=None, business_name=None):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.created_at = created_at
        self.is_approved = is_approved
        self.proof_path = proof_path
        self.business_name = business_name

    @staticmethod
    def create(name, email, password, role, is_approved=0, business_name=None, proof_path=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_account (name, email, password, role, is_approved, business_name, proof_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, email, password, role, is_approved, business_name, proof_path))
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
                is_approved=user_data['is_approved'],
                created_at=user_data.get('created_at'),
                proof_path=user_data.get('proof_path'),
                business_name=user_data.get('business_name')
            )
        return None
