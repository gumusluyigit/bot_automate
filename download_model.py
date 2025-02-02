import os
import subprocess
from pathlib import Path

def download_model():
    """Download the quantized DeepSeek-Coder model"""
    model_path = Path("models/deepseek-coder-6.7B-instruct-GGUF")
    
    # Create models directory if it doesn't exist
    model_path.parent.mkdir(exist_ok=True)
    
    if not model_path.exists():
        print("Downloading DeepSeek-Coder model...")
        try:
            subprocess.run([
                "git", "clone",
                "https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF",
                str(model_path)
            ], check=True)
            print("Model downloaded successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Error downloading model: {str(e)}")
            return False
    else:
        print("Model directory already exists.")
    
    # Verify the model file exists
    model_file = model_path / "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    if not model_file.exists():
        print(f"Error: Model file not found at {model_file}")
        return False
    
    print("Model is ready to use!")
    return True

if __name__ == "__main__":
    download_model() 