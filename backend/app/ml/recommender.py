import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import logging
from app.ml.dataset_utils import load_or_prepare_dataset, FEATURE_COLS

logger = logging.getLogger(__name__)

# Constants for scoring weights
W_EMOTION = 0.5
W_PREFERENCE = 0.4
W_POPULARITY = 0.1

class RecommenderEngine:
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.feature_matrix: Optional[np.ndarray] = None
        self.track_id_to_idx: Dict[str, int] = {}
        self.initialized = False

    def initialize(self):
        """Loads dataset and builds matrix for computation."""
        if not self.initialized:
            logger.info("Initializing Recommender Engine...")
            try:
                df, matrix, lookup = load_or_prepare_dataset()
                self.df = df
                self.feature_matrix = matrix
                self.track_id_to_idx = lookup
                self.initialized = True
                logger.info("Recommender Engine initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Recommender Engine: {e}")
                raise e

    def get_track_features(self, track_id: str) -> Optional[np.ndarray]:
        """Returns the normalized feature vector for a track."""
        self.initialize()
        idx = self.track_id_to_idx.get(track_id)
        if idx is not None:
            return self.feature_matrix[idx]
        return None

    def initialize_rocchio_vector(self, seed_track_ids: List[str]) -> np.ndarray:
        """
        Initializes the user's Rocchio preference vector.
        Calculates the average features of the seed tracks, multiplied by 3 (per user requirements).
        Returns a 7-dimensional NumPy array.
        """
        self.initialize()
        vectors = []
        for tid in seed_track_ids:
            vec = self.get_track_features(tid)
            if vec is not None:
                vectors.append(vec)
                
        if not vectors:
            # Fallback to a neutral preference profile (midpoint values)
            return np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)
            
        avg_vec = np.mean(vectors, axis=0)
        # Apply the initial +3 Love weight to the seeds
        rocchio = avg_vec * 3.0
        return np.clip(rocchio, 0.0, 1.0) # Clip features to valid normalized boundaries

    def update_rocchio_vector(self, current_vector: np.ndarray, song_features: np.ndarray, interaction: str) -> np.ndarray:
        """
        Updates the Rocchio vector based on interactions:
        - 'like': +1.0 * song_features
        - 'skip': -0.3 * song_features
        - 'dislike': -4.0 * song_features
        - 'remove': -4.0 * song_features
        """
        if interaction == "like":
            delta = 1.0
        elif interaction == "skip":
            delta = -0.3
        elif interaction in ("dislike", "remove"):
            delta = -4.0
        else:
            delta = 0.0
            
        updated = current_vector + delta * song_features
        # Keep features within normalized 0.0 to 1.0 bounds
        return np.clip(updated, 0.0, 1.0)

    def recommend(
        self,
        target_valence: float,
        target_arousal: float,
        rocchio_vector: np.ndarray,
        disliked_track_ids: List[str],
        liked_track_ids: List[str],
        top_n: int = 20
    ) -> List[Dict]:
        """
        Generates recommendations based on:
        1. Emotion Score: Euclidean distance between song (valence, energy) and target (valence, arousal).
        2. Preference Score: Cosine similarity between song features and the user's Rocchio vector.
        3. Popularity Score: Normalized track popularity.
        
        Formula: FinalScore = w1*EmotionScore + w2*PreferenceScore + w3*Popularity
        Disliked tracks are excluded.
        """
        self.initialize()
        
        # 1. Compute EmotionScore for all tracks
        # valence is index 0, energy is index 1 of the feature matrix
        track_valence = self.feature_matrix[:, 0]
        track_energy = self.feature_matrix[:, 1]
        
        # Euclidean distance in [0, 1] space
        distance = np.sqrt((track_valence - target_valence)**2 + (track_energy - target_arousal)**2)
        # Max distance in 2D space is sqrt(2)
        max_dist = np.sqrt(2.0)
        emotion_scores = 1.0 - (distance / max_dist)
        
        # 2. Compute PreferenceScore (Cosine Similarity)
        dot_products = np.dot(self.feature_matrix, rocchio_vector)
        matrix_norms = np.linalg.norm(self.feature_matrix, axis=1)
        rocchio_norm = np.linalg.norm(rocchio_vector)
        
        # Avoid division by zero
        preference_scores = dot_products / (matrix_norms * rocchio_norm + 1e-9)
        # Rescale cosine similarity from [-1, 1] to [0, 1]
        preference_scores = (preference_scores + 1.0) / 2.0
        
        # 3. Popularity Score (normalized from [0, 100] to [0.0, 1.0])
        popularity_scores = self.df["popularity"].to_numpy(dtype=np.float32) / 100.0
        
        # 4. Final blended score
        final_scores = (W_EMOTION * emotion_scores) + (W_PREFERENCE * preference_scores) + (W_POPULARITY * popularity_scores)
        
        # 5. Filter out disliked songs
        # Build filter mask
        exclude_indices = set()
        for tid in disliked_track_ids:
            idx = self.track_id_to_idx.get(tid)
            if idx is not None:
                exclude_indices.add(idx)
                
        # Also let's avoid recommending songs they already liked in this specific list if desired,
        # but since they might want to hear liked songs, let's keep them unless explicitly excluded.
        # Let's filter out
        mask = np.ones(len(self.df), dtype=bool)
        if exclude_indices:
            mask[list(exclude_indices)] = False
            
        # Get sorted indices of top tracks matching criteria
        indices = np.where(mask)[0]
        scored_indices = sorted(indices, key=lambda idx: final_scores[idx], reverse=True)
        
        # Build recommendation results
        recommendations = []
        for idx in scored_indices[:top_n]:
            row = self.df.iloc[idx]
            recommendations.append({
                "track_id": row["track_id"],
                "artists": row["artists"],
                "album_name": row["album_name"],
                "track_name": row["track_name"],
                "popularity": float(row["popularity"]),
                "valence": float(row["valence"]),
                "energy": float(row["energy"]),
                "danceability": float(row["danceability"]),
                "acousticness": float(row["acousticness"]),
                "instrumentalness": float(row["instrumentalness"]),
                "liveness": float(row["liveness"]),
                "tempo": float(row["tempo"]),
                "track_genre": row["track_genre"],
                "emotion_score": float(emotion_scores[idx]),
                "preference_score": float(preference_scores[idx]),
                "final_score": float(final_scores[idx])
            })
            
        return recommendations

# Singleton instance
recommender = RecommenderEngine()
