from fastapi import FastAPI
from app.api import routes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Image Processing API")
origins = [
    "http://localhost:5173" #no trailing / for adding any url
    "https://faceanalyzer-ui.netlify.app"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # or ["*"] to allow all (for development only)
    allow_credentials=True,
    allow_methods=["*"],              # GET, POST, etc.
    allow_headers=["*"],
)
app.include_router(routes.router)

@app.get("/")
def root():
    return {"message": "Welcome to the Image Processing API!"}