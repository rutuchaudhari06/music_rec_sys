import base64
import requests
import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, ENCRYPTION_KEY
from app.models import SpotifyCredentials

# Initialize Fernet encryptor
fernet = Fernet(ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    if not token:
        return ""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    return fernet.decrypt(encrypted_token.encode()).decode()

def get_spotify_auth_url() -> str:
    """Returns the authorization URL to redirect users to Spotify for consent."""
    scope = "playlist-modify-public playlist-modify-private user-read-private user-read-email"
    auth_url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={SPOTIFY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={scope}"
        f"&show_dialog=true"
    )
    return auth_url

def exchange_code_for_tokens(code: str) -> Dict:
    """Exchanges an OAuth code from redirect callback for Spotify credentials."""
    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI
    }
    
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    if response.status_code != 200:
        raise Exception(f"Spotify token exchange failed: {response.text}")
        
    res_data = response.json()
    return {
        "access_token": res_data["access_token"],
        "refresh_token": res_data.get("refresh_token"),
        "expires_in": res_data["expires_in"]
    }

def get_valid_access_token(user_id: int, db: Session) -> str:
    """Gets a decrypted valid access token for the user, refreshing it if expired."""
    creds = db.query(SpotifyCredentials).filter(SpotifyCredentials.user_id == user_id).first()
    if not creds:
        raise Exception("Spotify account not linked. Please connect your Spotify account first.")
        
    now = datetime.datetime.utcnow()
    # If expired or expiring in the next 60 seconds, refresh it
    if creds.expires_at <= now + datetime.timedelta(seconds=60):
        decrypted_refresh_token = decrypt_token(creds.encrypted_refresh_token)
        if not decrypted_refresh_token:
            raise Exception("No refresh token available to refresh access token.")
            
        auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": decrypted_refresh_token
        }
        
        response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
        if response.status_code != 200:
            raise Exception(f"Failed to refresh Spotify token: {response.text}")
            
        res_data = response.json()
        
        # Update credentials in database
        creds.encrypted_access_token = encrypt_token(res_data["access_token"])
        if "refresh_token" in res_data:
            creds.encrypted_refresh_token = encrypt_token(res_data["refresh_token"])
        creds.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=res_data["expires_in"])
        db.commit()
        
    return decrypt_token(creds.encrypted_access_token)

def get_spotify_user_profile(access_token: str) -> Dict:
    """Fetches the user's Spotify profile details."""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch Spotify user profile: {response.text}")
    return response.json()

def create_playlist_and_add_tracks(user_id: int, db: Session, playlist_name: str, track_ids: List[str]) -> Dict:
    """Creates a Spotify playlist and adds the recommended tracks to it."""
    access_token = get_valid_access_token(user_id, db)
    
    # 1. Get Spotify user ID
    user_profile = get_spotify_user_profile(access_token)
    spotify_user_id = user_profile["id"]
    
    # 2. Create the playlist
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    playlist_data = {
        "name": playlist_name,
        "description": "Created with MoodTunes - your vintage iPod emotion recommender.",
        "public": True
    }
    
    create_url = f"https://api.spotify.com/v1/users/{spotify_user_id}/playlists"
    response = requests.post(create_url, headers=headers, json=playlist_data)
    if response.status_code not in (200, 201):
        raise Exception(f"Failed to create Spotify playlist: {response.text}")
        
    playlist = response.json()
    playlist_id = playlist["id"]
    playlist_url = playlist["external_urls"]["spotify"]
    
    # 3. Add tracks to the playlist
    if track_ids:
        track_uris = []
        for tid in track_ids:
            # Handle both raw IDs and full URIs
            if tid.startswith("spotify:track:"):
                track_uris.append(tid)
            else:
                track_uris.append(f"spotify:track:{tid}")
                
        add_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        # Batch adding tracks (Spotify API allows max 100 tracks per call)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            add_res = requests.post(add_url, headers=headers, json={"uris": batch})
            if add_res.status_code not in (200, 201):
                raise Exception(f"Failed to add tracks to playlist: {add_res.text}")
                
    return {
        "playlist_id": playlist_id,
        "name": playlist_name,
        "external_url": playlist_url
    }
