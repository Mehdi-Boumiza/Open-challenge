import torch
import torch.nn as nn
from torchvision import transforms, models
from transformers import ViTForImageClassification
from PIL import Image
from typing import Dict, List
import logging
from fastapi import HTTPException
import os # Added for path checking

from diseases import DISEASES

logger = logging.getLogger(__name__)
# Changed to be passed to load_model instead of hardcoded
# MODEL_PATH = "backend/models/best_booststage2.pth" 
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class WheatDiseaseModel:
    def __init__(self):
        self.model = None

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    # 1. ADD 'self' AS THE FIRST ARGUMENT
    # 2. ADD 'model_path' AS THE SECOND ARGUMENT
    def load_model(self, model_path: str):
        try:
            # 3. Check if path exists
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at {model_path}")

            logger.info(f"Loading model from {model_path}...")
            
            # Using HuggingFace model structure based on your code
            model = ViTForImageClassification.from_pretrained(
                'google/vit-base-patch16-224',
                num_labels=len(DISEASES), # Dynamically set labels
                ignore_mismatched_sizes=True
            )
            model.load_state_dict(torch.load(model_path, map_location=device))
            model.to(device)
            model.eval()

            # 4. ASSIGN TO SELF
            self.model = model 
            logger.info("Model loaded successfully")
        
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise HTTPException(status_code=500, detail=f"Model loading failed: {e}")
    
    def predict(self, image: Image.Image) -> Dict:
        if self.model is None:
            raise HTTPException(status_code=500, detail="Model not loaded")

        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            img_tensor = self.transform(image).unsqueeze(0).to(device)

            with torch.no_grad():
                # For HuggingFace models, the output is often a Dict-like object
                outputs = self.model(img_tensor)
                logits = outputs.logits # Get logits from the ViT output
                probabilities = torch.softmax(logits, dim=1)

                confidence, predicted = torch.max(probabilities, dim=1)

            disease_id = predicted.item()
            confidence_score = confidence.item() * 100

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