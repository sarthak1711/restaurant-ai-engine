from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pipeline import run_campaign_pipeline, run_pipeline_all_restaurants
from models import SessionLocal
from sqlalchemy import text
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


@app.post("/restaurants/{restaurant_id}/campaign/run")
def run_campaign_for_restaurant(
    restaurant_id: int,
    as_of_date: Optional[str] = None
):
    """
    Run the full campaign pipeline for a single restaurant.
    Analyzes revenue data, asks Claude to decide, saves campaign if warranted.
    Pass as_of_date (YYYY-MM-DD) to analyze a specific date, or omit for today.
    """
    try:
        analysis_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        result = run_campaign_pipeline(restaurant_id, as_of_date=analysis_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


@app.post("/campaigns/run-all")
def run_all_restaurants(as_of_date: Optional[str] = None):
    """
    Run the campaign pipeline for ALL restaurants.
    This is what the daily scheduler will trigger.
    """
    try:
        analysis_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    results = run_pipeline_all_restaurants(as_of_date=analysis_date)

    sent_count = sum(1 for r in results if r.get('decision', {}).get('should_send'))

    return {
        "analysis_date":     str(analysis_date),
        "total_restaurants": len(results),
        "campaigns_generated": sent_count,
        "results":           results
    }


@app.get("/restaurants/{restaurant_id}/campaigns")
def get_restaurant_campaigns(restaurant_id: int):
    """Get all campaigns generated for a restaurant."""
    db = SessionLocal()
    try:
        campaigns = db.execute(text("""
            SELECT id, subject, trigger_type, status, created_at, sent_at
            FROM campaigns
            WHERE restaurant_id = :rid
            ORDER BY created_at DESC
            LIMIT 20
        """), {"rid": restaurant_id}).fetchall()

        return [
            {
                "id":           c.id,
                "subject":      c.subject,
                "trigger_type": c.trigger_type,
                "status":       c.status,
                "created_at":   str(c.created_at),
                "sent_at":      str(c.sent_at) if c.sent_at else None
            }
            for c in campaigns
        ]
    finally:
        db.close()


@app.get("/restaurants/{restaurant_id}/campaigns/{campaign_id}")
def get_campaign_detail(restaurant_id: int, campaign_id: int):
    """Get full details of a specific campaign including email body."""
    db = SessionLocal()
    try:
        campaign = db.execute(text("""
            SELECT id, subject, body, trigger_type, status, created_at, sent_at
            FROM campaigns
            WHERE id = :cid AND restaurant_id = :rid
        """), {"cid": campaign_id, "rid": restaurant_id}).fetchone()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {
            "id":           campaign.id,
            "subject":      campaign.subject,
            "body":         campaign.body,
            "trigger_type": campaign.trigger_type,
            "status":       campaign.status,
            "created_at":   str(campaign.created_at),
            "sent_at":      str(campaign.sent_at) if campaign.sent_at else None
        }
    finally:
        db.close()