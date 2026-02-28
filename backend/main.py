from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import logging
from fastapi.staticfiles import StaticFiles
from typing import List
import os
import requests
from io import BytesIO
import torch

from backend.model import WheatDiseaseModel
from backend.diseases import DISEASES

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dropbox URL for your model
MODEL_URL = "https://www.dropbox.com/scl/fi/ooy7h6coji64o27fei8s6/best_booststage2.pth?rlkey=belvhsd0cfakqnetqc2xvqiit&st=fj1y8mqa&dl=1"

# Writable location on Vercel
LOCAL_MODEL_PATH = "/tmp/best_booststage2.pth"

app = FastAPI(
    title="Wheat Disease Detection",
    description="AI wheat disease detection system with French and Arabic support",
    version="1.0.0"
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the model instance globally
wheat_model = WheatDiseaseModel()

# --- CRITICAL: Load model on startup ---
@app.on_event("startup")
async def startup_event():
    try:
        # The load_model() method now handles downloading to /tmp and loading
        wheat_model.load_model()
        logger.info("✅ Model loaded successfully on startup!")
    except Exception as e:
        logger.error(f"❌ Model failed to load: {e}")

def get_category(disease_info):
    category = disease_info.get("category", "").lower()

    if category == "root":
        return None, None

    mapping = {
        "maladies foliaires": ("Maladies foliaires", "أمراض الأوراق"),
        "maladies de l’épi": ("Maladies de l’épi", "أمراض السنابل"),
        "ravageurs": ("Ravageurs", "الآفات"),
    }

    return mapping.get(category, ("Autres maladies", "أمراض أخرى"))

# Multiple image upload endpoint
@app.post("/api/analyze-multiple")
async def analyze_multiple_wheat_diseases(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        if not file.content_type.startswith("image/"):
            results.append({
                "filename": file.filename,
                "success": False,
                "error": "Le fichier doit être une image / يجب أن يكون الملف صورة"
            })
            continue
        try:
            image_data = await file.read()
            image = Image.open(io.BytesIO(image_data)).convert('RGB')
            prediction = wheat_model.predict(image)
            disease_id = prediction["disease_id"]
            confidence = prediction["confidence"]
            

            disease_info = DISEASES[disease_id]
            is_critical = disease_info["severity"] == "high"

            response = {
                "filename": file.filename,
                "success": True,
                "uncertain": False,
                "disease_fr": disease_info["name_fr"],
                "disease_ar": disease_info["name_ar"],
                "severity": disease_info["severity"],
                "is_critical": is_critical,
                "description_fr": disease_info["description_fr"],
                "description_ar": disease_info["description_ar"],

                "symptoms": disease_info["symptoms"],
                "symptoms_ar": disease_info["symptoms_ar"],
                "treatment": disease_info["treatment"],
                "treatment_ar": disease_info["treatment_ar"],
                "prevention": disease_info["prevention"],
                "prevention_ar": disease_info["prevention_ar"],

                "recommendation_fr": "Appliquer le traitement recommandé et surveiller l’évolution sur 7 jours.",
                "recommendation_ar": "تطبيق العلاج الموصى به ومراقبة تطور الحالة لمدة 7 أيام.",

                "tip_fr": "Prenez plusieurs photos sous différents angles pour un meilleur diagnostic.",
                "tip_ar": "التقط عدة صور من زوايا مختلفة لتحسين دقة التشخيص.",

                "top3_predictions": prediction["top3_predictions"],
            }

            if 70 <= confidence < 80:
                response["warning_fr"] = "Confiance modérée. Vérification par un expert recommandée."
                response["warning_ar"] = "ثقة متوسطة. يُنصح بالتحقق من قبل خبير."

            if is_critical:
                response["urgent_note_fr"] = " MALADIE CRITIQUE Action immédiate recommandée"
                response["urgent_note_ar"] = "مرض خطير يُنصح بإجراء فوري"

            results.append(response)
        except Exception as e:
            logger.error(f" Analysis failed for {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    return {"results": results}

@app.post("/api/analyze")
async def analyze_wheat_disease(file: UploadFile = File(...)):

    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="Le fichier doit être une image / يجب أن يكون الملف صورة"
        )
    
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Get prediction
        prediction = wheat_model.predict(image)
        disease_id = prediction["disease_id"]
        confidence = prediction["confidence"]
        
        if confidence < CONFIDENCE_THRESHOLD:
            return {
                "success": True,
                "uncertain": True,
                "top3_predictions": prediction["top3_predictions"],
                "recommendation_fr": "Consultez un agronome ou votre CRDA local pour un diagnostic précis.",
                "recommendation_ar": "استشر خبيراً زراعياً أو مكتب التنمية الفلاحية المحلي للحصول على تشخيص دقيق.",
                "tip_fr": " Conseil : Prenez une photo plus proche avec un bon éclairage naturel.",
                "tip_ar": " نصيحة: التقط صورة أقرب مع إضاءة طبيعية جيدة.",
                "disease_fr": "",
                "disease_ar": "",
                "category_fr": "",
                "category_ar": "",
                "severity": "",
                "is_critical": False,
                "description_fr": "",
                "description_ar": "",
                "symptoms": [],
                "symptoms_ar": [],
                "treatment": [],
                "treatment_ar": [],
                "prevention": [],
                "prevention_ar": [],
            }
    
        disease_info = DISEASES[disease_id]
        category_fr, category_ar = get_category(disease_info)
        # If root disease, do not show as a disease
        if category_fr is None:
            return {
                "success": True,
                "uncertain": True,
                "top3_predictions": prediction["top3_predictions"],
                "message_fr": "Maladie racinaire non affichée / Root disease not shown",
                "message_ar": "مرض جذري غير معروض",
                "recommendation_fr": "Consultez un agronome pour plus d'informations.",
                "recommendation_ar": "استشر خبيراً زراعياً لمزيد من المعلومات.",
                "tip_fr": " Conseil : Prenez une photo plus proche avec un bon éclairage naturel.",
                "tip_ar": " نصيحة: التقط صورة أقرب مع إضاءة طبيعية جيدة.",
                "disease_fr": "",
                "disease_ar": "",
                "category_fr": "",
                "category_ar": "",
                "severity": "",
                "is_critical": False,
                "description_fr": "",
                "description_ar": "",
                "symptoms": [],
                "symptoms_ar": [],
                "treatment": [],
                "treatment_ar": [],
                "prevention": [],
                "prevention_ar": [],
            }
    
        is_critical = disease_info["severity"] == "high"
    
        response = {
            "success": True,
            "uncertain": False,
            "disease_fr": f"{category_fr} — {disease_info['name_fr']}",
            "disease_ar": f"{category_ar} — {disease_info['name_ar']}",
            "category_fr": category_fr,
            "category_ar": category_ar,
            "severity": disease_info["severity"],
            "is_critical": is_critical,

            "description_fr": disease_info["description_fr"],
            "description_ar": disease_info["description_ar"],

            "symptoms": disease_info["symptoms"],
            "symptoms_ar": disease_info["symptoms_ar"],
            "treatment": disease_info["treatment"],
            "treatment_ar": disease_info["treatment_ar"],
            "prevention": disease_info["prevention"],
            "prevention_ar": disease_info["prevention_ar"],

            "recommendation_fr": "Appliquer le traitement recommandé et surveiller l’évolution sur 7 jours.",
            "recommendation_ar": "تطبيق العلاج الموصى به ومراقبة تطور الحالة لمدة 7 أيام.",

            "tip_fr": "Prenez plusieurs photos sous différents angles pour un meilleur diagnostic.",
            "tip_ar": "التقط عدة صور من زوايا مختلفة لتحسين دقة التشخيص.",

            "top3_predictions": prediction["top3_predictions"],
        }
    
        if 70 <= confidence < 80:
            response["warning_fr"] = "Confiance modérée. Vérification par un expert recommandée."
            response["warning_ar"] = "ثقة متوسطة. يُنصح بالتحقق من قبل خبير."
    
        if is_critical:
            response["urgent_note_fr"] = " MALADIE CRITIQUE Action immédiate recommandée"
            response["urgent_note_ar"] = "مرض خطير يُنصح بإجراء فوري"
    
        logger.info(f" {disease_info['name_fr']}: {confidence:.1f}%")
    
        return response
    
    except Exception as e:
        logger.error(f" Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

CONFIDENCE_THRESHOLD = 70.0

@app.get("/api/info")
async def api_info():
    return {
        "status": "online",
        "name": "Wheat Disease Detection",
        "version": "1.0.0",
        "developer": "Mehdi Boumiza",
        "diseases": len(DISEASES),
        "languages": ["Français", "العربية"],
        "accuracy": "92.65%"
    }

@app.get("/api/diseases")
async def get_all_diseases():
    return {
        "diseases": DISEASES,
        "count": len(DISEASES),
        "languages": ["français", "العربية"]
    }

@app.get("/api/disease/{disease_id}")
async def get_disease_info(disease_id: int):
    if disease_id not in DISEASES:
        raise HTTPException(status_code=404, detail="Disease not found")
    return DISEASES[disease_id]

@app.get("/health")
async def health_check():
    import torch
    return {
        "status": "healthy",
        "model_loaded": wheat_model.model is not None,
        "device": str(device) if wheat_model.model else "model not loaded",
        "gpu_available": torch.cuda.is_available()
    }

# Mount the frontend
# Note: For Vercel deployment, ensure this path is correct relative to the root
app.mount(
    "/",
    StaticFiles(
        directory="frontend",
        html=True
    ),
    name="frontend"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
