from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import logging
from typing import Dict
import torch
from contextlib import asynccontextmanager

from model import WheatDiseaseModel
from diseases import DISEASES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Initialize model
wheat_model = WheatDiseaseModel()

# Confidence threshold
CONFIDENCE_THRESHOLD = 70.0

# ============================================
# LIFESPAN (replaces @app.on_event)
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        wheat_model.load_model()
        logger.info("✅ Model loaded successfully on startup!")
    except Exception as e:
        logger.error(f"❌ Model failed to load: {e}")
    
    yield
    
    # Shutdown (if needed)
    pass

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Wheat Disease Detection API",
    description="AI-powered wheat disease detection with French and Arabic support",
    version="1.0.0",
    lifespan=lifespan  # ✅ Use lifespan instead of on_event
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_category(disease_info):
    """Get disease category in French and Arabic"""
    category = disease_info.get("category", "").lower()

    if category == "root":
        return None, None

    mapping = {
        "maladies foliaires": ("Maladies foliaires", "أمراض الأوراق"),
        "maladies de l'épi": ("Maladies de l'épi", "أمراض السنابل"),
        "ravageurs": ("Ravageurs", "الآفات"),
    }

    return mapping.get(category, ("Autres maladies", "أمراض أخرى"))

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """API information"""
    return {
        "status": "online",
        "name": "Wheat Disease Detection API",
        "version": "1.0.0",
        "developer": "Mehdi Boumiza",
        "diseases": len(DISEASES),
        "languages": ["Français", "العربية"],
        "accuracy": "92.65%"
    }

@app.post("/api/analyze")
async def analyze_wheat_disease(file: UploadFile = File(...)):
    """
    Analyze wheat disease from single uploaded image
    Returns diagnosis in French and Arabic with confidence threshold
    """
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="Le fichier doit être une image / يجب أن يكون الملف صورة"
        )
    
    try:
        # Read and open image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # Get prediction
        prediction = wheat_model.predict(image)
        disease_id = prediction["disease_id"]
        confidence = prediction["confidence"]
        
        # ============================================
        # LOW CONFIDENCE (< 70%)
        # ============================================
        
        if confidence < CONFIDENCE_THRESHOLD:
            return {
                "success": True,
                "uncertain": True,
                "confidence": round(confidence, 2),
                "top3_predictions": prediction["top3_predictions"],
                "message_fr": "Analyse incertaine. Plusieurs maladies possibles.",
                "message_ar": "تحليل غير مؤكد. عدة أمراض محتملة.",
                "recommendation_fr": "Consultez un agronome ou votre CRDA local pour un diagnostic précis.",
                "recommendation_ar": "استشر خبيراً زراعياً أو مكتب التنمية الفلاحية المحلي للحصول على تشخيص دقيق.",
                "tip_fr": "💡 Conseil : Prenez une photo plus proche avec un bon éclairage naturel.",
                "tip_ar": "💡 نصيحة: التقط صورة أقرب مع إضاءة طبيعية جيدة.",
            }
        
        # ============================================
        # HIGH CONFIDENCE (≥ 70%)
        # ============================================
        
        disease_info = DISEASES[disease_id]
        category_fr, category_ar = get_category(disease_info)
        
        # If root disease, don't show
        if category_fr is None:
            return {
                "success": True,
                "uncertain": True,
                "confidence": round(confidence, 2),
                "top3_predictions": prediction["top3_predictions"],
                "message_fr": "Maladie racinaire non affichée",
                "message_ar": "مرض جذري غير معروض",
                "recommendation_fr": "Consultez un agronome pour plus d'informations.",
                "recommendation_ar": "استشر خبيراً زراعياً لمزيد من المعلومات.",
            }
        
        is_critical = disease_info["severity"] == "high"
        
        response = {
            "success": True,
            "uncertain": False,
            "confidence": round(confidence, 2),
            "disease_fr": f"{category_fr} — {disease_info['name_fr']}",
            "disease_ar": f"{category_ar} — {disease_info['name_ar']}",
            "category_fr": category_fr,
            "category_ar": category_ar,
            "severity": disease_info["severity"],
            "is_critical": is_critical,
            "description_fr": disease_info.get("description_fr", ""),
            "description_ar": disease_info.get("description_ar", ""),
            "symptoms": disease_info.get("symptoms", []),
            "symptoms_ar": disease_info.get("symptoms_ar", []),
            "treatment": disease_info.get("treatment", []),
            "treatment_ar": disease_info.get("treatment_ar", []),
            "prevention": disease_info.get("prevention", []),
            "prevention_ar": disease_info.get("prevention_ar", []),
            "recommendation_fr": "Appliquer le traitement recommandé et surveiller l'évolution sur 7 jours.",
            "recommendation_ar": "تطبيق العلاج الموصى به ومراقبة تطور الحالة لمدة 7 أيام.",
            "top3_predictions": prediction["top3_predictions"],
        }
        
        # Add warnings if needed
        if 70 <= confidence < 80:
            response["warning_fr"] = "Confiance modérée. Vérification par un expert recommandée."
            response["warning_ar"] = "ثقة متوسطة. يُنصح بالتحقق من قبل خبير."
        
        if is_critical:
            response["urgent_note_fr"] = "⚠️ MALADIE CRITIQUE - Action immédiate recommandée"
            response["urgent_note_ar"] = "⚠️ مرض خطير - يُنصح بإجراء فوري"
        
        logger.info(f"✅ {disease_info['name_fr']}: {confidence:.1f}%")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/diseases")
async def get_all_diseases():
    """Get all disease information"""
    return {
        "diseases": DISEASES,
        "count": len(DISEASES),
        "languages": ["français", "العربية"]
    }

@app.get("/api/disease/{disease_id}")
async def get_disease_info(disease_id: int):
    """Get specific disease info"""
    if disease_id not in DISEASES:
        raise HTTPException(status_code=404, detail="Disease not found")
    return DISEASES[disease_id]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": wheat_model.model is not None,
        "device": str(device),
        "gpu_available": torch.cuda.is_available()
    }

# ============================================
# NO STATIC FILES - Railway serves API only
# ============================================