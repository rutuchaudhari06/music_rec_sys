import os
import sys
import datetime
import logging
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from jose import jwt
import numpy as np
from sqlalchemy.orm import Session

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import config, database, models
from app.config import JWT_SECRET, JWT_ALGORITHM
from app.database import get_db, engine, Base
from app.models import User, SpotifyCredentials, UserPreference, UserInteraction

# Import auth utilities
from app.auth_utils import get_password_hash, verify_password, create_access_token, get_current_user

# Import ML components
from app.ml.emotion import classifier
from app.ml.recommender import recommender

# Import Spotify integrations
from app.services import spotify as spotify_service

app = FastAPI(
    title="MoodTunes API",
    description="Backend API for MoodTunes music recommendation platform",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas for request/response bodies
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    email: str

class SeedRequest(BaseModel):
    seed_track_ids: List[str]

class EmotionRequest(BaseModel):
    text: str

class EmotionResponse(BaseModel):
    text: str
    dominant_vibe: str
    target_valence: float
    target_arousal: float

class RecommendationRequest(BaseModel):
    text: str
    vibe_override: Optional[str] = None
    limit: Optional[int] = 20

class RecommendationTestRequest(BaseModel):
    target_valence: float
    target_arousal: float
    rocchio_vector: List[float] # Length 7 list
    disliked_track_ids: Optional[List[str]] = []
    liked_track_ids: Optional[List[str]] = []
    top_n: Optional[int] = 10

class InteractionRequest(BaseModel):
    track_id: str
    interaction_type: str # 'like', 'dislike', 'skip', 'remove'

class ExportRequest(BaseModel):
    playlist_name: str
    track_ids: List[str]

@app.on_event("startup")
async def startup_event():
    """Initialize DB tables, load dataset and initialize components at startup."""
    logger.info("Initializing database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        
    logger.info("Starting MoodTunes API ML loading...")
    parquet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dataset.parquet")
    if not os.path.exists(parquet_path):
        logger.warning(
            f"Dataset parquet file not found at {parquet_path}.\n"
            "Please run: python app/ml/download_and_convert.py to prepare it."
        )
    else:
        try:
            recommender.initialize()
            logger.info("Recommender engine pre-loaded successfully.")
        except Exception as e:
            logger.error(f"Error pre-loading recommender engine: {e}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the MoodTunes API!", "status": "online"}

# ----------------- AUTHENTICATION ENDPOINTS -----------------

@app.post("/api/auth/signup")
def signup(request: UserCreate, db: Session = Depends(get_db)):
    """User signup endpoint."""
    db_user = db.query(User).filter(User.email == request.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(request.password)
    user = User(email=request.email, hashed_password=hashed_password)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return {"status": "success", "message": "User registered successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to complete user signup: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed.")

@app.post("/api/auth/login", response_model=Token)
def login(request: UserLogin, db: Session = Depends(get_db)):
    """User login endpoint returning JWT token."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
        
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": user.email
    }

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns current user information to check token validity."""
    return {
        "id": current_user.id,
        "email": current_user.email
    }

# ----------------- ML & RECOMMENDATION ENDPOINTS -----------------

@app.post("/api/emotion/predict", response_model=EmotionResponse)
def predict_emotion(request: EmotionRequest):
    """
    Analyzes the user's emotion text input and returns:
    1. Dominant vibe
    2. Computed Valence-Arousal coordinates
    """
    try:
        dominant_vibe, target_valence, target_arousal = classifier.get_vibe_and_coordinates(request.text)
        return EmotionResponse(
            text=request.text,
            dominant_vibe=dominant_vibe,
            target_valence=target_valence,
            target_arousal=target_arousal
        )
    except Exception as e:
        logger.error(f"Emotion prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Emotion prediction failed: {str(e)}")

@app.get("/api/songs/search")
def search_songs(
    query: str = Query(..., min_length=2, description="Search term for track name or artist"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Searches the local dataset for songs matching query in artist name or track title.
    Useful for onboarding seed selection.
    """
    if not recommender.initialized:
        try:
            recommender.initialize()
        except Exception:
            raise HTTPException(
                status_code=503, 
                detail="Dataset not initialized. Please run python app/ml/download_and_convert.py first."
            )
            
    query_lower = query.lower()
    df = recommender.df
    
    match_mask = df["track_name"].str.lower().str.contains(query_lower, na=False) | \
                 df["artists"].str.lower().str.contains(query_lower, na=False)
                 
    results_df = df[match_mask].head(limit)
    
    results = []
    for _, row in results_df.iterrows():
        results.append({
            "track_id": row["track_id"],
            "artists": row["artists"],
            "album_name": row["album_name"],
            "track_name": row["track_name"],
            "popularity": int(row["popularity"]),
            "track_genre": row["track_genre"]
        })
        
    return results

@app.post("/api/recommendations/seed")
def set_seeds(request: SeedRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Initializes the user's preference vector based on selected seed tracks."""
    if len(request.seed_track_ids) < 3:
        raise HTTPException(status_code=400, detail="Please select at least 3 seed tracks for onboarding.")
        
    try:
        initial_vector = recommender.initialize_rocchio_vector(request.seed_track_ids)
        pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
        if pref:
            pref.rocchio_vector = initial_vector.tolist()
        else:
            pref = UserPreference(user_id=current_user.id, rocchio_vector=initial_vector.tolist())
            db.add(pref)
        db.commit()
        return {"status": "success", "message": "Onboarding seed profile created successfully."}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save onboarding seeds: {e}")
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")

@app.post("/api/recommendations")
def get_recommendations(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates personalized recommendations based on text input (valence-arousal),
    user preference vectors (Rocchio), and interaction filters (exclusion).
    """
    # 1. Determine valence and arousal
    if request.vibe_override:
        dominant_vibe = request.vibe_override
        target_v, target_a = classifier.get_vibe_default_coordinates(request.vibe_override)
    else:
        dominant_vibe, target_v, target_a = classifier.get_vibe_and_coordinates(request.text)
        
    # 2. Get user preferences
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        # User has not done onboarding seed selection, default to neutral preference profile
        rocchio = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    else:
        rocchio = np.array(pref.rocchio_vector, dtype=np.float32)
        
    # 3. Load interactions to filter out disliked tracks
    interactions = db.query(UserInteraction).filter(UserInteraction.user_id == current_user.id).all()
    disliked_ids = [i.track_id for i in interactions if i.interaction_type in ("dislike", "remove")]
    liked_ids = [i.track_id for i in interactions if i.interaction_type == "like"]
    
    try:
        recs = recommender.recommend(
            target_valence=target_v,
            target_arousal=target_a,
            rocchio_vector=rocchio,
            disliked_track_ids=disliked_ids,
            liked_track_ids=liked_ids,
            top_n=request.limit
        )
        return {
            "dominant_vibe": dominant_vibe,
            "target_valence": target_v,
            "target_arousal": target_a,
            "recommendations": recs
        }
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compute recommendations: {str(e)}")

@app.post("/api/interactions")
def log_interaction(
    request: InteractionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logs track interactions (like, dislike, skip) and updates the user's
    Rocchio preference profile vector.
    """
    if request.interaction_type not in ("like", "dislike", "skip", "remove"):
        raise HTTPException(status_code=400, detail="Invalid interaction type. Choose from: like, dislike, skip, remove")
        
    song_features = recommender.get_track_features(request.track_id)
    if song_features is None:
        raise HTTPException(status_code=404, detail="Track not found in local database features.")
        
    try:
        # 1. Log interaction
        interaction = UserInteraction(
            user_id=current_user.id,
            track_id=request.track_id,
            interaction_type=request.interaction_type
        )
        db.add(interaction)
        
        # 2. Update preference vector
        pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
        if not pref:
            current_vector = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        else:
            current_vector = np.array(pref.rocchio_vector, dtype=np.float32)
            
        updated_vector = recommender.update_rocchio_vector(current_vector, song_features, request.interaction_type)
        
        if not pref:
            pref = UserPreference(user_id=current_user.id, rocchio_vector=updated_vector.tolist())
            db.add(pref)
        else:
            pref.rocchio_vector = updated_vector.tolist()
            
        db.commit()
        return {
            "status": "success",
            "interaction_type": request.interaction_type,
            "updated_vector": updated_vector.tolist()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save user interaction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save interaction: {str(e)}")

@app.post("/api/recommendations/test")
def test_recommendations(request: RecommendationTestRequest):
    """
    Calculates recommendations using direct inputs. 
    Mainly for testing recommender core.
    """
    if not recommender.initialized:
        try:
            recommender.initialize()
        except Exception:
            raise HTTPException(
                status_code=503, 
                detail="Dataset not initialized. Please run python app/ml/download_and_convert.py first."
            )
            
    if len(request.rocchio_vector) != 7:
        raise HTTPException(status_code=400, detail="Rocchio vector must contain exactly 7 feature values.")
        
    rocchio_arr = np.array(request.rocchio_vector, dtype=np.float32)
    
    try:
        recs = recommender.recommend(
            target_valence=request.target_valence,
            target_arousal=request.target_arousal,
            rocchio_vector=rocchio_arr,
            disliked_track_ids=request.disliked_track_ids,
            liked_track_ids=request.liked_track_ids,
            top_n=request.top_n
        )
        return recs
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")

# ----------------- SPOTIFY INTEGRATION ENDPOINTS -----------------

@app.get("/api/spotify/connect")
def connect_spotify(token: str = Query(..., description="JWT token of the authenticated user")):
    """
    Redirects the user's browser to Spotify authorization screen.
    Uses the user's token as state to match them during callback.
    """
    try:
        # Validate JWT token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise Exception("Invalid token structure")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token.")
        
    auth_url = spotify_service.get_spotify_auth_url()
    # Pass user JWT as the OAuth state parameter
    auth_url += f"&state={token}"
    return RedirectResponse(auth_url)

@app.get("/api/spotify/callback", response_class=HTMLResponse)
def spotify_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    """Receives callback from Spotify, exchanges credentials and stores them securely."""
    try:
        # 1. Verify user using the token passed in state
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise Exception("State did not contain user context.")
            
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise Exception("User not found.")
            
        # 2. Exchange code for credentials
        tokens = spotify_service.exchange_code_for_tokens(code)
        
        # 3. Encrypt and store credentials
        encrypted_access = spotify_service.encrypt_token(tokens["access_token"])
        encrypted_refresh = spotify_service.encrypt_token(tokens["refresh_token"])
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=tokens["expires_in"])
        
        creds = db.query(SpotifyCredentials).filter(SpotifyCredentials.user_id == user.id).first()
        if creds:
            creds.encrypted_access_token = encrypted_access
            if tokens.get("refresh_token"):
                creds.encrypted_refresh_token = encrypted_refresh
            creds.expires_at = expires_at
        else:
            creds = SpotifyCredentials(
                user_id=user.id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                expires_at=expires_at
            )
            db.add(creds)
            
        db.commit()
        
        # 4. Elegant retro styled browser close notification
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Connection Successful</title>
            <style>
                body {
                    background-color: #fafafa;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .card {
                    background: #ffffff;
                    border: 1px solid #e1e4e8;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                    border-radius: 8px;
                    padding: 40px;
                    text-align: center;
                    max-width: 400px;
                }
                h1 {
                    color: #1DB954;
                    font-size: 24px;
                    margin-top: 0;
                    font-weight: 700;
                }
                p {
                    color: #586069;
                    font-size: 15px;
                    line-height: 1.5;
                }
                .btn {
                    margin-top: 24px;
                    display: inline-block;
                    padding: 10px 24px;
                    background-color: #1DB954;
                    color: white;
                    text-decoration: none;
                    border-radius: 500px;
                    font-weight: 600;
                    font-size: 14px;
                    border: none;
                    cursor: pointer;
                    transition: background-color 0.2s;
                }
                .btn:hover {
                    background-color: #1ed760;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Spotify Connected!</h1>
                <p>Your account is successfully linked. You can now export playlist recommendations directly to your Spotify profile.</p>
                <button class="btn" onclick="window.close()">Close Window</button>
            </div>
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Spotify connection callback failed: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Connection Failed</title></head>
        <body style="font-family: system-ui, sans-serif; padding: 40px; background-color: #fff5f5; color: #9c0000; text-align: center;">
            <h1 style="font-size: 24px;">Spotify Connection Failed</h1>
            <p style="margin-top: 10px; font-size: 15px;">Error: {str(e)}</p>
            <p style="color: #666; font-size: 13px;">Please close this window and try connecting again.</p>
        </body>
        </html>
        """

@app.get("/api/spotify/status")
def get_spotify_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns whether the user has successfully linked their Spotify credentials."""
    creds = db.query(SpotifyCredentials).filter(SpotifyCredentials.user_id == current_user.id).first()
    return {"connected": creds is not None}

@app.post("/api/spotify/export")
def export_playlist(
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a custom playlist and adds tracks to the user's Spotify account."""
    if not request.playlist_name.strip():
        raise HTTPException(status_code=400, detail="Playlist name cannot be empty.")
        
    try:
        result = spotify_service.create_playlist_and_add_tracks(
            user_id=current_user.id,
            db=db,
            playlist_name=request.playlist_name,
            track_ids=request.track_ids
        )
        return result
    except Exception as e:
        logger.error(f"Failed to export playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))
