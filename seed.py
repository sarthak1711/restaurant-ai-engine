import pandas as pd
import random
from datetime import datetime, date, timedelta
from models import (
    SessionLocal, BusinessProfile, Category,
    Item, Customer, Order, OrderLineItem
)

# ── Constants ─────────────────────────────────────────────────────────────────

CATEGORIES = ["Starter", "Main Course", "Side Dish", "Dessert", "Beverages"]

# Course mapping: your category name → dataset Course value
COURSE_MAP = {
    "Starter":     "Appetizer",
    "Main Course": "Main Course",
    "Side Dish":   "Side Dish",
    "Dessert":     "Dessert",
}

# Price ranges by country and category
# Format: (min, max)
PRICE_RANGES = {
    "IN": {
        "Starter":     (100, 250),
        "Main Course": (200, 400),
        "Side Dish":   (150, 300),
        "Dessert":     (80,  150),
        "Beverages":   (50,  150),
    },
    "AU": {
        "Starter":     (10,  15),
        "Main Course": (12,  20),
        "Side Dish":   (7,   12),
        "Dessert":     (5,   7),
        "Beverages":   (5,   7),
    },
    "CA": {
        "Starter":     (10,  15),
        "Main Course": (12,  20),
        "Side Dish":   (7,   12),
        "Dessert":     (5,   7),
        "Beverages":   (5,   7),
    },
}

# Standard beverages hardcoded for all restaurants
# These are realistic for each country
BEVERAGES = {
    "IN": [
        "Masala Chai", "Filter Coffee", "Lassi", "Nimbu Pani",
        "Mango Shake", "Buttermilk", "Cold Coffee"
    ],
    "AU": [
        "Flat White", "Long Black", "Fresh Orange Juice",
        "Sparkling Water", "Lemonade", "Iced Tea", "Smoothie"
    ],
    "CA": [
        "Drip Coffee", "Cappuccino", "Fresh Apple Juice",
        "Sparkling Water", "Lemonade", "Iced Tea", "Milkshake"
    ],
}

# Fully hardcoded items for QSR Burger restaurant
# Organized by category name → list of item names
BURGER_ITEMS = {
    "Starter": [
        "Crispy Chicken Wings", "Onion Rings", "Mozzarella Sticks",
        "Loaded Nachos", "Chicken Nuggets", "Potato Wedges",
        "Coleslaw Cup"
    ],
    "Main Course": [
        "Classic Beef Burger", "Crispy Chicken Burger", "Double Smash Burger",
        "BBQ Bacon Burger", "Veggie Burger", "Grilled Chicken Burger",
        "Mushroom Swiss Burger", "Spicy Jalapeno Burger", "Fish Burger"
    ],
    "Side Dish": [
        "Classic Fries", "Cheese Fries", "Sweet Potato Fries",
        "Peri Peri Fries", "Mac and Cheese", "Garden Salad",
        "Coleslaw Bowl"
    ],
    "Dessert": [
        "Chocolate Brownie", "Vanilla Soft Serve", "Oreo McFlurry Style",
        "Apple Pie", "Chocolate Milkshake Dessert", "Strawberry Sundae"
    ],
}

# Restaurant definitions
# cuisine_filter is the exact value to match against the CSV's Cuisine column
# None means fully hardcoded (no CSV lookup)
RESTAURANTS = [
    {
        "name":           "Spice Route",
        "cuisine_filter": "North Indian Recipes",
        "country":        "IN",
        "state":          "Delhi",
        "suburb":         "Connaught Place",
        "address":        "12 Janpath Road",
        "zip_code":       "110001",
        "phone_no":       "+91-9812345678",
        "email":          "spiceroute@example.com",
    },
    {
        "name":           "Dosa House",
        "cuisine_filter": "South Indian Recipes",
        "country":        "AU",
        "state":          "New South Wales",
        "suburb":         "Parramatta",
        "address":        "45 Church Street",
        "zip_code":       "2150",
        "phone_no":       "+61-412345678",
        "email":          "dosahouse@example.com",
    },
    {
        "name":           "Dragon Wok",
        "cuisine_filter": "Chinese",
        "country":        "IN",
        "state":          "Maharashtra",
        "suburb":         "Bandra",
        "address":        "7 Hill Road",
        "zip_code":       "400050",
        "phone_no":       "+91-9823456789",
        "email":          "dragonwok@example.com",
    },
    {
        "name":           "Coconut Grove",
        "cuisine_filter": "South Indian Recipes",
        "country":        "IN",
        "state":          "Karnataka",
        "suburb":         "Indiranagar",
        "address":        "22 100 Feet Road",
        "zip_code":       "560038",
        "phone_no":       "+91-9834567890",
        "email":          "coconutgrove@example.com",
    },
    {
        "name":           "Punjab Da Dhaba",
        "cuisine_filter": "Punjabi",
        "country":        "CA",
        "state":          "Ontario",
        "suburb":         "Brampton",
        "address":        "88 Main Street North",
        "zip_code":       "L6V1N8",
        "phone_no":       "+1-4165678901",
        "email":          "punjabdhaba@example.com",
    },
    {
        "name":           "The Continental Table",
        "cuisine_filter": "Continental",
        "country":        "AU",
        "state":          "Victoria",
        "suburb":         "Fitzroy",
        "address":        "31 Brunswick Street",
        "zip_code":       "3065",
        "phone_no":       "+61-423456789",
        "email":          "continentaltable@example.com",
    },
    {
        "name":           "BurgerBox",
        "cuisine_filter": None,
        "country":        "CA",
        "state":          "British Columbia",
        "suburb":         "Vancouver",
        "address":        "101 Robson Street",
        "zip_code":       "V6B1C8",
        "phone_no":       "+1-6045678901",
        "email":          "burgerbox@example.com",
    },
    {
        "name":           "Curry Leaf",
        "cuisine_filter": "Indian",
        "country":        "IN",
        "state":          "Uttar Pradesh",
        "suburb":         "Hazratganj",
        "address":        "5 MG Road",
        "zip_code":       "226001",
        "phone_no":       "+91-9856789012",
        "email":          "curryleaf@example.com",
    },
]


# ── Helper functions ──────────────────────────────────────────────────────────

def random_price(country, category):
    """Return a realistic random price for a given country and category."""
    low, high = PRICE_RANGES[country][category]
    return round(random.uniform(low, high), 2)


def get_items_from_csv(df, cuisine_filter, course_name, n_items=8):
    """
    Filter the dataset by cuisine and course, return n random item names.
    Falls back to a broader filter if not enough items found.
    """
    course_value = COURSE_MAP.get(course_name)
    if not course_value:
        return []

    filtered = df[
        (df["Cuisine"] == cuisine_filter) &
        (df["Course"]  == course_value)
    ]

    # If less than n_items found, relax the cuisine filter
    if len(filtered) < n_items:
        filtered = df[df["Course"] == course_value]

    if len(filtered) == 0:
        return []

    sample_size = min(n_items, len(filtered))
    sampled = filtered.sample(n=sample_size)

    # Use TranslatedRecipeName if available, else fall back to RecipeName
    names = []
    for _, row in sampled.iterrows():
        name = row.get("TranslatedRecipeName") or row.get("RecipeName")
        if isinstance(name, str) and name.strip():
            names.append(name.strip()[:100])  # enforce column max length

    return names


# ── Seed functions ────────────────────────────────────────────────────────────

def seed_businesses(db):
    """
    Create all 8 BusinessProfile records.
    Returns a list of created BusinessProfile objects with their DB-assigned IDs.
    """
    created = []
    for r in RESTAURANTS:
        business = BusinessProfile(
            name=r["name"],
            email=r["email"],
            phone_no=r["phone_no"],
            address=r["address"],
            suburb=r["suburb"],
            state=r["state"],
            country=r["country"],
            zip_code=r["zip_code"],
        )
        db.add(business)
        created.append((business, r))

    db.commit()
    print(f"Created {len(created)} business profiles")
    return created


def seed_categories_and_items(db, businesses, df):
    """
    For each business, create 5 categories and seed items into each.
    Indian food dataset is used where cuisine_filter is set.
    Hardcoded items are used for BurgerBox.
    Beverages are always hardcoded.
    """
    total_categories = 0
    total_items = 0

    for business, restaurant_config in businesses:
        cuisine_filter = restaurant_config["cuisine_filter"]
        country        = restaurant_config["country"]

        for category_name in CATEGORIES:
            # Create the category
            category = Category(
                business_id=business.id,
                category_name=category_name,
                active=True,
            )
            db.add(category)
            db.flush()  # flush to get category.id before creating items
            total_categories += 1

            # Determine item names for this category
            if category_name == "Beverages":
                # Always hardcoded, same for all restaurants per country
                item_names = BEVERAGES[country]

            elif cuisine_filter is None:
                # BurgerBox — fully hardcoded
                item_names = BURGER_ITEMS.get(category_name, [])

            else:
                # Indian food dataset
                item_names = get_items_from_csv(df, cuisine_filter, category_name)

            # Create items
            for item_name in item_names:
                item = Item(
                    business_id=business.id,
                    category_id=category.id,
                    item_name=item_name,
                    price=random_price(country, category_name),
                    tax=5.0 if country == "IN" else 10.0,
                    active=True,
                )
                db.add(item)
                total_items += 1

        db.commit()

    print(f"Created {total_categories} categories and {total_items} items")


def seed_customers(db, businesses):
    """
    Create 60-100 customers per restaurant.
    Returns dict of business_id -> list of Customer objects.
    """
    first_names = [
        "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohan",
        "Meera", "James", "Sarah", "Liam", "Emma", "Noah", "Olivia",
        "Tom", "Lucy", "Arjun", "Kavya", "Singh", "Patel"
    ]
    last_names = [
        "Sharma", "Patel", "Singh", "Smith", "Brown", "Wilson", "Johnson",
        "Williams", "Jones", "Taylor", "Gupta", "Kumar", "Verma", "Chen",
        "Davis", "Miller", "Martin", "Lee", "Khan", "Mehta"
    ]
    segments = ["vip", "regular", "regular", "regular", "at_risk", "churned"]

    customer_map = {}
    total_customers = 0

    for business, _ in businesses:
        customers = []
        num_customers = random.randint(60, 100)

        for _ in range(num_customers):
            first = random.choice(first_names)
            last  = random.choice(last_names)
            num   = random.randint(1, 999)

            customer = Customer(
                business_id=business.id,
                customer_name=f"{first} {last}",
                customer_email=f"{first.lower()}.{last.lower()}{num}@example.com",
                segment=random.choice(segments),
            )
            db.add(customer)
            customers.append(customer)
            total_customers += 1

        db.commit()
        customer_map[business.id] = customers

    print(f"Created {total_customers} customers")
    return customer_map


def seed_orders(db, businesses, customer_map):
    """
    Create realistic orders with day-of-week patterns, lull periods,
    and peak periods. Each order gets 1-4 order line items from
    that restaurant's actual menu.
    """

    # Lull periods — revenue should visibly drop here
    LULL_PERIODS = [
        (date(2024, 12, 2),  date(2024, 12, 10)),
        (date(2025, 1, 15),  date(2025, 1, 25)),
        (date(2025, 3, 3),   date(2025, 3, 12)),
    ]

    # Peak periods — revenue spikes here
    PEAK_PERIODS = [
        (date(2024, 12, 20), date(2024, 12, 31)),
        (date(2025, 2, 13),  date(2025, 2, 15)),
        (date(2025, 4, 18),  date(2025, 4, 21)),
    ]

    # Day of week multipliers — Mon=0, Sun=6
    DOW_MULTIPLIER = {
        0: 0.70,  # Monday
        1: 0.75,  # Tuesday
        2: 0.82,  # Wednesday
        3: 0.88,  # Thursday
        4: 1.20,  # Friday
        5: 1.40,  # Saturday
        6: 1.25,  # Sunday
    }

    def is_lull(d):
        return any(start <= d <= end for start, end in LULL_PERIODS)

    def is_peak(d):
        return any(start <= d <= end for start, end in PEAK_PERIODS)

    def orders_for_day(d, base_orders):
        multiplier = DOW_MULTIPLIER[d.weekday()]
        if is_peak(d):
            multiplier *= 1.8
        elif is_lull(d):
            multiplier *= 0.35
        noise = random.uniform(0.92, 1.08)
        return max(5, int(base_orders * multiplier * noise))

    START_DATE = date(2024, 11, 1)
    END_DATE   = date(2025, 5, 1)

    total_orders = 0
    total_line_items = 0

    for business, config in businesses:
        customers = customer_map[business.id]
        base_orders = random.randint(35, 65)

        # Get all active items for this business
        from sqlalchemy import text
        items = db.execute(
            text("SELECT id, price, tax,item_name  FROM items WHERE business_id = :bid AND active = true"),
            {"bid": business.id}
        ).fetchall()

        if not items:
            print(f"  Warning: no items found for {business.name}, skipping orders")
            continue

        current = START_DATE
        while current <= END_DATE:
            num_orders = orders_for_day(current, base_orders)

            for _ in range(num_orders):
                customer = random.choice(customers)

                # Random order time — lunch or dinner peaks
                hour   = random.choices([12, 13, 14, 19, 20, 21, 22], weights=[15, 20, 10, 20, 20, 10, 5])[0]
                minute = random.randint(0, 59)
                order_datetime = datetime(current.year, current.month, current.day, hour, minute)

                order = Order(
                    business_id=business.id,
                    customer_id=customer.id,
                    order_date=order_datetime,
                    status=random.choices(["paid", "pending"], weights=[95, 5])[0],
                    payment_mode=random.choices(["card", "cash"], weights=[70, 30])[0],
                    discount=0.0,
                    tax=0.0,
                    total=0.0,
                )
                db.add(order)
                db.flush()

                # Add 1-4 line items per order
                selected_items = random.sample(items, k=min(random.randint(1, 4), len(items)))
                order_total = 0.0
                order_tax   = 0.0

                for item_row in selected_items:
                    item_price    = float(item_row.price)
                    item_tax_rate = float(item_row.tax)
                    item_tax_amt  = round(item_price * item_tax_rate / 100, 2)
                    item_name = item_row.item_name

                    line_item = OrderLineItem(
                        order_id=order.id,
                        item_id=item_row.id,
                        item_name=item_name,       # will fill below
                        item_price=item_price,
                        item_discount=0.0,
                        item_tax=item_tax_amt,
                    )
                    db.add(line_item)

                    order_total += item_price
                    order_tax   += item_tax_amt
                    total_line_items += 1

                # Update order totals
                order.total = round(order_total, 2)
                order.tax   = round(order_tax, 2)
                total_orders += 1

            current += timedelta(days=1)

        db.commit()
        print(f"  {business.name}: {total_orders} orders so far")

    print(f"Created {total_orders} orders and {total_line_items} order line items")


# ── Main ──────────────────────────────────────────────────────────────────────

def seed():
    print("Loading Indian food dataset...")
    df = pd.read_csv("indian_food.csv")
    print(f"Dataset loaded: {len(df)} recipes")

    db = SessionLocal()

    try:
        # Clear existing data in reverse dependency order
        print("\nClearing existing data...")
        db.query(OrderLineItem).delete()
        db.query(Order).delete()
        db.query(Customer).delete()
        db.query(Item).delete()
        db.query(Category).delete()
        db.query(BusinessProfile).delete()
        db.commit()
        print("Cleared")

        print("\nSeeding businesses...")
        businesses = seed_businesses(db)

        print("\nSeeding categories and items...")
        seed_categories_and_items(db, businesses, df)

        print("\nSeeding customers...")
        customer_map = seed_customers(db, businesses)

        print("\nSeeding orders and line items...")
        seed_orders(db, businesses, customer_map)

        print("\nSeed completed successfully")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()