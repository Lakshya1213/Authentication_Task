import sys
import os
import asyncio
import httpx

# Add parent directory of scratch/ to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from models.auth_model import User, ConnectedAccount, OAuthToken
from utils.encryption import decrypt_token

async def diagnose():
    db = SessionLocal()
    try:
        # Get the first user
        user = db.query(User).first()
        if not user:
            print("ERROR: No users found in the database.")
            return
            
        print(f"Diagnosing user: id={user.id}, email={user.email}")
        
        # Get Google connected account
        account = db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == "google"
        ).first()
        
        if not account:
            print("ERROR: No Google connected account found for this user.")
            return
            
        print(f"Connected account status: {account.status}, scopes: {account.scopes}")
        
        # Get token
        token = db.query(OAuthToken).filter(
            OAuthToken.connected_account_id == account.id
        ).first()
        
        if not token:
            print("ERROR: No OAuth token found for this connection.")
            return
            
        try:
            decrypted_access = decrypt_token(token.encrypted_access_token)
            print("Access token decrypted successfully.")
        except Exception as e:
            print(f"ERROR: Failed to decrypt access token: {e}")
            return
            
        # Call Google Calendar API
        print("Calling Google Calendar API...")
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {decrypted_access}"}
            # Fetch events from primary calendar
            url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            response = await client.get(url, headers=headers)
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(diagnose())
