from fastapi import APIRouter, UploadFile, File
from PIL import Image
from fastapi.responses import StreamingResponse
import io
from app.core.image_processing import analyze_image
from app.recommendations.router import router as recommendations_router


# ✅ THIS is what FastAPI is looking for
router = APIRouter()
router.include_router(recommendations_router)

@router.post("/ping")
async def ping():
    print("✅ /ping endpoint was hit")
    #returns json response
    return {"message": "pong"}

@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    print("✅ /inside analyze image")
    image_data = await analyze_image(file)
    return {"data":image_data}

@router.post("/resize/")
async def resize(file: UploadFile = File(...), width: int = 100, height: int = 100):
    resized_image = await resize_image(file, width, height)
    return StreamingResponse(resized_image, media_type="image/jpeg")