from models.db import get_connection 

class User:
    def __init__(self, id, name, email, password, role, created_at=None, business_name=None, profile_image =None):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.created_at = created_at
        self.business_name = business_name
        self.profile_image = profile_image

    @staticmethod
    def create(name, email, password, role, business_name=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_account (name, email, password, role, business_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, password, role, business_name))
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
                business_name=user_data.get('business_name'),
                profile_image=('profile_image')
            )
        return None
