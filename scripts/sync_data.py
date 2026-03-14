"""
sync_data.py

Syncs the repository datasets and conversations to Kaggle and Hugging Face.
Uses KAGGLE_API_TOKEN and HF_TOKEN.
"""

import os
import subprocess
from pathlib import Path
from huggingface_hub import HfApi

# Config
KAGGLE_REPO = "hichambedrani/being-repository"
HF_REPO = "LOOFYYLO/being-repository"
BASE_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = BASE_DIR / "datasets"

def sync_to_kaggle():
    print("--- Syncing to Kaggle ---")
    if "KAGGLE_API_TOKEN" not in os.environ:
        print("Error: KAGGLE_API_TOKEN not found in environment.")
        return

    # Kaggle expects dataset-metadata.json in the data directory
    metadata_path = DATASETS_DIR / "dataset-metadata.json"
    if not metadata_path.exists():
        print(f"Error: {metadata_path} not found.")
        return

    try:
        # Create dataset if it doesn't exist, else update
        # We use subprocess to call the kaggle CLI
        # Check if dataset exists
        check = subprocess.run(["kaggle", "datasets", "status", KAGGLE_REPO],
                             capture_output=True, text=True)

        if "NotFound" in check.stderr or check.returncode != 0:
            print(f"Creating new dataset: {KAGGLE_REPO}")
            subprocess.run(["kaggle", "datasets", "create", "-p", str(DATASETS_DIR), "-u"], check=True)
        else:
            print(f"Updating existing dataset: {KAGGLE_REPO}")
            subprocess.run(["kaggle", "datasets", "version", "-p", str(DATASETS_DIR), "-m", "Auto-update from sync script"], check=True)
        print("Kaggle sync complete.")
    except Exception as e:
        print(f"Kaggle sync failed: {e}")

def sync_to_hf():
    print("--- Syncing to Hugging Face ---")
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("Error: HF_TOKEN not found in environment.")
        return

    api = HfApi(token=token)
    try:
        # Create repo if not exists
        try:
            api.create_repo(repo_id=HF_REPO, repo_type="dataset", exist_ok=True)
        except Exception as e:
            print(f"Note on create_repo: {e}")

        print(f"Uploading folder to HF: {HF_REPO}")
        api.upload_folder(
            folder_path=str(BASE_DIR),
            repo_id=HF_REPO,
            repo_type="dataset",
            ignore_patterns=["*.pyc", ".git/*", "__pycache__/*", "*.npy"]
        )
        print("Hugging Face sync complete.")
    except Exception as e:
        print(f"Hugging Face sync failed: {e}")

if __name__ == "__main__":
    sync_to_kaggle()
    sync_to_hf()
