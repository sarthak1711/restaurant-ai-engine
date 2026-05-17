from fastapi import FastAPI
from dotenv import load_dotenv
import os
from analyzer import get_revenue_summary
from datetime import date
from typing import Optional

app = FastAPI(
    title="Restaurant AI Engine",
    description="Intelligent campaign automation system for restaurants",
    version="0.1.0"
)

load_dotenv()

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "project": "twirll-ai-engine"}

@app.get("/restaurants/{restaurant_id}/analysis")
def get_analysis(
    restaurant_id: int,
    as_of_date: Optional[str] = None
):
    """
    Analyze revenue patterns for a restaurant and detect lull conditions.
    Pass as_of_date (YYYY-MM-DD) to analyze a specific date, or omit for today.
    """
    try:
        analysis_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        result = get_revenue_summary(restaurant_id, as_of_date=analysis_date)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result