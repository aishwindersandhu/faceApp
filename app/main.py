from fastapi import FastAPI
from app.api import routes

app = FastAPI(title="Image Processing API")

app.include_router(routes.router)

@app.get("/")
def root():
    return {"message": "Welcome to the Image Processing API!"}