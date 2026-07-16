from transformers import pipeline

print("Downloading model...")

pipeline(
    "text-classification",
    model="SamLowe/roberta-base-go_emotions"
)

print("Model downloaded successfully!")