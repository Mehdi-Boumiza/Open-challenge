import torch
import torch.nn as nn
from torchvision import transforms, models
from transformers import ViTForImageClassification
from PIL import Image
from typing import Dict, List
import logging
from fastapi import HTTPException
import os
import requests  # Ensure 'requests' is in your requirements.txt
from backend.diseases import DISEASES

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Determine device (CPU for Vercel)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class WheatDiseaseModel:
    def __init__(self):
        self.model = None
        # Vercel allows writing files only to /tmp
        self.model_path = "/tmp/best_booststage2.pth" 
        self.dropbox_url = "https://www.dropbox.com/scl/fi/ooy7h6coji64o27fei8s6/best_booststage2.pth?rlkey=belvhsd0cfakqnetqc2xvqiit&st=fj1y8mqa&dl=1"

        # Define image transformations
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def load_model(self):
        """
        Downloads model from Dropbox to /tmp if not present, 
        then loads it into memory.
        """
        try:
            # 1. Download if not exists in /tmp
            if not os.path.exists(self.model_path):
                logger.info(f"Downloading model from Dropbox to {self.model_path}...")
                response = requests.get(self.dropbox_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download model. Status code: {response.status_code}")
                
                with open(self.model_path, 'wb') as f:
                    f.write(response.content)
                logger.info("Download complete.")
            else:
                logger.info("Model already exists in /tmp, skipping download.")

            # 2. Load the model into memory
            logger.info(f"Loading model into memory from {self.model_path}...")
            
            # Initialize model architecture based on HuggingFace Vit
            model = ViTForImageClassification.from_pretrained(
                'google/vit-base-patch16-224',
                num_labels=len(DISEASES), # Dynamically set labels
                ignore_mismatched_sizes=True
            )
            
            # Load trained weights
            model.load_state_dict(torch.load(self.model_path, map_location=device))
            model.to(device)
            model.eval()

            self.model = model 
            logger.info("Model loaded successfully into memory.")
        
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise HTTPException(status_code=500, detail=f"Model loading failed: {e}")
    
    def predict(self, image: Image.Image) -> Dict:
        """
        Predicts disease from image and returns top 3 predictions.
        """
        if self.model is None:
            raise HTTPException(status_code=500, detail="Model not loaded. Call load_model() first.")

        try:
            # Preprocess image
            if image.mode != "RGB":
                image = image.convert("RGB")

            img_tensor = self.transform(image).unsqueeze(0).to(device)

            # Run inference
            with torch.no_grad():
                outputs = self.model(img_tensor)
                logits = outputs.logits # Get logits from the ViT output
                probabilities = torch.softmax(logits, dim=1)

                confidence, predicted = torch.max(probabilities, dim=1)

            disease_id = predicted.item()
            confidence_score = confidence.item() * 100

            # Get Top 3 predictions
            top3_probs, top3_indices = torch.topk(probabilities, 3)

            top3_predictions: List[Dict] = [
                {
                    "disease_fr": DISEASES[idx.item()]["name_fr"],
                    "disease_ar": DISEASES[idx.item()]["name_ar"],
                    "confidence": round(prob.item() * 100, 2)
                }
                for prob, idx in zip(top3_probs[0], top3_indices[0])
            ]

            return {
                "disease_id": disease_id,
                "confidence": round(confidence_score, 2),
                "top3_predictions": top3_predictions
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise HTTPException(status_code=500, detail="Prediction failed")
