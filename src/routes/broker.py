from flask import Blueprint, request, jsonify
from src.models.user import db, User, BrokerAccount
from src.services.tradovate_service import TradovateService
from src.services.topstep_service import TopStepService
from src.utils.encryption import encrypt_data, decrypt_data
from datetime import datetime
import json

broker_bp = Blueprint('broker', __name__)

@broker_bp.route('/connect', methods=['POST'])
def connect_broker():
    """Connect a new broker account"""
    try:
        # For now, we'll use a simple user lookup since JWT is not implemented
        # In production, you'd want proper authentication
        data = request.get_json()
        
        # Get user_id from request or use default for demo
        user_id = data.get('user_id', 1)  # Default to user 1 for demo
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate required fields
        required_fields = ['broker_type', 'credentials']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        broker_type = data['broker_type'].lower()
        credentials = data['credentials']
        
        # Validate broker type
        if broker_type not in ['tradovate', 'topstep']:
            return jsonify({'error': 'Invalid broker type. Must be "tradovate" or "topstep"'}), 400
        
        # For demo purposes, we'll skip the actual API connection test
        # In production, you'd test the connection here
        account_info = {
            'account_id': f'{broker_type}_demo_account',
            'account_name': f'{broker_type.title()} Demo Account',
            'balance': 10000.00,
            'equity': 10000.00,
            'margin_used': 0.00,
            'margin_available': 10000.00
        }
        
        # Encrypt credentials before storing
        encrypted_credentials = encrypt_data(json.dumps(credentials))
        
        # Create broker account record
        broker_account = BrokerAccount(
            user_id=user.id,
            broker_type=broker_type,
            broker_account_id=account_info.get('account_id', ''),
            api_credentials=encrypted_credentials,
            account_name=account_info.get('account_name', ''),
            balance=account_info.get('balance', 0),
            equity=account_info.get('equity', 0),
            margin_used=account_info.get('margin_used', 0),
            margin_available=account_info.get('margin_available', 0),
            last_sync=datetime.utcnow()
        )
        
        db.session.add(broker_account)
        db.session.commit()
        
        return jsonify({
            'message': f'{broker_type.title()} account connected successfully',
            'broker_account': broker_account.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to connect broker account', 'details': str(e)}), 500

@broker_bp.route('/accounts', methods=['GET'])
def get_broker_accounts():
    """Get all broker accounts for the current user"""
    try:
        # For demo, get user_id from query params or use default
        user_id = request.args.get('user_id', 1, type=int)
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_accounts = BrokerAccount.query.filter_by(user_id=user.id).all()
        
        return jsonify({
            'broker_accounts': [account.to_dict() for account in broker_accounts]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve broker accounts', 'details': str(e)}), 500
