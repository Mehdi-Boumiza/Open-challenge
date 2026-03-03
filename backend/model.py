import torch
import torch.nn as nn
from torchvision import transforms
from transformers import ViTForImageClassification
from PIL import Image
from typing import Dict, List
import logging
import os
import requests
import shutil
from diseases import DISEASES

# Setup Logging
logger = logging.getLogger(__name__)

class WheatDiseaseModel:
    def __init__(self):
        self.model = None
        # Railway/Linux temporary directory for storing the downloaded weights
        self.model_path = "/tmp/best_booststage2.pth"
        self.dropbox_url = "https://www.dropbox.com/scl/fi/ooy7h6coji64o27fei8s6/best_booststage2.pth?rlkey=belvhsd0cfakqnetqc2xvqiit&st=fj1y8mqa&dl=1"
        
        # Image transformation pipeline (Must match your training preprocessing)
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
        Downloads the model weights from Dropbox if not present 
        and loads the ViT architecture into memory.
        """
        try:
            # Step 1: Streamed Download
            # This is critical for Railway to avoid exceeding RAM limits during the download
            if not os.path.exists(self.model_path):
                logger.info("Downloading model weights from Dropbox...")
                with requests.get(self.dropbox_url, stream=True) as r:
                    r.raise_for_status()
                    with open(self.model_path, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                logger.info("Download successful.")
            else:
                logger.info("Model weights already exist in /tmp.")

            # Step 2: Initialize ViT Architecture
            logger.info("Initializing Vision Transformer (ViT) architecture...")
            device = torch.device("cpu") # Default to CPU for cloud stability
            
            # Load the base model from HuggingFace
            model = ViTForImageClassification.from_pretrained(
                'google/vit-base-patch16-224',
                num_labels=len(DISEASES),
                ignore_mismatched_sizes=True
            )
            
            # Step 3: Load the custom trained weights
            state_dict = torch.load(self.model_path, map_location=device)
            model.load_state_dict(state_dict)
            model.to(device)
            model.eval()
            
            self.model = model
            logger.info("Model loaded successfully into memory.")
            
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            raise RuntimeError(f"Model initialization error: {e}")

    def predict(self, image: Image.Image) -> Dict:
        """
        Takes a PIL image, runs inference, and returns prediction results.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded. Ensure load_model() was called.")

        try:
            # Ensure image is in RGB format (handles PNGs with alpha channels)
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Preprocess the image
            img_tensor = self.transform(image).unsqueeze(0)

            # Run inference without calculating gradients (saves memory/time)
            with torch.no_grad():
                outputs = self.model(img_tensor)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
                
                # Extract top 3 highest probabilities
                top3_probs, top3_indices = torch.topk(probabilities, 3)

            # Format the top 3 results for the API response
            top3_results = [
                {
                    "disease_fr": DISEASES[idx.item()]["name_fr"],
                    "disease_ar": DISEASES[idx.item()]["name_ar"],
                    "confidence": round(prob.item() * 100, 2)
                }
                for prob, idx in zip(top3_probs[0], top3_indices[0])
            ]

            return {
                "disease_id": int(top3_indices[0][0]),
                "confidence": round(top3_probs[0][0].item() * 100, 2),
                "top3_predictions": top3_results
            }

        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise e