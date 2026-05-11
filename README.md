# Backend — Skin Tone & Colour Analysis

The backend for the Face Analyser web app. Built with FastAPI and Python, it accepts a face image, runs a computer vision pipeline to detect skin tone and undertone, and returns a full personalised colour palette as a JSON response.

---

## Tech Stack

- **FastAPI** — API framework
- **OpenCV** — image processing and colour space conversions
- **scikit-learn** — KMeans clustering for dominant skin tone detection
- **NumPy** — numerical operations
- **Pillow** — image handling

---

## How It Works

1. The uploaded image is decoded and passed through a YCrCb colour space mask to isolate skin pixels
2. A center-weighted ellipse mask discards background pixels
3. Skin pixels are converted to LAB colour space — perceptually uniform, making similar-looking colours cluster together accurately
4. KMeans clustering (5 clusters) finds the dominant skin tone
5. A scoring function selects the best cluster, rejecting background bleed and specular highlights
6. Undertone (warm / cool / neutral) is classified from the LAB a and b channel values
7. All palette colours are derived mathematically from the detected skin LAB values and converted back to hex for CSS/web rendering

---

## Project Structure

```
backend/
├── main.py               # FastAPI app, CORS config, server entry point
├── routes.py             # API endpoint definitions
├── image_processing.py   # Full CV pipeline — skin detection, undertone, palette derivation
├── run.py                # Server runner
└── requirements.txt
```

---

## Getting Started

**Clone the repo**
```bash
git clone https://github.com/aishwindersandhu/faceApp
cd faceApp
git checkout server
```

**Create and activate a virtual environment**
```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**Install dependencies**
```bash
pip install -r requirements.txt
```

**Run the server**
```bash
python run.py
```

---

## API

### `GET /ping`
Health check.

**Response**
```json
{ "message": "pong" }
```

---

### `POST /analyze`

Accepts a face image and returns skin tone data with a full colour profile.

**Request**
```
Content-Type: multipart/form-data
Body: image (File) — JPG, PNG, or WEBP
```

**Response**
```json
{
  "filename": "photo.jpg",
  "skinTone": "Medium",
  "colorCode": "#a79272",
  "colorPalette": ["#b8a282", "#a79272", "#8c7255", "#beab82"],
  "profile": {
    "undertone": "warm",
    "contrast": "medium",
    "depth": "Medium",
    "L": 148, "a": 142, "b": 151,
    "warm_palette":  [{ "name": "Camel",       "hex": "#b8935a" }, "..."],
    "cool_palette":  [{ "name": "Navy",         "hex": "#3a4a6b" }, "..."],
    "dark_palette":  [{ "name": "Wine",         "hex": "#6b2d3a" }, "..."],
    "jewel_tones":   [{ "name": "Ruby",         "hex": "#8b3a4a" }, "..."],
    "lip_shades":    [{ "name": "Coral",        "hex": "#c4705a" }, "..."],
    "blush_shades":  [{ "name": "Peach Blush",  "hex": "#d4a888" }, "..."]
  }
}
```

`colorPalette` order: `[Conceal, Base, Contour, Highlight]`

---

## Logs

The server logs key steps so you can trace detection results during development.

**Successful server start**

![Server start](screenshots/image.png)

**Successful image processing**

![Image processing logs](screenshots/image-1.png)

---

## Requirements

```
fastapi
uvicorn
opencv-python-headless
scikit-learn
numpy
pillow
python-multipart
```

---

## Roadmap

- [ ] Integrate MediaPipe for more accurate face region detection
- [ ] Reduce light sensitivity in detection pipeline
- [ ] Proper error handling and fallback responses
- [ ] Add authentication layer for the API
- [ ] Improve accuracy of the data returned, make it more light insensitive
- [ ] Integrate LLM models for further exploration
- [ ] Explore more from color theory 

---

## Contact

Reach out at [aishwinder.sandhu@gmail.com](mailto:aishwinder.sandhu@gmail.com) or on [LinkedIn](https://www.linkedin.com/in/aishwinder-sandhu-3b5002102/)