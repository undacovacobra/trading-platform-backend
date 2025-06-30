from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, BrokerAccount
from src.services.tradovate_service import TradovateService
from src.services.topstep_service import TopStepService
from src.utils.encryption import encrypt_data, decrypt_data
from datetime import datetime
import json

broker_bp = Blueprint('broker', __name__)

@broker_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect_broker():
    """Connect a new broker account"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
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
        
        # Validate credentials based on broker type
        if broker_type == 'tradovate':
            required_creds = ['username', 'password', 'api_key', 'secret']
            for cred in required_creds:
                if not credentials.get(cred):
                    return jsonify({'error': f'Tradovate {cred} is required'}), 400
            
            # Test Tradovate connection
            tradovate_service = TradovateService()
            connection_result = tradovate_service.test_connection(credentials)
            
            if not connection_result['success']:
                return jsonify({'error': 'Failed to connect to Tradovate', 'details': connection_result['error']}), 400
            
            account_info = connection_result['account_info']
            
        elif broker_type == 'topstep':
            required_creds = ['api_token']
            for cred in required_creds:
                if not credentials.get(cred):
                    return jsonify({'error': f'TopStep {cred} is required'}), 400
            
            # Test TopStep connection
            topstep_service = TopStepService()
            connection_result = topstep_service.test_connection(credentials)
            
            if not connection_result['success']:
                return jsonify({'error': 'Failed to connect to TopStep', 'details': connection_result['error']}), 400
            
            account_info = connection_result['account_info']
        
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
@jwt_required()
def get_broker_accounts():
    """Get all broker accounts for the current user"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_accounts = BrokerAccount.query.filter_by(user_id=user.id).all()
        
        return jsonify({
            'broker_accounts': [account.to_dict() for account in broker_accounts]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve broker accounts', 'details': str(e)}), 500

@broker_bp.route('/accounts/<int:account_id>', methods=['GET'])
@jwt_required()
def get_broker_account(account_id):
    """Get a specific broker account"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
        
        if not broker_account:
            return jsonify({'error': 'Broker account not found'}), 404
        
        return jsonify({
            'broker_account': broker_account.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve broker account', 'details': str(e)}), 500

@broker_bp.route('/accounts/<int:account_id>/sync', methods=['POST'])
@jwt_required()
def sync_broker_account(account_id):
    """Sync broker account data"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
        
        if not broker_account:
            return jsonify({'error': 'Broker account not found'}), 404
        
        # Decrypt credentials
        credentials = json.loads(decrypt_data(broker_account.api_credentials))
        
        # Sync based on broker type
        if broker_account.broker_type == 'tradovate':
            tradovate_service = TradovateService()
            sync_result = tradovate_service.sync_account_data(credentials, broker_account)
        elif broker_account.broker_type == 'topstep':
            topstep_service = TopStepService()
            sync_result = topstep_service.sync_account_data(credentials, broker_account)
        else:
            return jsonify({'error': 'Unknown broker type'}), 400
        
        if not sync_result['success']:
            return jsonify({'error': 'Failed to sync account data', 'details': sync_result['error']}), 500
        
        # Update last sync time
        broker_account.last_sync = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Account data synced successfully',
            'broker_account': broker_account.to_dict(),
            'sync_data': sync_result['data']
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to sync broker account', 'details': str(e)}), 500

@broker_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
@jwt_required()
def delete_broker_account(account_id):
    """Delete a broker account"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
        
        if not broker_account:
            return jsonify({'error': 'Broker account not found'}), 404
        
        db.session.delete(broker_account)
        db.session.commit()
        
        return jsonify({
            'message': 'Broker account deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete broker account', 'details': str(e)}), 500

@broker_bp.route('/accounts/<int:account_id>/test', methods=['POST'])
@jwt_required()
def test_broker_connection(account_id):
    """Test broker account connection"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
        
        if not broker_account:
            return jsonify({'error': 'Broker account not found'}), 404
        
        # Decrypt credentials
        credentials = json.loads(decrypt_data(broker_account.api_credentials))
        
        # Test connection based on broker type
        if broker_account.broker_type == 'tradovate':
            tradovate_service = TradovateService()
            test_result = tradovate_service.test_connection(credentials)
        elif broker_account.broker_type == 'topstep':
            topstep_service = TopStepService()
            test_result = topstep_service.test_connection(credentials)
        else:
            return jsonify({'error': 'Unknown broker type'}), 400
        
        return jsonify({
            'connection_status': 'success' if test_result['success'] else 'failed',
            'message': test_result.get('message', ''),
            'error': test_result.get('error', '') if not test_result['success'] else None
        }), 200 if test_result['success'] else 400
        
    except Exception as e:
        return jsonify({'error': 'Failed to test broker connection', 'details': str(e)}), 500

