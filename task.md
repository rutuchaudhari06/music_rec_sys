# MoodTunes Task List

## Sprint 1: ML Model, Dataset & Recommendation Core (Backend Core)
- [/] Initialize Python virtual environment & install requirements in `backend/`
- [ ] Prepare static Spotify dataset: write conversion script to create `dataset.parquet` and load it into memory
- [ ] Implement GoEmotions ML inference module (`emotion.py`) with emotion-to-vibe mapping
- [ ] Implement vectorized recommendation engine (`recommender.py`) using NumPy for Valence-Arousal & Rocchio profile calculations
- [ ] Verify Sprint 1 recommendation logic with automated tests

## Sprint 2: Database, User Auth & Spotify API (Backend Integration)
- [ ] Configure PostgreSQL database & set up SQLAlchemy schemas (Users, Preferences, Interactions, SpotifyCredentials)
- [ ] Implement JWT-based signup and login endpoints
- [ ] Build endpoints for recording likes, dislikes, and skips, updating the Postgres Rocchio vector
- [ ] Set up Spotify OAuth Flow, credential encryption/decryption, and token refresh logic
- [ ] Create playlist export to Spotify API endpoint
- [ ] Verify Sprint 2 backend integrations with Postman/cURL

## Sprint 3: Skeuomorphic iPod Frontend & End-to-End Integration (Frontend & Polish)
- [ ] Initialize React + Vite frontend and design the skeuomorphic iPod shell and screens with vanilla CSS
- [ ] Write click-wheel gesture tracking in JS for menu navigation
- [ ] Implement screens: Auth, Onboarding (seed selection), Mood text prompt, Player/Recommendation deck, and Spotify export options
- [ ] Integrate React frontend with FastAPI backend API endpoints
- [ ] Conduct end-to-end user flow testing and UI refinement
