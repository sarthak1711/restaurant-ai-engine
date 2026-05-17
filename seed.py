import random
from datetime import datetime, timedelta, date
from models import SessionLocal, Restaurant, Order, DailyRevenue, Customer, Campaign, engine
from sqlalchemy.orm import Session

# ── Helpers ───────────────────────────────────────────────────────────────────

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def random_datetime_on(d: date) -> datetime:
    # Realistic meal time distribution
    # Lunch: 12-15, Dinner: 19-22, off-peak: 10-12, 15-19
    meal_slot = random.choices(
        ["lunch", "dinner", "off_peak"],
        weights=[35, 50, 15]
    )[0]
    if meal_slot == "lunch":
        hour = random.randint(12, 14)
    elif meal_slot == "dinner":
        hour = random.randint(19, 22)
    else:
        hour = random.randint(10, 18)
    return datetime(d.year, d.month, d.day, hour, random.randint(0, 59))

# ── Restaurant profiles — size differences by country ─────────────────────────

RESTAURANTS = [
    # India — smaller avg order value, higher volume
    {"name": "Spice Garden",       "email": "spice@example.com",   "country": "IN",
     "base_orders": 55,  "base_aov": 520,  "size": "medium"},
    {"name": "The Curry House",    "email": "curry@example.com",   "country": "IN",
     "base_orders": 40,  "base_aov": 480,  "size": "small"},
    {"name": "Tandoor Express",    "email": "tandoor@example.com", "country": "IN",
     "base_orders": 75,  "base_aov": 560,  "size": "large"},
    # Australia — higher aov, moderate volume
    {"name": "Sydney Bites",       "email": "sydney@example.com",  "country": "AU",
     "base_orders": 45,  "base_aov": 1800, "size": "medium"},
    {"name": "Melbourne Kitchen",  "email": "melb@example.com",    "country": "AU",
     "base_orders": 35,  "base_aov": 1650, "size": "small"},
    # Canada — between india and australia
    {"name": "Toronto Diner",      "email": "toronto@example.com", "country": "CA",
     "base_orders": 50,  "base_aov": 1200, "size": "medium"},
]

# Day of week multipliers — Mon=0, Sun=6
DOW_MULTIPLIER = {
    0: 0.70,   # Monday    — deadest day
    1: 0.75,   # Tuesday
    2: 0.82,   # Wednesday
    3: 0.88,   # Thursday
    4: 1.20,   # Friday    — starts the weekend rush
    5: 1.40,   # Saturday  — busiest
    6: 1.25,   # Sunday
}

# ── Lull and peak periods ─────────────────────────────────────────────────────

# Each lull has a gradual_start — when the decline begins (3-4 days before core lull)
LULL_PERIODS = [
    {
        "gradual_start": date(2024, 11, 28),
        "core_start":    date(2024, 12, 2),
        "core_end":      date(2024, 12, 10),
        "gradual_end":   date(2024, 12, 13),
        "name":          "early_december_slump"
    },
    {
        "gradual_start": date(2025, 1, 12),
        "core_start":    date(2025, 1, 15),
        "core_end":      date(2025, 1, 25),
        "gradual_end":   date(2025, 1, 28),
        "name":          "post_newyear_slump"
    },
    {
        "gradual_start": date(2025, 3, 1),
        "core_start":    date(2025, 3, 4),
        "core_end":      date(2025, 3, 12),
        "gradual_end":   date(2025, 3, 15),
        "name":          "march_midmonth_dip"
    },
]

PEAK_PERIODS = [
    {"start": date(2024, 12, 20), "end": date(2024, 12, 31), "name": "christmas_newyear", "multiplier": 1.85},
    {"start": date(2025, 2, 13),  "end": date(2025, 2, 15),  "name": "valentines",        "multiplier": 1.60},
    {"start": date(2025, 4, 18),  "end": date(2025, 4, 21),  "name": "easter",            "multiplier": 1.45},
]

# Holiday recovery — after a peak, there's always a hangover dip
RECOVERY_PERIODS = [
    {"start": date(2025, 1, 1),  "end": date(2025, 1, 10),  "multiplier": 0.65},  # post christmas/NY
    {"start": date(2025, 2, 16), "end": date(2025, 2, 20),  "multiplier": 0.80},  # post valentines
    {"start": date(2025, 4, 22), "end": date(2025, 4, 26),  "multiplier": 0.78},  # post easter
]

def get_lull_multiplier(d: date):
    for lull in LULL_PERIODS:
        if lull["core_start"] <= d <= lull["core_end"]:
            return 0.38   # core lull — sharp drop
        if lull["gradual_start"] <= d < lull["core_start"]:
            # gradual decline — interpolate over the days
            days_total  = (lull["core_start"] - lull["gradual_start"]).days
            days_in     = (d - lull["gradual_start"]).days
            progress    = days_in / days_total   # 0.0 → 1.0
            return 1.0 - (progress * 0.62)       # tapers from 1.0 down to 0.38
        if lull["core_end"] < d <= lull["gradual_end"]:
            # gradual recovery after lull
            days_total  = (lull["gradual_end"] - lull["core_end"]).days
            days_in     = (d - lull["core_end"]).days
            progress    = days_in / days_total
            return 0.38 + (progress * 0.62)      # recovers from 0.38 back to 1.0
    return None

def get_peak_multiplier(d: date):
    for peak in PEAK_PERIODS:
        if peak["start"] <= d <= peak["end"]:
            return peak["multiplier"]
    return None

def get_recovery_multiplier(d: date):
    for rec in RECOVERY_PERIODS:
        if rec["start"] <= d <= rec["end"]:
            return rec["multiplier"]
    return None

def get_day_multiplier(d: date, restaurant: dict) -> tuple:
    """Returns (order_multiplier, aov_multiplier) for a given day."""
    base_mult = DOW_MULTIPLIER[d.weekday()]

    lull_mult     = get_lull_multiplier(d)
    peak_mult     = get_peak_multiplier(d)
    recovery_mult = get_recovery_multiplier(d)

    if lull_mult is not None:
        order_mult = base_mult * lull_mult
        aov_mult   = lull_mult + 0.15   # aov drops less than volume during lull
    elif peak_mult is not None:
        order_mult = base_mult * peak_mult
        aov_mult   = peak_mult * 1.1    # people spend more per order during peaks
    elif recovery_mult is not None:
        order_mult = base_mult * recovery_mult
        aov_mult   = recovery_mult + 0.10
    else:
        order_mult = base_mult
        aov_mult   = 1.0

    return order_mult, aov_mult

START_DATE = date(2024, 11, 1)
END_DATE   = date(2025, 5, 1)

FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali",
               "James", "Sarah", "Liam", "Emma", "Noah", "Olivia",
               "Arjun", "Meera", "Rohan", "Kavya", "Tom", "Lucy"]
LAST_NAMES  = ["Sharma", "Patel", "Singh", "Smith", "Brown", "Wilson",
               "Johnson", "Williams", "Jones", "Taylor", "Martin", "Lee",
               "Gupta", "Kumar", "Verma", "Chen", "Davis", "Miller"]

# ── Seed ──────────────────────────────────────────────────────────────────────

def seed():
    db: Session = SessionLocal()

    try:
        # Clear
        db.query(Campaign).delete()
        db.query(Order).delete()
        db.query(DailyRevenue).delete()
        db.query(Customer).delete()
        db.query(Restaurant).delete()
        db.commit()
        print("Cleared existing data")

        # ── Restaurants ──
        restaurant_objects = []
        for r in RESTAURANTS:
            restaurant = Restaurant(
                name=r["name"],
                email=r["email"],
                country=r["country"],
                created_at=datetime(2024, 10, 1)
            )
            db.add(restaurant)
            restaurant_objects.append((restaurant, r))
        db.commit()
        print(f"Created {len(restaurant_objects)} restaurants")

        # ── Customers — repeat vs new ratio ──
        # Each restaurant has a pool of repeat customers (60%)
        # and new customers trickle in each month (40%)
        all_customers = []
        customer_pools = {}   # restaurant_id → list of customer ids

        for restaurant, profile in restaurant_objects:
            pool = []
            # Core repeat customers — 60% of expected monthly traffic
            num_repeat = int(profile["base_orders"] * 30 * 0.60 / 8)  # avg 8 visits/month
            num_repeat = max(num_repeat, 60)

            for _ in range(num_repeat):
                first = random.choice(FIRST_NAMES)
                last  = random.choice(LAST_NAMES)
                total_orders = random.randint(8, 45)
                total_spent  = round(total_orders * profile["base_aov"] * random.uniform(0.85, 1.15), 2)
                last_order   = random_date(date(2025, 2, 1), END_DATE)

                if total_orders >= 25 and total_spent >= profile["base_aov"] * 20:
                    segment = "vip"
                else:
                    segment = "regular"

                c = Customer(
                    restaurant_id=restaurant.id,
                    name=f"{first} {last}",
                    email=f"{first.lower()}.{last.lower()}{random.randint(1,999)}@example.com",
                    total_orders=total_orders,
                    total_spent=total_spent,
                    last_order_date=last_order,
                    segment=segment
                )
                db.add(c)
                pool.append(c)
                all_customers.append(c)

            # At-risk customers — last order 45-90 days ago
            for _ in range(int(num_repeat * 0.15)):
                first = random.choice(FIRST_NAMES)
                last  = random.choice(LAST_NAMES)
                last_order = random_date(date(2024, 11, 1), date(2025, 1, 15))
                c = Customer(
                    restaurant_id=restaurant.id,
                    name=f"{first} {last}",
                    email=f"{first.lower()}.{last.lower()}{random.randint(1,999)}@example.com",
                    total_orders=random.randint(3, 10),
                    total_spent=round(random.randint(3,10) * profile["base_aov"] * 0.9, 2),
                    last_order_date=last_order,
                    segment="at_risk"
                )
                db.add(c)
                pool.append(c)
                all_customers.append(c)

            # Churned customers — last order 90+ days ago
            for _ in range(int(num_repeat * 0.10)):
                first = random.choice(FIRST_NAMES)
                last  = random.choice(LAST_NAMES)
                last_order = random_date(START_DATE, date(2024, 12, 1))
                c = Customer(
                    restaurant_id=restaurant.id,
                    name=f"{first} {last}",
                    email=f"{first.lower()}.{last.lower()}{random.randint(1,999)}@example.com",
                    total_orders=random.randint(1, 3),
                    total_spent=round(random.randint(1,3) * profile["base_aov"] * 0.8, 2),
                    last_order_date=last_order,
                    segment="churned"
                )
                db.add(c)
                pool.append(c)
                all_customers.append(c)

            db.commit()
            customer_pools[restaurant.id] = pool

        print(f"Created {len(all_customers)} customers")

        # ── Daily Revenue + Orders ──
        total_orders_created = 0
        current = START_DATE

        while current <= END_DATE:
            for restaurant, profile in restaurant_objects:
                order_mult, aov_mult = get_day_multiplier(current, profile)

                # Add small random noise so data doesn't look mechanical
                noise        = random.uniform(0.92, 1.08)
                order_count  = max(5, int(profile["base_orders"] * order_mult * noise))
                aov          = round(profile["base_aov"] * aov_mult * random.uniform(0.95, 1.05), 2)
                total_rev    = round(order_count * aov, 2)

                dr = DailyRevenue(
                    restaurant_id=restaurant.id,
                    date=current,
                    total_revenue=total_rev,
                    order_count=order_count,
                    avg_order_value=aov
                )
                db.add(dr)

                # Repeat vs new customer ratio — 60/40
                repeat_count = int(order_count * 0.60)
                new_count    = order_count - repeat_count

                pool = customer_pools[restaurant.id]

                # Repeat customer orders
                for _ in range(repeat_count):
                    customer = random.choice(pool)
                    order = Order(
                        restaurant_id=restaurant.id,
                        total_amount=round(aov * random.uniform(0.70, 1.30), 2),
                        status=random.choices(
                            ["completed", "cancelled", "refunded"],
                            weights=[93, 4, 3]
                        )[0],
                        order_type=random.choices(
                            ["dine_in", "delivery", "takeaway"],
                            weights=[50, 35, 15]
                        )[0],
                        created_at=random_datetime_on(current)
                    )
                    db.add(order)
                    total_orders_created += 1

                # New customer orders
                for _ in range(new_count):
                    order = Order(
                        restaurant_id=restaurant.id,
                        total_amount=round(aov * random.uniform(0.60, 1.20), 2),
                        status=random.choices(
                            ["completed", "cancelled", "refunded"],
                            weights=[88, 8, 4]
                        )[0],
                        order_type=random.choices(
                            ["dine_in", "delivery", "takeaway"],
                            weights=[40, 45, 15]
                        )[0],
                        created_at=random_datetime_on(current)
                    )
                    db.add(order)
                    total_orders_created += 1

            db.commit()
            current += timedelta(days=1)

        print(f"Created daily revenue and {total_orders_created} orders")

        # ── Sample past campaigns ──
        for restaurant, profile in restaurant_objects:
            for _ in range(random.randint(4, 7)):
                sent_date = random_datetime_on(random_date(START_DATE, END_DATE))
                campaign = Campaign(
                    restaurant_id=restaurant.id,
                    subject=random.choice([
                        "We miss you! Here's 20% off your next visit",
                        "Holiday special — book your table now",
                        "Exclusive weekend offer for valued customers",
                        "Stock up before the holiday rush",
                        "Limited time offer — this weekend only",
                        "Thank you for being a loyal customer",
                    ]),
                    body="Sample campaign — LLM generated content will replace this.",
                    trigger_type=random.choice(["lull_period", "holiday", "pre_stock"]),
                    status="sent",
                    created_at=sent_date,
                    sent_at=sent_date
                )
                db.add(campaign)
        db.commit()
        print("Created sample past campaigns")

        # ── Summary ──
        print("\nSeed completed successfully")
        print(f"  Restaurants : {len(restaurant_objects)}")
        print(f"  Customers   : {len(all_customers)}")
        print(f"  Orders      : {total_orders_created}")
        print(f"  Date range  : {START_DATE} → {END_DATE}")
        print(f"\n  Lull periods built in:")
        for lull in LULL_PERIODS:
            print(f"    {lull['name']}: {lull['core_start']} → {lull['core_end']}")
        print(f"\n  Peak periods built in:")
        for peak in PEAK_PERIODS:
            print(f"    {peak['name']}: {peak['start']} → {peak['end']}")
        print(f"\n  Recovery periods built in:")
        for rec in RECOVERY_PERIODS:
            print(f"    {rec['start']} → {rec['end']} (multiplier: {rec['multiplier']})")

    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()