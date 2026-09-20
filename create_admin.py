import getpass
import bcrypt
from db import get_connection


name = "System Administrator"
email = "admin@smartpreschool.com"

# Ask for password securely when running the script
password = getpass.getpass("Enter Admin password: ")


# Create secure bcrypt password hash
password_hash = bcrypt.hashpw(
    password.encode("utf-8"),
    bcrypt.gensalt()
).decode("utf-8")


conn = get_connection()

try:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users
                (name, email, password_hash, role, is_active)
            VALUES
                (%s, %s, %s, 'ADMIN', TRUE)
            """,
            (name, email, password_hash)
        )

    conn.commit()
    print("Admin account created successfully!")

finally:
    conn.close()