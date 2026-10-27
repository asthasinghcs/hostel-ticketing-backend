"""Trusted server-side staff provisioning. Passwords are read without echo."""
import argparse
import getpass
from werkzeug.security import generate_password_hash
from app import app, BLOCKS, get_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-staff"])
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=["admin", "warden"])
    parser.add_argument("--block", choices=BLOCKS)
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not args.name.strip() or len(args.name.strip()) > 100 or len(email) > 254 or email.count("@") != 1 or not all(email.split("@")) or any(c.isspace() for c in email):
        parser.error("Enter a name (up to 100 characters) and a valid email")
    password = getpass.getpass("Password (8-128 characters): ")
    if not 8 <= len(password) <= 128 or password != getpass.getpass("Confirm password: "):
        parser.error("Passwords must match and contain 8-128 characters")
    with app.app_context():
        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
            parser.error("Email already registered; existing accounts are never overwritten")
        db.execute("INSERT INTO users (name,email,password,role,hostel_block) VALUES (?,?,?,?,?)",
                   (args.name.strip(), email, generate_password_hash(password), args.role,
                    args.block if args.role == "warden" else None))
        db.commit()
    print("Staff account created.")


if __name__ == "__main__":
    main()
