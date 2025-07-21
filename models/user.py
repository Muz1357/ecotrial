from models.db import get_connection
from werkzeug.security import generate_password_hash

class User:
    def __init__(self, id=None, name=None, email=None, password=None, role=None,
                 created_at=None, is_approved=False, proof_path=None, business_name=None):
        self.id = id
        self.name = name
        self.email = email
        self.password = password  # plain password here; hashed on save
        self.role = role
        self.created_at = created_at
        self.is_approved = is_approved
        self.proof_path = proof_path  # path to uploaded proof document
        self.business_name = business_name

    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
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
        from models.db import get_connection
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_account WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()
        return user