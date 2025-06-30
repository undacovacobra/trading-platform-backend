from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    
    # Relationships
    broker_accounts = db.relationship('BrokerAccount', backref='user', lazy=True, cascade='all, delete-orphan')
    trading_strategies = db.relationship('TradingStrategy', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set the password"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        """Check if the provided password matches the hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'email_verified': self.email_verified
        }


class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='sessions')

    def __repr__(self):
        return f'<UserSession {self.session_token[:10]}...>'


class BrokerAccount(db.Model):
    __tablename__ = 'broker_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    broker_type = db.Column(db.String(50), nullable=False)  # 'tradovate' or 'topstep'
    broker_account_id = db.Column(db.String(255), nullable=False)
    api_credentials = db.Column(db.Text, nullable=False)  # encrypted JSON
    account_name = db.Column(db.String(255))
    account_status = db.Column(db.String(50), default='active')
    balance = db.Column(db.Numeric(15, 2))
    equity = db.Column(db.Numeric(15, 2))
    margin_used = db.Column(db.Numeric(15, 2))
    margin_available = db.Column(db.Numeric(15, 2))
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trading_strategies = db.relationship('TradingStrategy', backref='broker_account', lazy=True)
    positions = db.relationship('Position', backref='broker_account', lazy=True)
    orders = db.relationship('Order', backref='broker_account', lazy=True)
    trades = db.relationship('Trade', backref='broker_account', lazy=True)

    def __repr__(self):
        return f'<BrokerAccount {self.broker_type}:{self.account_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'broker_type': self.broker_type,
            'broker_account_id': self.broker_account_id,
            'account_name': self.account_name,
            'account_status': self.account_status,
            'balance': float(self.balance) if self.balance else None,
            'equity': float(self.equity) if self.equity else None,
            'margin_used': float(self.margin_used) if self.margin_used else None,
            'margin_available': float(self.margin_available) if self.margin_available else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TradingStrategy(db.Model):
    __tablename__ = 'trading_strategies'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    broker_account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    strategy_name = db.Column(db.String(255), nullable=False)
    strategy_config = db.Column(db.Text, nullable=False)  # JSON configuration
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TradingStrategy {self.strategy_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'strategy_config': self.strategy_config,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Position(db.Model):
    __tablename__ = 'positions'
    
    id = db.Column(db.Integer, primary_key=True)
    broker_account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # 'long' or 'short'
    quantity = db.Column(db.Integer, nullable=False)
    entry_price = db.Column(db.Numeric(10, 4), nullable=False)
    current_price = db.Column(db.Numeric(10, 4))
    unrealized_pnl = db.Column(db.Numeric(15, 2))
    realized_pnl = db.Column(db.Numeric(15, 2))
    opened_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Position {self.symbol}:{self.side}:{self.quantity}>'

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': float(self.entry_price) if self.entry_price else None,
            'current_price': float(self.current_price) if self.current_price else None,
            'unrealized_pnl': float(self.unrealized_pnl) if self.unrealized_pnl else None,
            'realized_pnl': float(self.realized_pnl) if self.realized_pnl else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    broker_account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    broker_order_id = db.Column(db.String(255), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    order_type = db.Column(db.String(20), nullable=False)  # 'market', 'limit', 'stop'
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 4))
    stop_price = db.Column(db.Numeric(10, 4))
    status = db.Column(db.String(20), nullable=False)  # 'pending', 'filled', 'cancelled'
    filled_quantity = db.Column(db.Integer, default=0)
    filled_price = db.Column(db.Numeric(10, 4))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trades = db.relationship('Trade', backref='order', lazy=True)

    def __repr__(self):
        return f'<Order {self.symbol}:{self.side}:{self.quantity}@{self.price}>'

    def to_dict(self):
        return {
            'id': self.id,
            'broker_order_id': self.broker_order_id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': float(self.price) if self.price else None,
            'stop_price': float(self.stop_price) if self.stop_price else None,
            'status': self.status,
            'filled_quantity': self.filled_quantity,
            'filled_price': float(self.filled_price) if self.filled_price else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Trade(db.Model):
    __tablename__ = 'trades'
    
    id = db.Column(db.Integer, primary_key=True)
    broker_account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    side = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 4), nullable=False)
    commission = db.Column(db.Numeric(10, 2))
    executed_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Trade {self.symbol}:{self.side}:{self.quantity}@{self.price}>'

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': float(self.price),
            'commission': float(self.commission) if self.commission else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
