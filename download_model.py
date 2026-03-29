import os
from sentence_transformers import SentenceTransformer

def download():
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    print("Downloading all-MiniLM-L6-v2 (~90MB)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    save_dir = os.path.join("assets", "models", "all-MiniLM-L6-v2")
    os.makedirs(save_dir, exist_ok=True)
    model.save(save_dir)
    print(f"Model saved securely to {save_dir}")

if __name__ == "__main__":
    download()
