from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Heygray001,,@localhost/budget_db'
app.config['SQLALCHEMY_TRACK_MONDIFICATIONS'] = False

db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class BudgetGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True, nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), default="Student")
    income_target = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(5), default="$")

with app.app_context():
    db.create_all()

    if not Transaction.query.first():
        sample_tx = Transaction(title="Sample Income", amount=1500, type="Income", category="Paycheck")
        sample_goal = BudgetGoal(category="Food", monthly_limit=400)
        sample_settings = Settings(id=1, student_name="Grayson", income_target=2000, currency="$")
        
        db.session.add_all([sample_tx, sample_goal, sample_settings])
        db.session.commit()
        print("Database seeded with sample data!")

@app.route('/')
def index():
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year
    
    txs = Transaction.query.filter(
        db.extract('month', Transaction.date) == current_month,
        db.extract('year', Transaction.date) == current_year
    ).all()
    
    total_income = sum(t.amount for t in txs if t.type == 'Income')
    total_expenses = sum(t.amount for t in txs if t.type == 'Expense')
    net_balance = total_income - total_expenses
    
    return render_template('index.html', 
                           income=total_income, 
                           expenses=total_expenses, 
                           balance=net_balance)

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if request.method == 'POST':
        new_tx = Transaction(
            title=request.form['title'],
            amount=float(request.form['amount']),
            type=request.form['type'],
            category=request.form['category']
        )
        db.session.add(new_tx)
        db.session.commit()
        return redirect(url_for('transactions'))

    all_transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template('transactions.html')

@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if request.method == 'POST':
        category = request.form['category']
        limit = float(request.form['monthly_limit'])
        
        existing_goal = BudgetGoal.query.filter_by(category=category).first()
        
        if existing_goal:
            existing_goal.monthly_limit = limit
        else:
            new_goal = BudgetGoal(category=category, monthly_limit=limit)
            db.session.add(new_goal)
            
        db.session.commit()
        return redirect(url_for('goals'))

    all_goals = BudgetGoal.query.all()
    return render_template('goals.html', goals=all_goals)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    settings = Settings.query.get(1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.student_name = request.form['student_name']
        settings.income_target = float(request.form['income_target'])
        settings.currency = request.form['currency']
        db.session.commit()
        return redirect(url_for('profile'))

    return render_template('profile.html', settings=settings)

if __name__ == '__main__':
    app.run(debug=True)