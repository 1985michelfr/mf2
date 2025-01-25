from app import db
from datetime import datetime

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'invest', 'withdraw', 'update', 'amortize', 'increase', 'debt'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    confirmed = db.Column(db.Boolean, default=False)
