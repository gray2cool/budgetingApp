from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json
import calendar

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Heygray001,,@localhost/budget_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super_secret_budget_key'

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

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    income_target = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(5), default="$")

with app.app_context():
    db.create_all()
    if not db.session.execute(db.select(User)).first():
        sample_user = User(student_name="Grayson", password="password123", income_target=2000, currency="$")
        sample_tx = Transaction(student_name="Grayson", title="Sample Income", amount=1500, type="INCOME", category="PAYCHECK")
        sample_goal = BudgetGoal(student_name="Grayson", category="FOOD", monthly_limit=400)
        
        db.session.add_all([sample_user, sample_tx, sample_goal])
        db.session.commit()
        print("Database seeded with sample data!")

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'student_name' not in session:
        return redirect(url_for('login'))

def get_current_user():
    return session.get('student_name')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        student_name = request.form['student_name']
        password = request.form['password']
        income_target = float(request.form['income_target'])
        currency = request.form['currency']

        user = db.session.query(User).filter_by(student_name=student_name).first()
        
        if user:
            if user.password == password:
                user.income_target = income_target
                user.currency = currency
                session['student_name'] = student_name
                db.session.commit()
                return redirect(url_for('index'))
            else:
                error = "Incorrect password for this user."
        else:
            new_user = User(
                student_name=student_name, 
                password=password, 
                income_target=income_target, 
                currency=currency
            )
            db.session.add(new_user)
            session['student_name'] = student_name
            db.session.commit()
            return redirect(url_for('index'))

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('student_name', None)
    return redirect(url_for('login'))

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
            "title": title, "amount": amount, "type": type_, 
            "category": category, "date": tx_date.isoformat()
        }
        event = EventLog(student_name=current_user, event_type='TRANSACTION_CREATED', payload=json.dumps(event_payload))
        new_tx = Transaction(student_name=current_user, title=title, amount=amount, type=type_, category=category, date=tx_date)
        
        db.session.add_all([event, new_tx])
        db.session.commit()
        return redirect(url_for('transactions'))

    all_transactions = db.session.query(Transaction).filter_by(student_name=current_user).order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=all_transactions)

@app.route('/delete_tx/<int:id>', methods=['POST'])
def delete_tx(id):
    current_user = get_current_user()
    tx = db.session.get(Transaction, id)
    if tx and tx.student_name == current_user:
        event_payload = {
            "title": tx.title,
            "amount": tx.amount,
            "type": tx.type,
            "category": tx.category,
            "date": tx.date.isoformat()
        }
        deletion_event = EventLog(
            student_name=current_user,
            event_type='TRANSACTION_DELETED',
            payload=json.dumps(event_payload)
        )
        db.session.add(deletion_event)
        db.session.delete(tx)
        db.session.commit()
        return '', 200
        
    return 'Not Found or Unauthorized', 404

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    current_user = get_current_user()
    if request.method == 'POST':
        category = request.form['category'].upper()
        limit = float(request.form['monthly_limit'])

        event = EventLog(student_name=current_user, event_type='BUDGET_GOAL_SET', payload=json.dumps({"category": category, "monthly_limit": limit}))
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

@app.route('/api/analytics/velocity', methods=['GET'])
def api_analytics_velocity():
    current_user = get_current_user()
    now = datetime.now(timezone.utc)
    days_elapsed = max(now.day, 1)
    _, total_days_in_month = calendar.monthrange(now.year, now.month)
    
    expense_events = db.session.query(EventLog).filter(
        EventLog.student_name == current_user,
        EventLog.event_type.in_(['TRANSACTION_CREATED', 'TRANSACTION_DELETED'])
    ).all()
    
    monthly_category_spending = {}
    total_all_expenses = 0.0 
    
    for event in expense_events:
        try:
            payload = json.loads(event.payload)
            if payload.get('type', '').upper() == 'EXPENSE':
                tx_date_str = payload.get('date')
                tx_date = datetime.fromisoformat(tx_date_str.replace('Z', '+00:00')) if tx_date_str else event.timestamp
                
                if tx_date.year == now.year and tx_date.month == now.month:
                    category = payload.get('category', 'MISCELLANEOUS').upper()
                    amount = float(payload.get('amount', 0.0))
                    
                    if event.event_type == 'TRANSACTION_CREATED':
                        monthly_category_spending[category] = monthly_category_spending.get(category, 0.0) + amount
                        total_all_expenses += amount
                    elif event.event_type == 'TRANSACTION_DELETED':
                        monthly_category_spending[category] = monthly_category_spending.get(category, 0.0) - amount
                        total_all_expenses -= amount
                        
        except (ValueError, TypeError, json.JSONDecodeError):
            continue

    user = db.session.query(User).filter_by(student_name=current_user).first()
    income_target = user.income_target if user else 0.0

    active_budget_goals = {}
    all_stored_goals = db.session.query(BudgetGoal).filter_by(student_name=current_user).all()
    for goal in all_stored_goals:
        active_budget_goals[goal.category.upper()] = goal.monthly_limit

    velocity_analytics_response = []
    
    total_all_expenses = max(0, total_all_expenses)
    
    daily_avg_all = total_all_expenses / days_elapsed
    proj_all = daily_avg_all * total_days_in_month
    perc_all = (proj_all / income_target * 100.0) if income_target > 0 else 0.0
    
    if perc_all < 80.0:
        status_all, color_all = "On Track", "green"
    elif perc_all <= 100.0:
        status_all, color_all = "Watch Out", "yellow"
    else:
        status_all, color_all = "Over Budget", "red"

    velocity_analytics_response.append({
        "category": "INCOME TARGET",
        "monthly_limit": round(income_target, 2),
        "total_spent": round(total_all_expenses, 2),
        "daily_average": round(daily_avg_all, 2),
        "projected_spend": round(proj_all, 2),
        "percentage": round(perc_all, 1),
        "status": status_all,
        "status_color": color_all
    })

    for category, monthly_limit in active_budget_goals.items():
        total_spent = max(0, monthly_category_spending.get(category, 0.0))
        daily_average = total_spent / days_elapsed
        projected_spend = daily_average * total_days_in_month
        
        projected_percent = (projected_spend / monthly_limit * 100.0) if monthly_limit > 0 else 0.0
        
        if projected_percent < 80.0:
            status, status_color = "On Track", "green"
        elif projected_percent <= 100.0:
            status, status_color = "Watch Out", "yellow"
        else:
            status, status_color = "Over Budget", "red"
            
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