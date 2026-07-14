import os
import base64
import hashlib

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./moodtunes.db")

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-jwt-key-change-in-production-moodtunes-2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080)) # 7 days

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/api/spotify/callback")

# Encryption Key for token storage
ENCRYPTION_KEY_RAW = os.getenv("ENCRYPTION_KEY", "")
if ENCRYPTION_KEY_RAW:
    ENCRYPTION_KEY = ENCRYPTION_KEY_RAW
else:
    # Derive a valid 32-byte Fernet key from the JWT_SECRET for local environments
    key_bytes = hashlib.sha256(JWT_SECRET.encode()).digest()
    ENCRYPTION_KEY = base64.urlsafe_b64encode(key_bytes).decode()
