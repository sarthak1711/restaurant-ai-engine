from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "project": "twirll-ai-engine"}
