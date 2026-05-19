from sqlalchemy import text
from models import SessionLocal
from datetime import date, timedelta


def fetch_restaurant_signals(restaurant_id: int, as_of_date: date) -> dict:
    """
    Fetches all raw data points needed for campaign analysis.
    No computation or verdicts here — just clean data from the database.
    """
    db = SessionLocal()

    try:
        # ── Restaurant info ───────────────────────────────────────────────────
        restaurant = db.execute(text("""
            SELECT id, name, email, country
            FROM restaurants
            WHERE id = :rid
        """), {"rid": restaurant_id}).fetchone()

        if not restaurant:
            raise ValueError(f"Restaurant {restaurant_id} not found")

        # ── Last 10 days day by day ───────────────────────────────────────────
        ten_days_ago = as_of_date - timedelta(days=10)
        last_10_days = db.execute(text("""
            SELECT
                date,
                TO_CHAR(date, 'Day') as day_name,
                total_revenue,
                order_count,
                avg_order_value
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
            ORDER BY date ASC
        """), {
            "rid": restaurant_id,
            "start": ten_days_ago,
            "end": as_of_date
        }).fetchall()

        # ── Consecutive declining days ────────────────────────────────────────
        consecutive_decline_days = 0
        if len(last_10_days) >= 2:
            reversed_days = list(reversed(last_10_days))
            for i in range(len(reversed_days) - 1):
                if reversed_days[i].total_revenue < reversed_days[i + 1].total_revenue:
                    consecutive_decline_days += 1
                else:
                    break

        # ── Last 3 months average ─────────────────────────────────────────────
        three_months_ago = as_of_date - timedelta(days=90)
        last_3_months = db.execute(text("""
            SELECT
                ROUND(AVG(total_revenue)::numeric, 2) as avg_daily_revenue,
                ROUND(AVG(order_count)::numeric, 1)   as avg_daily_orders,
                ROUND(AVG(avg_order_value)::numeric, 2) as avg_order_value,
                COUNT(*) as days_of_data
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
        """), {
            "rid": restaurant_id,
            "start": three_months_ago,
            "end": as_of_date
        }).fetchone()

        # ── Previous 3 months average ─────────────────────────────────────────
        six_months_ago = as_of_date - timedelta(days=180)
        prev_3_months = db.execute(text("""
            SELECT
                ROUND(AVG(total_revenue)::numeric, 2) as avg_daily_revenue,
                ROUND(AVG(order_count)::numeric, 1)   as avg_daily_orders,
                ROUND(AVG(avg_order_value)::numeric, 2) as avg_order_value,
                COUNT(*) as days_of_data
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
        """), {
            "rid": restaurant_id,
            "start": six_months_ago,
            "end": three_months_ago
        }).fetchone()

        # ── Weekday vs weekend averages ───────────────────────────────────────
        # Weekdays: Mon-Thu (0-3), Weekends: Fri-Sun (4-6)
        dow_breakdown = db.execute(text("""
            SELECT
                CASE
                    WHEN EXTRACT(DOW FROM date) IN (1,2,3,4) THEN 'weekday'
                    ELSE 'weekend'
                END as period_type,
                ROUND(AVG(total_revenue)::numeric, 2) as avg_revenue,
                ROUND(AVG(order_count)::numeric, 1)   as avg_orders,
                ROUND(AVG(avg_order_value)::numeric, 2) as avg_order_value
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
            GROUP BY period_type
        """), {
            "rid": restaurant_id,
            "start": three_months_ago,
            "end": as_of_date
        }).fetchall()

        weekday_avg = None
        weekend_avg = None
        for row in dow_breakdown:
            if row.period_type == "weekday":
                weekday_avg = {
                    "avg_revenue": float(row.avg_revenue or 0),
                    "avg_orders": float(row.avg_orders or 0),
                    "avg_order_value": float(row.avg_order_value or 0)
                }
            else:
                weekend_avg = {
                    "avg_revenue": float(row.avg_revenue or 0),
                    "avg_orders": float(row.avg_orders or 0),
                    "avg_order_value": float(row.avg_order_value or 0)
                }

        # ── Last campaign ─────────────────────────────────────────────────────
        last_campaign = db.execute(text("""
            SELECT sent_at, trigger_type, subject
            FROM campaigns
            WHERE restaurant_id = :rid
              AND status = 'sent'
              AND sent_at <= :as_of
            ORDER BY sent_at DESC
            LIMIT 1
        """), {"rid": restaurant_id, "as_of": as_of_date}).fetchone()

        # ── Customer segments ─────────────────────────────────────────────────
        segments = db.execute(text("""
            SELECT segment, COUNT(*) as count
            FROM customers
            WHERE restaurant_id = :rid
            GROUP BY segment
        """), {"rid": restaurant_id}).fetchall()

        segment_counts = {row.segment: row.count for row in segments}

        return {
            "restaurant": {
                "id": restaurant_id,
                "name": restaurant.name,
                "email": restaurant.email,
                "country": restaurant.country,
            },
            "as_of_date": str(as_of_date),
            "current_day_of_week": as_of_date.strftime("%A"),
            "last_10_days": [
                {
                    "date": str(row.date),
                    "day": row.day_name.strip(),
                    "revenue": float(row.total_revenue),
                    "orders": int(row.order_count),
                    "avg_order_value": float(row.avg_order_value)
                }
                for row in last_10_days
            ],
            "consecutive_declining_days": consecutive_decline_days,
            "last_3_months": {
                "avg_daily_revenue": float(last_3_months.avg_daily_revenue or 0),
                "avg_daily_orders": float(last_3_months.avg_daily_orders or 0),
                "avg_order_value": float(last_3_months.avg_order_value or 0),
                "days_of_data": last_3_months.days_of_data
            },
            "previous_3_months": {
                "avg_daily_revenue": float(prev_3_months.avg_daily_revenue or 0),
                "avg_daily_orders": float(prev_3_months.avg_daily_orders or 0),
                "avg_order_value": float(prev_3_months.avg_order_value or 0),
                "days_of_data": prev_3_months.days_of_data
            },
            "weekday_average": weekday_avg,
            "weekend_average": weekend_avg,
            "last_campaign": {
                "sent_at": str(last_campaign.sent_at) if last_campaign else None,
                "trigger_type": last_campaign.trigger_type if last_campaign else None,
                "subject": last_campaign.subject if last_campaign else None,
                "days_ago": (as_of_date - last_campaign.sent_at.date()).days if last_campaign else None,
            },
            "customer_segments": segment_counts
        }

    finally:
        db.close()


def build_analysis_context(signals: dict) -> str:
    """
    Shapes raw signals into a clean, readable context string for Claude.
    Claude receives this instead of raw JSON — easier to reason over.
    """
    r = signals["restaurant"]
    last_3 = signals["last_3_months"]
    prev_3 = signals["previous_3_months"]
    weekday = signals["weekday_average"]
    weekend = signals["weekend_average"]
    campaign = signals["last_campaign"]
    segments = signals["customer_segments"]

    # Calculate 3-month vs previous 3-month change
    if prev_3["avg_daily_revenue"] > 0:
        three_month_change_pct = round(
            ((last_3["avg_daily_revenue"] - prev_3["avg_daily_revenue"])
             / prev_3["avg_daily_revenue"]) * 100, 1
        )
    else:
        three_month_change_pct = 0
    # If we have data — show the numbers
    # If we don't — show a clear message
    if prev_3['days_of_data'] > 0:
        previous_3_months_note = f"₹{prev_3['avg_daily_revenue']:,.0f} revenue | {prev_3['avg_daily_orders']} orders | AOV ₹{prev_3['avg_order_value']:,.0f}"
    else:
        previous_3_months_note = "No data available for this period"

    # Build last 10 days summary
    days_summary = "\n".join([
        f"  {d['date']} ({d['day'][:3]}): "
        f"Revenue ₹{d['revenue']:,.0f} | "
        f"Orders {d['orders']} | "
        f"AOV ₹{d['avg_order_value']:,.0f}"
        for d in signals["last_10_days"]
    ])

    context = f"""
RESTAURANT: {r['name']} ({r['country']})
ANALYSIS DATE: {signals['as_of_date']} ({signals['current_day_of_week']})

--- REVENUE TRENDS ---
Last 10 days (most recent at bottom):
{days_summary}

Consecutive declining days: {signals['consecutive_declining_days']}

--- BASELINE COMPARISON ---
Last 3 months daily average   : ₹{last_3['avg_daily_revenue']:,.0f} revenue | {last_3['avg_daily_orders']} orders | AOV ₹{last_3['avg_order_value']:,.0f}
Previous 3 months daily average: {previous_3_months_note}
3-month over 3-month change   : {f"{three_month_change_pct:+.1f}%" if prev_3['days_of_data'] > 0 else "N/A (insufficient historical data)"}

--- DAY OF WEEK CONTEXT ---
Weekday average (Mon-Thu): ₹{weekday['avg_revenue']:,.0f} revenue | {weekday['avg_orders']} orders
Weekend average (Fri-Sun): ₹{weekend['avg_revenue']:,.0f} revenue | {weekend['avg_orders']} orders

--- CAMPAIGN HISTORY ---
Last campaign sent: {f"{campaign['days_ago']} days ago (type: {campaign['trigger_type']})" if campaign['days_ago'] else 'No previous campaigns'}
Subject: {campaign['subject'] if campaign['subject'] else 'N/A'}

--- CUSTOMER HEALTH ---
VIP customers    : {segments.get('vip', 0)}
Regular customers: {segments.get('regular', 0)}
At-risk customers: {segments.get('at_risk', 0)} (haven't ordered in 45+ days)
Churned customers: {segments.get('churned', 0)} (haven't ordered in 90+ days)
"""
    return context


if __name__ == "__main__":
    import json
    signals = fetch_restaurant_signals(7, as_of_date=date(2025, 1, 20))
    context = build_analysis_context(signals)
    print(context)