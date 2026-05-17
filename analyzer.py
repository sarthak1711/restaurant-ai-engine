from sqlalchemy import text
from models import SessionLocal
from datetime import date, timedelta


def get_revenue_summary(restaurant_id: int, as_of_date: date = None) -> dict:
    """
    Analyzes revenue patterns for a restaurant and detects lull conditions.
    
    Returns a summary dict the AI agent will use to make campaign decisions.
    """
    if as_of_date is None:
        as_of_date = date.today()

    db = SessionLocal()

    try:
        # ── 30-day baseline average ───────────────────────────────────────────
        thirty_days_ago = as_of_date - timedelta(days=30)

        baseline = db.execute(text("""
            SELECT 
                ROUND(AVG(total_revenue)::numeric, 2) as avg_daily_revenue,
                ROUND(AVG(order_count)::numeric, 1)   as avg_daily_orders,
                COUNT(*)                               as days_of_data
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
        """), {
            "rid":   restaurant_id,
            "start": thirty_days_ago,
            "end":   as_of_date
        }).fetchone()

        avg_daily_revenue = float(baseline.avg_daily_revenue or 0)
        avg_daily_orders  = float(baseline.avg_daily_orders or 0)

        # ── Last 7 days performance ───────────────────────────────────────────
        seven_days_ago = as_of_date - timedelta(days=7)

        recent = db.execute(text("""
            SELECT 
                ROUND(AVG(total_revenue)::numeric, 2) as avg_revenue,
                ROUND(AVG(order_count)::numeric, 1)   as avg_orders,
                ROUND(MIN(total_revenue)::numeric, 2) as min_revenue,
                ROUND(MAX(total_revenue)::numeric, 2) as max_revenue,
                COUNT(*)                              as days_of_data
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
        """), {
            "rid":   restaurant_id,
            "start": seven_days_ago,
            "end":   as_of_date
        }).fetchone()

        recent_avg_revenue = float(recent.avg_revenue or 0)
        recent_avg_orders  = float(recent.avg_orders or 0)

        # ── Last 7 days day by day — for trend analysis ───────────────────────
        daily_recent = db.execute(text("""
            SELECT date, total_revenue, order_count
            FROM daily_revenue
            WHERE restaurant_id = :rid
              AND date >= :start
              AND date < :end
            ORDER BY date ASC
        """), {
            "rid":   restaurant_id,
            "start": seven_days_ago,
            "end":   as_of_date
        }).fetchall()

        # ── Consecutive declining days ────────────────────────────────────────
        # Walk backwards through daily data and count how many days in a row
        # revenue has been falling — key signal for gradual lull detection
        consecutive_decline_days = 0
        if len(daily_recent) >= 2:
            reversed_days = list(reversed(daily_recent))
            for i in range(len(reversed_days) - 1):
                if reversed_days[i].total_revenue < reversed_days[i + 1].total_revenue:
                    consecutive_decline_days += 1
                else:
                    break

        # ── Revenue drop percentage ───────────────────────────────────────────
        if avg_daily_revenue > 0:
            revenue_drop_pct = round(
                ((avg_daily_revenue - recent_avg_revenue) / avg_daily_revenue) * 100, 1
            )
        else:
            revenue_drop_pct = 0.0

        # ── Lull verdict ──────────────────────────────────────────────────────
        # Conditions for a lull:
        # - Revenue dropped more than 25% below 30-day average, OR
        # - Revenue dropped more than 15% AND 3+ consecutive declining days
        is_lull = (
            revenue_drop_pct > 25
        ) or (
            revenue_drop_pct > 15 and consecutive_decline_days >= 3
        )

        # Severity of lull
        if revenue_drop_pct > 40:
            lull_severity = "severe"
        elif revenue_drop_pct > 25:
            lull_severity = "moderate"
        elif revenue_drop_pct > 15:
            lull_severity = "mild"
        else:
            lull_severity = "none"

        # ── Last campaign sent ────────────────────────────────────────────────
        last_campaign = db.execute(text("""
            SELECT sent_at, trigger_type
            FROM campaigns
            WHERE restaurant_id = :rid
            AND status = 'sent'
            AND sent_at <= :as_of
            ORDER BY sent_at DESC
            LIMIT 1
            """), {"rid": restaurant_id, "as_of": as_of_date}).fetchone()
        days_since_last_campaign = None
        if last_campaign and last_campaign.sent_at:
            delta = as_of_date - last_campaign.sent_at.date()
            days_since_last_campaign = delta.days

        # ── Customer segments ─────────────────────────────────────────────────
        segments = db.execute(text("""
            SELECT segment, COUNT(*) as count
            FROM customers
            WHERE restaurant_id = :rid
            GROUP BY segment
        """), {"rid": restaurant_id}).fetchall()

        segment_counts = {row.segment: row.count for row in segments}

        # ── Restaurant info ───────────────────────────────────────────────────
        restaurant = db.execute(text("""
            SELECT name, email, country FROM restaurants WHERE id = :rid
        """), {"rid": restaurant_id}).fetchone()

        # ── Build summary ─────────────────────────────────────────────────────
        return {
            "restaurant": {
                "id":      restaurant_id,
                "name":    restaurant.name,
                "email":   restaurant.email,
                "country": restaurant.country,
            },
            "analysis_date": str(as_of_date),
            "baseline": {
                "avg_daily_revenue": avg_daily_revenue,
                "avg_daily_orders":  avg_daily_orders,
                "days_analyzed":     baseline.days_of_data,
            },
            "recent_7_days": {
                "avg_daily_revenue":       recent_avg_revenue,
                "avg_daily_orders":        recent_avg_orders,
                "min_daily_revenue":       float(recent.min_revenue or 0),
                "max_daily_revenue":       float(recent.max_revenue or 0),
                "consecutive_decline_days": consecutive_decline_days,
            },
            "lull_detection": {
                "is_lull":           is_lull,
                "severity":          lull_severity,
                "revenue_drop_pct":  revenue_drop_pct,
            },
            "campaign_context": {
                "days_since_last_campaign":    days_since_last_campaign,
                "last_campaign_trigger_type":  last_campaign.trigger_type if last_campaign else None,
            },
            "customer_segments": segment_counts,
        }

    finally:
        db.close()


if __name__ == "__main__":
    # Test it against restaurant 1 during a known lull period
    import json

    print("=== Testing during lull period (Jan 20 2025) ===")
    result = get_revenue_summary(7, as_of_date=date(2025, 1, 20))
    print(json.dumps(result, indent=2))

    print("\n=== Testing during peak period (Dec 25 2024) ===")
    result = get_revenue_summary(7, as_of_date=date(2024, 12, 25))
    print(json.dumps(result, indent=2))

    print("\n=== Testing normal period (Mar 1 2025) ===")
    result = get_revenue_summary(7, as_of_date=date(2025, 3, 1))
    print(json.dumps(result, indent=2))