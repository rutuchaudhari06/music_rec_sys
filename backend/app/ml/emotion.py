from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Hugging Face model identifier
MODEL_NAME = "SamLowe/roberta-base-go_emotions"

# Emotion categories mapping to Valence-Arousal coordinates [valence, arousal]
# Valence: 0.0 (negative) to 1.0 (positive)
# Arousal: 0.0 (low energy) to 1.0 (high energy)
VALENCE_AROUSAL_LOOKUP: Dict[str, Tuple[float, float]] = {
    # Main Character Energy
    "joy": (0.9, 0.8),
    "excitement": (0.9, 0.9),
    "pride": (0.8, 0.6),
    "approval": (0.7, 0.4),
    "amusement": (0.85, 0.7),
    
    # Heartbreak & Healing
    "sadness": (0.15, 0.2),
    "grief": (0.1, 0.15),
    "remorse": (0.2, 0.3),
    "disappointment": (0.25, 0.3),
    "embarrassment": (0.35, 0.5),
    "loneliness": (0.15, 0.2), # Fallback, not natively predicted by GoEmotions
    
    # Late Night Feels
    "fear": (0.15, 0.8),
    "nervousness": (0.3, 0.75),
    "confusion": (0.4, 0.5),
    
    # Romantic Yearning
    "love": (0.9, 0.6),
    "desire": (0.8, 0.7),
    "caring": (0.8, 0.4),
    
    # Chaotic Energy
    "anger": (0.1, 0.85),
    "annoyance": (0.2, 0.65),
    "disgust": (0.15, 0.6),
    "disapproval": (0.25, 0.55),
    
    # Escapism & Discovery
    "curiosity": (0.65, 0.6),
    "realization": (0.6, 0.5),
    "surprise": (0.7, 0.8),
    
    # Peaceful & Hopeful
    "gratitude": (0.8, 0.3),
    "relief": (0.7, 0.2),
    "optimism": (0.8, 0.5),
    "admiration": (0.8, 0.5),
    "neutral": (0.5, 0.4)
}

# Mapping of the 28 emotions to 7 user-facing vibes
MOOD_MAPPING: Dict[str, List[str]] = {
    "Heartbreak & Healing": [
        "sadness",
        "grief",
        "remorse",
        "disappointment",
        "embarrassment",
        "loneliness"
    ],
    "Late Night Feels": [
        "loneliness",
        "fear",
        "nervousness",
        "confusion"
    ],
    "Romantic Yearning": [
        "love",
        "desire",
        "caring"
    ],
    "Main Character Energy": [
        "joy",
        "pride",
        "excitement",
        "approval",
        "amusement"
    ],
    "Chaotic Energy": [
        "anger",
        "annoyance",
        "disgust",
        "disapproval"
    ],
    "Escapism & Discovery": [
        "curiosity",
        "realization",
        "surprise"
    ],
    "Peaceful & Hopeful": [
        "gratitude",
        "relief",
        "optimism",
        "admiration",
        "neutral"
    ]
}

# Emotion Classifier Class
class EmotionClassifier:
    def __init__(self):
        self.pipeline = None

    def initialize(self):
        """Lazy load the pipeline to avoid importing and downloading at startup if not used immediately."""
        if self.pipeline is None:
            logger.info("Initializing Hugging Face Emotion Pipeline...")
            from transformers import pipeline
            # Load the classification pipeline (CPU mode by default)
            self.pipeline = pipeline(
                "text-classification",
                model=MODEL_NAME,
                return_all_scores=True
            )
            logger.info("Emotion Pipeline initialized successfully.")

    def predict_emotions(self, text: str) -> List[Dict[str, float]]:
        """Predicts confidence score for all 28 emotions."""
        self.initialize()
        if not text.strip():
            # If text is empty or blank, return neutral as 1.0 and others as 0.0
            return [{"label": k, "score": 1.0 if k == "neutral" else 0.0} for k in VALENCE_AROUSAL_LOOKUP.keys()]
        
        # Run prediction
        predictions = self.pipeline(text)
        # The output format is [[{"label": "anger", "score": 0.01}, ...]]

        return predictions
        # return predictions[0]

    def get_vibe_and_coordinates(self, text: str) -> Tuple[str, float, float]:
        """
        Analyzes the text, determines the dominant aggregate vibe,
        and computes the target valence-arousal coordinates as a weighted average.
        """
        predictions = self.predict_emotions(text)
        
        # Calculate weighted Valence-Arousal coordinates
        total_score = 0.0
        weighted_valence = 0.0
        weighted_arousal = 0.0
        
        # For mapping to the 7 user-facing vibes, aggregate the scores
        vibe_scores = {vibe: 0.0 for vibe in MOOD_MAPPING.keys()}
        
        for pred in predictions:
            label = pred["label"]
            score = pred["score"]
            
            # Map score to the 7 vibes
            for vibe, emotions in MOOD_MAPPING.items():
                if label in emotions:
                    vibe_scores[vibe] += score
            
            # Map score to coordinates if label exists in coordinates lookup
            if label in VALENCE_AROUSAL_LOOKUP:
                v, a = VALENCE_AROUSAL_LOOKUP[label]
                weighted_valence += v * score
                weighted_arousal += a * score
                total_score += score
                
        # Handle division by zero
        if total_score > 0:
            target_valence = weighted_valence / total_score
            target_arousal = weighted_arousal / total_score
        else:
            target_valence, target_arousal = VALENCE_AROUSAL_LOOKUP["neutral"]
            
        # Get the dominant vibe (highest score)
        dominant_vibe = max(vibe_scores, key=vibe_scores.get)
        
        # If the highest score is very low, or it is neutral-like, default to Peaceful & Hopeful (Neutral)
        # However, GoEmotions neutral score will naturally map it.
        
        return dominant_vibe, target_valence, target_arousal

    def get_vibe_default_coordinates(self, vibe: str) -> Tuple[float, float]:
        """
        Returns average valence-arousal coordinates of all emotions in a vibe.
        Used for manual vibe overrides.
        """
        if vibe not in MOOD_MAPPING:
            return VALENCE_AROUSAL_LOOKUP["neutral"]
            
        emotions = MOOD_MAPPING[vibe]
        total_v = 0.0
        total_a = 0.0
        count = 0
        for emo in emotions:
            if emo in VALENCE_AROUSAL_LOOKUP:
                v, a = VALENCE_AROUSAL_LOOKUP[emo]
                total_v += v
                total_a += a
                count += 1
                
        if count > 0:
            return total_v / count, total_a / count
        return VALENCE_AROUSAL_LOOKUP["neutral"]

# Singleton instance
classifier = EmotionClassifier()
