from datetime import date
from analyzer import fetch_restaurant_signals, build_analysis_context
from campaign_generator import generate_campaign_decision, save_campaign_to_db
from models import SessionLocal
from sqlalchemy import text


def run_campaign_pipeline(restaurant_id: int, as_of_date: date = None) -> dict:
    """
    Orchestrates the full campaign pipeline for a single restaurant:
    1. Fetch raw signals from DB
    2. Build analysis context
    3. Ask Claude to reason and decide
    4. If campaign should be sent, save it as draft to DB
    5. Return full result

    This is the single entry point called by FastAPI endpoints
    and later by the scheduler.
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Step 1 + 2 — fetch and build context (inside generate_campaign_decision)
    result = generate_campaign_decision(restaurant_id, as_of_date)

    decision = result.get("campaign_decision", {})
    campaign_id = None

    # Step 3 — save to DB only if Claude decided to send
    if decision.get("should_send") and not decision.get("error"):
        campaign_id = save_campaign_to_db(
            restaurant_id=restaurant_id,
            decision=result,
            analysis_date=as_of_date
        )

    return {
        "restaurant":    result["restaurant"],
        "analysis_date": str(as_of_date),
        "decision": {
            "lull_detected":   decision.get("lull_detected"),
            "lull_severity":   decision.get("lull_severity"),
            "key_signal":      decision.get("key_signal"),
            "should_send":     decision.get("should_send"),
            "reason":          decision.get("reason"),
            "reasoning":       decision.get("reasoning"),
            "campaign_type":   decision.get("campaign_type"),
            "discount_pct":    decision.get("discount_percentage"),
        },
        "campaign": {
            "id":      campaign_id,
            "saved":   campaign_id is not None,
            "subject": decision.get("email", {}).get("subject") if decision.get("email") else None,
            "body":    decision.get("email", {}).get("body") if decision.get("email") else None,
        }
    }


def run_pipeline_all_restaurants(as_of_date: date = None) -> list:
    """
    Runs the campaign pipeline for every restaurant in the database.
    This is what the daily scheduler will call.
    """
    if as_of_date is None:
        as_of_date = date.today()

    db = SessionLocal()
    try:
        restaurants = db.execute(text(
            "SELECT id, name FROM restaurants ORDER BY id"
        )).fetchall()
    finally:
        db.close()

    results = []
    for restaurant in restaurants:
        try:
            print(f"Running pipeline for: {restaurant.name}")
            result = run_campaign_pipeline(restaurant.id, as_of_date)
            results.append(result)
            print(f"  → should_send: {result['decision']['should_send']} | severity: {result['decision']['lull_severity']}")
        except Exception as e:
            print(f"  → Error for {restaurant.name}: {e}")
            results.append({
                "restaurant": {"id": restaurant.id, "name": restaurant.name},
                "error": str(e)
            })

    return results


if __name__ == "__main__":
    print("=== Running pipeline for single restaurant ===\n")
    result = run_campaign_pipeline(7, as_of_date=date(2025, 1, 20))
    print(f"Restaurant : {result['restaurant']['name']}")
    print(f"Lull       : {result['decision']['lull_detected']} ({result['decision']['lull_severity']})")
    print(f"Should send: {result['decision']['should_send']}")
    print(f"Campaign ID: {result['campaign']['id']}")
    print(f"Subject    : {result['campaign']['subject']}")

    print("\n=== Running pipeline for ALL restaurants (lull period) ===\n")
    all_results = run_pipeline_all_restaurants(as_of_date=date(2025, 1, 20))
    print(f"\nProcessed {len(all_results)} restaurants")
    sent_count = sum(1 for r in all_results if r.get('decision', {}).get('should_send'))
    print(f"Campaigns generated: {sent_count}/{len(all_results)}")