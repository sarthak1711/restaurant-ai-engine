import anthropic
import json
import os
from dotenv import load_dotenv
from analyzer import get_revenue_summary
from datetime import date

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_campaign(restaurant_id: int, as_of_date: date = None) -> dict:
    """
    Takes revenue analysis and uses Claude to:
    1. Decide whether a campaign should be sent
    2. Generate the email content if yes
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Step 1 — get the analysis
    analysis = get_revenue_summary(restaurant_id, as_of_date=as_of_date)

    # Step 2 — build the prompt
    prompt = f"""
You are an AI assistant for a restaurant management platform.
You have been given a revenue analysis for a restaurant.
Your job is to decide whether to send a marketing campaign email and generate the content if yes.

## Restaurant Analysis
{json.dumps(analysis, indent=2)}

## Your Task
Based on this analysis, decide:
1. Should a campaign email be sent right now?
2. If yes, what type? (discount_offer, re_engagement, general_promotion)
3. Generate the email content

## Rules
- Only recommend sending if is_lull is true
- Do not recommend sending if days_since_last_campaign is less than 14 (avoid spamming)
- If severity is "severe", offer a higher discount (20-25%)
- If severity is "moderate", offer a moderate discount (10-15%)
- If severity is "mild", send a softer re-engagement email
- Tailor the tone to the restaurant's country (IN=India, AU=Australia, CA=Canada)
- Address the customer warmly but professionally

## Response Format
Respond ONLY with a JSON object, no extra text, no markdown backticks:
{{
  "should_send": true or false,
  "reason": "one sentence explanation",
  "campaign_type": "discount_offer or re_engagement or general_promotion or null",
  "discount_percentage": 0,
  "email": {{
    "subject": "email subject line here",
    "body": "full email body here with proper greeting and sign off"
  }}
}}
"""

    # Step 3 — call Claude
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Step 4 — parse response
    raw_response = message.content[0].text

    try:
        campaign_decision = json.loads(raw_response)
    except json.JSONDecodeError:
        # If Claude added any extra text, try to extract JSON
        import re
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            campaign_decision = json.loads(json_match.group())
        else:
            campaign_decision = {"error": "Failed to parse response", "raw": raw_response}

    return {
        "analysis": analysis,
        "campaign_decision": campaign_decision
    }


if __name__ == "__main__":
    print("=== Testing campaign generation during lull period ===\n")
    result = generate_campaign(7, as_of_date=date(2025, 1, 20))

    print("ANALYSIS SUMMARY:")
    print(f"  Restaurant  : {result['analysis']['restaurant']['name']}")
    print(f"  Is lull     : {result['analysis']['lull_detection']['is_lull']}")
    print(f"  Severity    : {result['analysis']['lull_detection']['severity']}")
    print(f"  Revenue drop: {result['analysis']['lull_detection']['revenue_drop_pct']}%")
    print(f"  Days since last campaign: {result['analysis']['campaign_context']['days_since_last_campaign']}")

    print("\nCAMPAIGN DECISION:")
    decision = result['campaign_decision']
    print(f"  Should send : {decision.get('should_send')}")
    print(f"  Reason      : {decision.get('reason')}")
    print(f"  Type        : {decision.get('campaign_type')}")
    print(f"  Discount    : {decision.get('discount_percentage')}%")

    print("\nGENERATED EMAIL:")
    if decision.get('email'):
        print(f"  Subject: {decision['email'].get('subject')}")
        print(f"\n  Body:\n{decision['email'].get('body')}")

    print("\n=== Testing during peak period (should NOT send) ===\n")
    result2 = generate_campaign(7, as_of_date=date(2024, 12, 25))
    decision2 = result2['campaign_decision']
    print(f"  Should send : {decision2.get('should_send')}")
    print(f"  Reason      : {decision2.get('reason')}")