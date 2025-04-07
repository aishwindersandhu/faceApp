from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from app.core.image_processing import resize_image

# ✅ THIS is what FastAPI is looking for
router = APIRouter()

@router.get("/ping")
async def ping():
    print("✅ /ping endpoint was hit")
    #returns json response
    return {"message": "pong"}

@router.post("/resize/")
async def resize(file: UploadFile = File(...), width: int = 100, height: int = 100):
    resized_image = await resize_image(file, width, height)
    return StreamingResponse(resized_image, media_type="image/jpeg")