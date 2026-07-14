import os
import urllib.request
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "dataset.csv")
PARQUET_PATH = os.path.join(DATA_DIR, "dataset.parquet")

# Hugging Face Direct Download Link (LFS redirect handler)
DATASET_URL = "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv"

# Features used for Rocchio/Similarity mapping
FEATURE_COLS = [
    "valence",
    "energy",
    "danceability",
    "acousticness",
    "instrumentalness",
    "liveness",
    "tempo_normalized"
]

def download_dataset():
    """Downloads the Spotify Tracks CSV from Hugging Face to data/dataset.csv."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(CSV_PATH):
        logger.info("dataset.csv already exists. Skipping download.")
        return

    logger.info(f"Downloading dataset from {DATASET_URL}...")
    
    # Custom opener to handle redirects and user agent requirements if any
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    urllib.request.install_opener(opener)
    
    try:
        urllib.request.urlretrieve(DATASET_URL, CSV_PATH)
        logger.info("Download completed successfully.")
    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        raise e

def prepare_parquet():
    """Cleans the CSV dataset and saves it as dataset.parquet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(PARQUET_PATH):
        logger.info("dataset.parquet already exists. Skipping conversion.")
        return

    if not os.path.exists(CSV_PATH):
        download_dataset()

    logger.info("Cleaning CSV dataset and converting to Parquet...")
    # Load dataset
    df = pd.read_csv(CSV_PATH)
    
    # Drop index column if present (e.g. Unnamed: 0)
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
        
    # Drop duplicates on track_id
    df = df.drop_duplicates(subset=["track_id"])
    
    # Handle missing metadata
    df["artists"] = df["artists"].fillna("Unknown Artist")
    df["album_name"] = df["album_name"].fillna("Unknown Album")
    df["track_name"] = df["track_name"].fillna("Unknown Title")
    
    # Fill missing audio features with 0.0
    for col in ["valence", "energy", "danceability", "acousticness", "instrumentalness", "liveness", "tempo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    # Normalize tempo to [0, 1]
    min_tempo = df["tempo"].min()
    max_tempo = df["tempo"].max()
    if max_tempo > min_tempo:
        df["tempo_normalized"] = (df["tempo"] - min_tempo) / (max_tempo - min_tempo)
    else:
        df["tempo_normalized"] = 0.0
        
    # Save as parquet
    df.to_parquet(PARQUET_PATH, index=False)
    logger.info(f"Successfully created parquet dataset with {len(df)} tracks at {PARQUET_PATH}.")

def load_or_prepare_dataset():
    """
    Main entrypoint: ensures Parquet exists, then loads and returns:
    1. df (Pandas DataFrame of tracks)
    2. feature_matrix (NumPy matrix of normalized audio features)
    3. track_id_to_idx (dictionary mapping track_id string -> row index)
    """
    if not os.path.exists(PARQUET_PATH):
        prepare_parquet()
        
    logger.info(f"Loading track dataset from {PARQUET_PATH}...")
    df = pd.read_parquet(PARQUET_PATH)
    
    # Construct feature matrix
    feature_matrix = df[FEATURE_COLS].to_numpy(dtype=np.float32)
    
    # Create fast index lookup map
    track_id_to_idx = {track_id: idx for idx, track_id in enumerate(df["track_id"])}
    
    logger.info("Dataset loaded successfully into memory.")
    return df, feature_matrix, track_id_to_idx
