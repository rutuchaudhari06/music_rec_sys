import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Add parent directory to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.dataset_utils import prepare_parquet

if __name__ == "__main__":
    logger.info("Starting dataset setup process...")
    try:
        prepare_parquet()
        logger.info("Dataset setup successfully completed!")
    except Exception as e:
        logger.error(f"Error preparing dataset: {e}")
        sys.exit(1)
