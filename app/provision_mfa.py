"""Generate a TOTP secret for Sprite Builder MFA.

Usage:
    python -m app.provision_mfa

Copy the printed AUTH_TOTP_SECRET line into your .env file, then scan the
otpauth:// URI with Google Authenticator, Authy, 1Password, etc.
"""
import os

import pyotp
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    secret = pyotp.random_base32()
    username = os.environ.get("AUTH_USERNAME", "admin")
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="Sprite Builder",
    )

    print("Generated a new TOTP secret.\n")
    print("1. Add this line to your .env file:\n")
    print(f"   AUTH_TOTP_SECRET={secret}\n")
    print("2. Scan this URI with an authenticator app")
    print("   (paste into https://qr.io, or run `qrencode -t ANSI '<uri>'`):\n")
    print(f"   {uri}\n")
    print("3. Restart the server. Login will then require a 6-digit code.")


if __name__ == "__main__":
    main()
