from flask import Blueprint, request, jsonify
from src.models.user import db, User, BrokerAccount, Position, Order, Trade
from datetime import datetime
import json

trading_bp = Blueprint('trading', __name__)

@trading_bp.route('/positions', methods=['GET'])
def get_positions():
    """Get all positions for the current user"""
    try:
        # For demo, get user_id from query params or use default
        user_id = request.args.get('user_id', 1, type=int)
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get positions for all user's broker accounts
        broker_accounts = BrokerAccount.query.filter_by(user_id=user.id).all()
        account_ids = [account.id for account in broker_accounts]
        
        positions = Position.query.filter(Position.broker_account_id.in_(account_ids)).all()
        
        return jsonify({
            'positions': [position.to_dict() for position in positions]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve positions', 'details': str(e)}), 500

@trading_bp.route('/orders', methods=['GET'])
def get_orders():
    """Get all orders for the current user"""
    try:
        # For demo, get user_id from query params or use default
        user_id = request.args.get('user_id', 1, type=int)
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get orders for all user's broker accounts
        broker_accounts = BrokerAccount.query.filter_by(user_id=user.id).all()
        account_ids = [account.id for account in broker_accounts]
        
        orders = Order.query.filter(Order.broker_account_id.in_(account_ids)).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve orders', 'details': str(e)}), 500

@trading_bp.route('/trades', methods=['GET'])
def get_trades():
    """Get all trades for the current user"""
    try:
        # For demo, get user_id from query params or use default
        user_id = request.args.get('user_id', 1, type=int)
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get trades for all user's broker accounts
        broker_accounts = BrokerAccount.query.filter_by(user_id=user.id).all()
        account_ids = [account.id for account in broker_accounts]
        
        trades = Trade.query.filter(Trade.broker_account_id.in_(account_ids)).all()
        
        return jsonify({
            'trades': [trade.to_dict() for trade in trades]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve trades', 'details': str(e)}), 500

