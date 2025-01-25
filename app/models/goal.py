from app import db
from datetime import datetime

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    target_date = db.Column(db.DateTime)
    target_value = db.Column(db.Float)
    target_percentage = db.Column(db.Float)
    current_value = db.Column(db.Float, default=0.0)
    initial_value = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='BRL')
    is_debt = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('goal.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    priority = db.Column(db.Integer, default=0)  # 0 é a menor prioridade
    
    children = db.relationship('Goal', 
                             backref=db.backref('parent', remote_side=[id]),
                             cascade='all, delete-orphan')
    
    transactions = db.relationship('Transaction',
                                 backref='goal',
                                 cascade='all, delete-orphan',
                                 lazy=True) 
    
    def __str__(self):
        return f"Title: {self.title} - Current Value: {self.current_value} Currency: {self.currency} - Target Value: {self.target_value} - Target Percentage: {self.target_percentage}% - Parent ID: {self.parent_id}"
    
    def __repr__(self):
        return f"<Goal {self.title}>"