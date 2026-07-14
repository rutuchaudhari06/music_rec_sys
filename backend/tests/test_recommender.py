import unittest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

# Import backend recommender modules
from app.ml.recommender import RecommenderEngine
from app.ml.emotion import EmotionClassifier, VALENCE_AROUSAL_LOOKUP, MOOD_MAPPING

class TestEmotionClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = EmotionClassifier()
        # Mock pipeline to avoid downloading the model during testing
        self.classifier.pipeline = MagicMock()

    def test_get_vibe_default_coordinates(self):
        vibe = "Romantic Yearning"
        valence, arousal = self.classifier.get_vibe_default_coordinates(vibe)
        # Average of love(0.9, 0.6), desire(0.8, 0.7), caring(0.8, 0.4)
        expected_v = (0.9 + 0.8 + 0.8) / 3.0
        expected_a = (0.6 + 0.7 + 0.4) / 3.0
        self.assertAlmostEqual(valence, expected_v)
        self.assertAlmostEqual(arousal, expected_a)

    def test_get_vibe_default_coordinates_invalid_vibe(self):
        v, a = self.classifier.get_vibe_default_coordinates("Unknown Vibe")
        self.assertEqual((v, a), VALENCE_AROUSAL_LOOKUP["neutral"])

    @patch('app.ml.emotion.EmotionClassifier.predict_emotions')
    def test_get_vibe_and_coordinates(self, mock_predict):
        # Setup mock emotions prediction
        mock_predict.return_value = [
            {"label": "joy", "score": 0.8},
            {"label": "sadness", "score": 0.2}
        ]
        
        vibe, val, aro = self.classifier.get_vibe_and_coordinates("Test text")
        
        # Dominant vibe should be Main Character Energy because joy is 0.8
        self.assertEqual(vibe, "Main Character Energy")
        
        # Weighted coordinates: joy (0.9, 0.8)*0.8 + sadness (0.15, 0.2)*0.2
        expected_val = (0.9 * 0.8 + 0.15 * 0.2) / 1.0
        expected_aro = (0.8 * 0.8 + 0.2 * 0.2) / 1.0
        self.assertAlmostEqual(val, expected_val)
        self.assertAlmostEqual(aro, expected_aro)

class TestRecommenderEngine(unittest.TestCase):
    def setUp(self):
        # Create a tiny mock tracks dataset
        self.mock_df = pd.DataFrame([
            {
                "track_id": "song1",
                "artists": "Artist A",
                "album_name": "Album A",
                "track_name": "Happy Song",
                "popularity": 80.0,
                "valence": 0.9,
                "energy": 0.8,
                "danceability": 0.8,
                "acousticness": 0.1,
                "instrumentalness": 0.0,
                "liveness": 0.2,
                "tempo": 120.0,
                "tempo_normalized": 0.6,
                "track_genre": "pop"
            },
            {
                "track_id": "song2",
                "artists": "Artist B",
                "album_name": "Album B",
                "track_name": "Sad Song",
                "popularity": 50.0,
                "valence": 0.1,
                "energy": 0.2,
                "danceability": 0.3,
                "acousticness": 0.8,
                "instrumentalness": 0.1,
                "liveness": 0.1,
                "tempo": 80.0,
                "tempo_normalized": 0.2,
                "track_genre": "acoustic"
            },
            {
                "track_id": "song3",
                "artists": "Artist C",
                "album_name": "Album C",
                "track_name": "Neutral Beat",
                "popularity": 60.0,
                "valence": 0.5,
                "energy": 0.5,
                "danceability": 0.5,
                "acousticness": 0.4,
                "instrumentalness": 0.2,
                "liveness": 0.15,
                "tempo": 100.0,
                "tempo_normalized": 0.4,
                "track_genre": "lo-fi"
            }
        ])
        
        # Instantiate recommender engine manually and inject mock variables
        self.recommender = RecommenderEngine()
        self.recommender.df = self.mock_df
        
        feature_cols = [
            "valence",
            "energy",
            "danceability",
            "acousticness",
            "instrumentalness",
            "liveness",
            "tempo_normalized"
        ]
        self.recommender.feature_matrix = self.mock_df[feature_cols].to_numpy(dtype=np.float32)
        self.recommender.track_id_to_idx = {"song1": 0, "song2": 1, "song3": 2}
        self.recommender.initialized = True

    def test_get_track_features(self):
        features = self.recommender.get_track_features("song1")
        self.assertIsNotNone(features)
        # Check valence and energy
        self.assertEqual(features[0], 0.9)
        self.assertEqual(features[1], 0.8)

    def test_get_track_features_missing(self):
        features = self.recommender.get_track_features("non_existent")
        self.assertIsNone(features)

    def test_initialize_rocchio_vector(self):
        # Initialize with song1 and song3
        rocchio = self.recommender.initialize_rocchio_vector(["song1", "song3"])
        
        # Expected is average of song1 features and song3 features, multiplied by 3 (capped at 1.0)
        song1_f = np.array([0.9, 0.8, 0.8, 0.1, 0.0, 0.2, 0.6])
        song3_f = np.array([0.5, 0.5, 0.5, 0.4, 0.2, 0.15, 0.4])
        expected = np.clip(((song1_f + song3_f) / 2.0) * 3.0, 0.0, 1.0)
        
        np.testing.assert_array_almost_equal(rocchio, expected)

    def test_update_rocchio_vector_like(self):
        current_rocchio = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        song_features = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
        
        # Like interaction updates by +1.0 * song_features
        updated = self.recommender.update_rocchio_vector(current_rocchio, song_features, "like")
        expected = np.clip(current_rocchio + 1.0 * song_features, 0.0, 1.0)
        np.testing.assert_array_almost_equal(updated, expected)

    def test_update_rocchio_vector_skip(self):
        current_rocchio = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        song_features = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        
        # Skip updates by -0.3 * song_features
        updated = self.recommender.update_rocchio_vector(current_rocchio, song_features, "skip")
        expected = np.clip(current_rocchio - 0.3 * song_features, 0.0, 1.0)
        np.testing.assert_array_almost_equal(updated, expected)

    def test_update_rocchio_vector_dislike(self):
        current_rocchio = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        song_features = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        
        # Dislike updates by -4.0 * song_features
        updated = self.recommender.update_rocchio_vector(current_rocchio, song_features, "dislike")
        expected = np.clip(current_rocchio - 4.0 * song_features, 0.0, 1.0)
        np.testing.assert_array_almost_equal(updated, expected)

    def test_recommend_ranking_happy(self):
        # Target mood is happy/high energy: valence=0.9, arousal=0.8
        rocchio = np.array([0.9, 0.8, 0.8, 0.1, 0.0, 0.2, 0.6]) # Matches song1 profile
        
        recs = self.recommender.recommend(
            target_valence=0.9,
            target_arousal=0.8,
            rocchio_vector=rocchio,
            disliked_track_ids=[],
            liked_track_ids=[]
        )
        
        # song1 should be the top recommendation
        self.assertEqual(recs[0]["track_id"], "song1")
        self.assertEqual(len(recs), 3)

    def test_recommend_exclusion(self):
        # Even if mood matches song1, if song1 is in disliked list, it should be excluded
        rocchio = np.array([0.9, 0.8, 0.8, 0.1, 0.0, 0.2, 0.6])
        recs = self.recommender.recommend(
            target_valence=0.9,
            target_arousal=0.8,
            rocchio_vector=rocchio,
            disliked_track_ids=["song1"],
            liked_track_ids=[]
        )
        
        # song1 must not be in recommendations
        rec_ids = [r["track_id"] for r in recs]
        self.assertNotIn("song1", rec_ids)
        self.assertEqual(len(recs), 2)

if __name__ == "__main__":
    unittest.main()
