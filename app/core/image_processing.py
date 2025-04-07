from PIL import Image
from io import BytesIO

def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    image = Image.open(BytesIO(image_data))
    image = image.resize((width, height))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()

def ping():
    print("✅ /ping endpoint was hit")
    return {"message": "pong"}