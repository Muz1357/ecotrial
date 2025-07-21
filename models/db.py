import mysql.connector
import os

def get_connection():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST'),
        port=int(os.environ.get('DB_PORT')),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASS'),
        database=os.environ.get('DB_NAME')
    )
