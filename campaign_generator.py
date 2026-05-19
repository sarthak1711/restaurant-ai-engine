import anthropic
import json
import os
from dotenv import load_dotenv
from datetime import date
from models import SessionLocal
from sqlalchemy import text
from analyzer import fetch_restaurant_signals, build_analysis_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_campaign_decision(restaurant_id: int, as_of_date: date = None) -> dict:
    """
    Fetches restaurant signals, builds context, and asks Claude to:
    1. Reason over the raw business data
    2. Decide whether a campaign should be sent
    3. Generate the email content if yes
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Step 1 — fetch raw signals from DB
    signals = fetch_restaurant_signals(restaurant_id, as_of_date)

    # Step 2 — build readable context for Claude
    context = build_analysis_context(signals)

    # Step 3 — build prompt
    prompt = f"""
You are a smart business analyst and marketing expert for a restaurant management platform.

Below is the recent business data for a restaurant. Analyze it carefully and decide 
whether a marketing campaign should be sent to bring customers back.

## Business Data
{context}

## How to reason
- Look at the last 10 days trend — is revenue consistently below the 3-month baseline?
- Compare each day against the weekday/weekend averages — a slow Saturday is more alarming than a slow Monday
- Check consecutive declining days — 3+ days declining is a strong lull signal
- Consider customer health — high at-risk count means re-engagement is urgent
- Never recommend sending if last campaign was less than 14 days ago

## Campaign rules
- Severe drop (40%+ below relevant day-type average): offer 20-25% discount
- Moderate drop (20-40%): offer 10-15% discount
- Mild drop (under 20%): soft re-engagement, no discount needed
- Tailor tone to country: IN=warm Hindi-English mix, AU=casual friendly, CA=professional warm

## Response format
Respond ONLY with a JSON object, no markdown, no extra text:
{{
  "reasoning": "step by step analysis of the data — what you noticed and why you decided",
  "lull_detected": true or false,
  "lull_severity": "none or mild or moderate or severe",
  "key_signal": "the single most important data point that drove your decision",
  "should_send": true or false,
  "reason": "one sentence summary of decision",
  "campaign_type": "discount_offer or re_engagement or general_promotion or null",
  "discount_percentage": 0,
  "email": {{
    "subject": "subject line or null",
    "body": "full email body or null"
  }}
}}
"""

    # Step 4 — call Claude
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_response = message.content[0].text

    # Step 5 — parse response
    try:
        decision = json.loads(raw_response)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            decision = json.loads(json_match.group())
        else:
            decision = {
                "error": "Failed to parse Claude response",
                "raw": raw_response
            }

    return {
        "restaurant": signals["restaurant"],
        "analysis_date": str(as_of_date),
        "signals": signals,
        "campaign_decision": decision
    }


def save_campaign_to_db(restaurant_id: int, decision: dict, analysis_date: date) -> int:
    """
    Saves a generated campaign to the database.
    Returns the campaign id.
    """
    db = SessionLocal()
    try:
        campaign_decision = decision.get("campaign_decision", {})
        email = campaign_decision.get("email", {})

        result = db.execute(text("""
            INSERT INTO campaigns 
                (restaurant_id, subject, body, trigger_type, status, created_at)
            VALUES 
                (:restaurant_id, :subject, :body, :trigger_type, :status, :created_at)
            RETURNING id
        """), {
            "restaurant_id": restaurant_id,
            "subject":       email.get("subject") if email else None,
            "body":          email.get("body") if email else None,
            "trigger_type":  campaign_decision.get("campaign_type"),
            "status":        "draft",
            "created_at":    analysis_date
        })

        campaign_id = result.fetchone().id
        db.commit()
        return campaign_id

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Campaign Generator — Level 2 (Claude reasons over raw data) ===\n")

    print("--- Lull period (Jan 20 2025) ---")
    result = generate_campaign_decision(7, as_of_date=date(2025, 1, 20))
    decision = result['campaign_decision']
    print(f"Reasoning    : {decision.get('reasoning')}")
    print(f"Key signal   : {decision.get('key_signal')}")
    print(f"Lull detected: {decision.get('lull_detected')}")
    print(f"Severity     : {decision.get('lull_severity')}")
    print(f"Should send  : {decision.get('should_send')}")
    print(f"Reason       : {decision.get('reason')}")
    if decision.get('email'):
        print(f"Subject      : {decision['email'].get('subject')}")
        print(f"\nEmail body:\n{decision['email'].get('body')}")

    print("\n--- Peak period (Dec 25 2024) ---")
    result2 = generate_campaign_decision(7, as_of_date=date(2024, 12, 25))
    decision2 = result2['campaign_decision']
    print(f"Reasoning    : {decision2.get('reasoning')}")
    print(f"Lull detected: {decision2.get('lull_detected')}")
    print(f"Should send  : {decision2.get('should_send')}")
    print(f"Reason       : {decision2.get('reason')}")

    print("\n--- Normal period (Mar 1 2025) ---")
    result3 = generate_campaign_decision(7, as_of_date=date(2025, 3, 1))
    decision3 = result3['campaign_decision']
    print(f"Reasoning    : {decision3.get('reasoning')}")
    print(f"Lull detected: {decision3.get('lull_detected')}")
    print(f"Should send  : {decision3.get('should_send')}")
    print(f"Reason       : {decision3.get('reason')}")