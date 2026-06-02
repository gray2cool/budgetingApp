from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json
import calendar

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Heygray001,,@localhost/budget_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class EventLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class BudgetGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), default="Student")
    income_target = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(5), default="$")

with app.app_context():
    db.create_all()
    if not db.session.execute(db.select(Transaction)).first():
        sample_settings = Settings(id=1, student_name="Grayson", income_target=2000, currency="$")
        sample_tx = Transaction(student_name="Grayson", title="Sample Income", amount=1500, type="INCOME", category="PAYCHECK")
        sample_goal = BudgetGoal(student_name="Grayson", category="FOOD", monthly_limit=400)
        
        db.session.add_all([sample_settings, sample_tx, sample_goal])

        sample_tx_event = EventLog(
            student_name="Grayson",
            event_type='TRANSACTION_CREATED',
            payload=json.dumps({
                "title": "Sample Income",
                "amount": 1500.0,
                "type": "INCOME",
                "category": "PAYCHECK",
                "date": datetime.now(timezone.utc).isoformat()
            })
        )
        sample_goal_event = EventLog(
            student_name="Grayson",
            event_type='BUDGET_GOAL_SET',
            payload=json.dumps({
                "category": "FOOD",
                "monthly_limit": 400.0
            })
        )
        sample_settings_event = EventLog(
            student_name="Grayson",
            event_type='SETTINGS_UPDATED',
            payload=json.dumps({
                "student_name": "Grayson",
                "income_target": 2000.0,
                "currency": "$"
            })
        )

        db.session.add_all([sample_tx_event, sample_goal_event, sample_settings_event])
        db.session.commit()
        print("Database seeded with sample data!")

def get_current_user():
    settings = db.session.get(Settings, 1)
    return settings.student_name if settings else "Student"

@app.route('/')
def index():
    current_user = get_current_user()
    now = datetime.now(timezone.utc)
    
    txs = db.session.query(Transaction).filter(
        Transaction.student_name == current_user,
        db.extract('month', Transaction.date) == now.month,
        db.extract('year', Transaction.date) == now.year
    ).all()
    
    total_income = sum(t.amount for t in txs if t.type == 'INCOME')
    total_expenses = sum(t.amount for t in txs if t.type == 'EXPENSE')
    net_balance = total_income - total_expenses
    
    return render_template('index.html', 
                           income=total_income, 
                           expenses=total_expenses, 
                           balance=net_balance)

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    current_user = get_current_user()
    
    if request.method == 'POST':
        title = request.form['title']
        amount = float(request.form['amount'])
        type_ = request.form['type'].upper()
        category = request.form['category'].upper()
        tx_date = datetime.now(timezone.utc)

        event_payload = {
            "title": title,
            "amount": amount,
            "type": type_,
            "category": category,
            "date": tx_date.isoformat()
        }
        event = EventLog(
            student_name=current_user,
            event_type='TRANSACTION_CREATED',
            payload=json.dumps(event_payload)
        )
        db.session.add(event)

        new_tx = Transaction(
            student_name=current_user,
            title=title,
            amount=amount,
            type=type_,
            category=category,
            date=tx_date
        )
        db.session.add(new_tx)

        db.session.commit()
        return redirect(url_for('transactions'))

    all_transactions = db.session.query(Transaction).filter_by(student_name=current_user).order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=all_transactions)

# Added missing deletion route
@app.route('/delete_tx/<int:id>', methods=['POST'])
def delete_tx(id):
    tx = db.session.get(Transaction, id)
    if tx:
        db.session.delete(tx)
        db.session.commit()
        return '', 200
    return 'Not Found', 404

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    current_user = get_current_user()
    
    if request.method == 'POST':
        category = request.form['category'].upper()
        limit = float(request.form['monthly_limit'])

        goal_payload = {
            "category": category,
            "monthly_limit": limit
        }
        event = EventLog(
            student_name=current_user,
            event_type='BUDGET_GOAL_SET',
            payload=json.dumps(goal_payload)
        )
        db.session.add(event)
        
        existing_goal = db.session.query(BudgetGoal).filter_by(student_name=current_user, category=category).first()
        if existing_goal:
            existing_goal.monthly_limit = limit
        else:
            new_goal = BudgetGoal(student_name=current_user, category=category, monthly_limit=limit)
            db.session.add(new_goal)
            
        db.session.commit()
        return redirect(url_for('goals'))

    all_goals = db.session.query(BudgetGoal).filter_by(student_name=current_user).all()
    return render_template('goals.html', goals=all_goals)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    settings = db.session.get(Settings, 1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        student_name = request.form['student_name']
        income_target = float(request.form['income_target'])
        currency = request.form['currency']

        settings_payload = {
            "student_name": student_name,
            "income_target": income_target,
            "currency": currency
        }
        event = EventLog(
            student_name=student_name,
            event_type='SETTINGS_UPDATED',
            payload=json.dumps(settings_payload)
        )
        db.session.add(event)

        settings.student_name = student_name
        settings.income_target = income_target
        settings.currency = currency
        db.session.commit()
        return redirect(url_for('profile'))

    return render_template('profile.html', settings=settings)

@app.route('/api/analytics/velocity', methods=['GET'])
def api_analytics_velocity():
    current_user = get_current_user()
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month
    
    days_elapsed = max(now.day, 1)
    _, total_days_in_month = calendar.monthrange(current_year, current_month)
    
    expense_events = db.session.query(EventLog).filter_by(student_name=current_user, event_type='TRANSACTION_CREATED').all()
    
    monthly_category_spending = {}
    for event in expense_events:
        try:
            payload = json.loads(event.payload)
            if payload.get('type', '').upper() == 'EXPENSE':
                tx_date_str = payload.get('date')
                if tx_date_str:
                    tx_date = datetime.fromisoformat(tx_date_str.replace('Z', '+00:00'))
                else:
                    tx_date = event.timestamp
                
                if tx_date.year == current_year and tx_date.month == current_month:
                    category = payload.get('category', 'MISCELLANEOUS').upper()
                    amount = float(payload.get('amount', 0.0))
                    monthly_category_spending[category] = monthly_category_spending.get(category, 0.0) + amount
        except (ValueError, TypeError, json.JSONDecodeError):
            continue

    goal_events = db.session.query(EventLog).filter_by(student_name=current_user, event_type='BUDGET_GOAL_SET').order_by(EventLog.timestamp.asc()).all()
    
    active_budget_goals = {}
    for event in goal_events:
        try:
            payload = json.loads(event.payload)
            category = payload.get('category', '').upper()
            limit = float(payload.get('monthly_limit', 0.0))
            if category:
                active_budget_goals[category] = limit
        except (ValueError, TypeError, json.JSONDecodeError):
            continue

    all_stored_goals = db.session.query(BudgetGoal).filter_by(student_name=current_user).all()
    for goal in all_stored_goals:
        upper_cat = goal.category.upper()
        if upper_cat not in active_budget_goals:
            active_budget_goals[upper_cat] = goal.monthly_limit

    velocity_analytics_response = []
    
    for category, monthly_limit in active_budget_goals.items():
        total_spent = monthly_category_spending.get(category, 0.0)
        daily_average = total_spent / days_elapsed
        projected_spend = daily_average * total_days_in_month
        
        projected_percent = (projected_spend / monthly_limit * 100.0) if monthly_limit > 0 else 0.0
        
        if projected_percent < 80.0:
            status = "On Track"
            status_color = "green"
        elif projected_percent <= 100.0:
            status = "Watch Out"
            status_color = "yellow"
        else:
            status = "Over Budget"
            status_color = "red"
            
        velocity_analytics_response.append({
            "category": category,
            "monthly_limit": round(monthly_limit, 2),
            "total_spent": round(total_spent, 2),
            "daily_average": round(daily_average, 2),
            "projected_spend": round(projected_spend, 2),
            "percentage": round(projected_percent, 1),
            "status": status,
            "status_color": status_color
        })
        
    return jsonify({"categories": velocity_analytics_response})

if __name__ == '__main__':
    app.run(debug=True)