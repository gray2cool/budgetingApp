import json
import random
import calendar
from datetime import datetime, timedelta, timezone
from budgetApp import app, db, User, Transaction, EventLog, BudgetGoal

def generate_bulk_data():
    print("Initializing bulk data generation for the year 2026...")
    
    # 1. Establish time boundaries for the current active month
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month
    days_in_month = calendar.monthrange(current_year, current_month)[1]
    
    # 2. Define our core data structures
    users_config = [
        {"name": "Grayson", "password": "password123", "income": 4500.0, "currency": "$"},
        {"name": "Alice", "password": "securepwd456", "income": 5200.0, "currency": "€"},
        {"name": "Bob", "password": "mypassword789", "income": 3800.0, "currency": "£"}
    ]
    
    categories = ["FOOD", "TRANSPORT", "UTILITIES", "ENTERTAINMENT", "BOOKS", "RENT", "HEALTH"]
    
    titles_expense = {
        "FOOD": ["Grocery Store Run", "Local Bistro Dinner", "Coffee Shop", "Fast Food Drive-Thru", "Snack Vending Machine"],
        "TRANSPORT": ["Gas Station Fill-up", "Subway Metro Pass", "Rideshare App", "Train Ticket", "Parking Fee"],
        "UTILITIES": ["Electric Bill", "Water Utility", "High-Speed Internet", "Mobile Phone Plan"],
        "ENTERTAINMENT": ["Movie Theater Ticket", "Streaming Service Subscription", "Concert Voucher", "Bowling Alley Night"],
        "BOOKS": ["University Textbook", "Notebook & Pens", "Online Research Article Access", "Fiction Novel"],
        "RENT": ["Monthly Apartment Rent", "Storage Unit Fee"],
        "HEALTH": ["Pharmacy Prescription", "Gym Membership Premium", "Dental Cleaning Copay"]
    }
    
    titles_income = ["Monthly Paycheck", "Freelance Coding Gig", "Part-time Shift Pay", "Stipend Award"]

    with app.app_context():
        # Clear out existing records to provide a completely sterile setup
        print("Clearing existing database records...")
        db.session.query(EventLog).delete()
        db.session.query(Transaction).delete()
        db.session.query(BudgetGoal).delete()
        db.session.query(User).delete()
        db.session.commit()

        # Seed Users
        print("Seeding authenticated user profiles...")
        for u_data in users_config:
            user = User(
                student_name=u_data["name"],
                password=u_data["password"],
                income_target=u_data["income"],
                currency=u_data["currency"]
            )
            db.session.add(user)
        db.session.commit()

        # Seed Budget Goals for each user
        print("Seeding budget limit targets...")
        for u_data in users_config:
            for cat in categories:
                # Randomize a realistic monthly limit between $150 and $600
                limit = round(random.uniform(150.0, 600.0), 2)
                goal = BudgetGoal(
                    student_name=u_data["name"],
                    category=cat,
                    monthly_limit=limit
                )
                db.session.add(goal)
                
                # Accompanying configuration log event
                goal_event = EventLog(
                    student_name=u_data["name"],
                    event_type="BUDGET_GOAL_SET",
                    payload=json.dumps({"category": cat, "monthly_limit": limit})
                )
                db.session.add(goal_event)
        db.session.commit()

        # Generate Transactions and creation events
        print("Simulating 1,000 baseline historical log records across users...")
        
        # Keep references to track created items so we can realistically simulate subsequent deletions
        created_transactions_by_user = {u["name"]: [] for u in users_config}
        
        # We generate records evenly distributed across our targeted profiles
        for i in range(500):
            for u_data in users_config:
                uname = u_data["name"]
                
                # Determine type weightings (roughly 85% expenses, 15% income to test limits)
                is_income = random.random() < 0.15
                tx_type = "INCOME" if is_income else "EXPENSE"
                
                if is_income:
                    cat = "PAYCHECK"
                    title = random.choice(titles_income)
                    amount = round(random.uniform(300.0, 1500.0), 2)
                else:
                    cat = random.choice(categories)
                    title = random.choice(titles_expense[cat])
                    amount = round(random.uniform(5.0, 120.0), 2)
                
                # Spread out timestamps realistically across the current month up to the current day
                random_day = random.randint(1, max(1, now.day))
                random_hour = random.randint(0, 23)
                random_minute = random.randint(0, 59)
                tx_date = datetime(current_year, current_month, random_day, random_hour, random_minute, tzinfo=timezone.utc)
                
                # Form transaction object
                new_tx = Transaction(
                    student_name=uname,
                    title=title,
                    amount=amount,
                    type=tx_type,
                    category=cat,
                    date=tx_date
                )
                db.session.add(new_tx)
                
                # Form matching log creation event
                creation_payload = {
                    "title": title,
                    "amount": amount,
                    "type": tx_type,
                    "category": cat,
                    "date": tx_date.isoformat()
                }
                creation_event = EventLog(
                    student_name=uname,
                    event_type="TRANSACTION_CREATED",
                    payload=json.dumps(creation_payload),
                    timestamp=tx_date
                )
                db.session.add(creation_event)
                
                # Queue up object definitions to allow processing deletions shortly after
                created_transactions_by_user[uname].append({
                    "tx_obj": new_tx,
                    "payload": creation_payload,
                    "date": tx_date
                })
                
        db.session.commit()

        # Simulate compensating transaction deletions
        print("Injecting randomized compensating TRANSACTION_DELETED events...")
        for u_data in users_config:
            uname = u_data["name"]
            user_pool = created_transactions_by_user[uname]
            
            # Select 25 random entries per user to mock delete
            deletion_sample = random.sample(user_pool, min(25, len(user_pool)))
            
            for item in deletion_sample:
                target_tx = item["tx_obj"]
                orig_payload = item["payload"]
                orig_date = item["date"]
                
                # The deletion event occurs slightly after the transaction was originally logged
                deletion_date = orig_date + timedelta(hours=random.randint(1, 24))
                if deletion_date > now:
                    deletion_date = now
                
                # Append the deletion compensating event to the immutable log
                deletion_event = EventLog(
                    student_name=uname,
                    event_type="TRANSACTION_DELETED",
                    payload=json.dumps(orig_payload),
                    timestamp=deletion_date
                )
                db.session.add(deletion_event)
                
                # Remove the actual row tracking standard visibility state
                db.session.delete(target_tx)
                
        db.session.commit()
        print("Successfully generated full-capacity database structure!")

if __name__ == "__main__":
    generate_bulk_data()