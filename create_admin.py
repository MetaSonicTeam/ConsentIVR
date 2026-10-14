"""
Create or reset a dashboard admin user.

    python create_admin.py <username> <password>
"""

import sys

from db import execute, init_db, query
from security import hash_password


def main():
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <username> <password>")
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    init_db()
    existing = query("SELECT id FROM users WHERE username = ?", (username,), one=True)
    pw = hash_password(password)
    if existing:
        execute("UPDATE users SET password_hash = ?, role = 'admin', active = 1 WHERE username = ?",
                (pw, username))
        print(f"Updated admin '{username}'.")
    else:
        execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,'admin')",
                (username, pw))
        print(f"Created admin '{username}'.")


if __name__ == "__main__":
    main()
