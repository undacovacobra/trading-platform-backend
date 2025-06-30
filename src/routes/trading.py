from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, BrokerAccount, Position, Order, Trade
from src.services.tradovate_service import TradovateService
from src.services.topstep_service import TopStepService
from src.utils.encryption import decrypt_data
from datetime import datetime
import json

trading_bp = Blueprint('trading', __name__)

@trading_bp.route('/positions', methods=['GET'])
@jwt_required()
def get_positions():
    """Get all positions for the current user"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get account_id filter if provided
        account_id = request.args.get('account_id', type=int)
        
        if account_id:
            # Verify user owns this account
            broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
            if not broker_account:
                return jsonify({'error': 'Broker account not found'}), 404
            
            positions = Position.query.filter_by(broker_account_id=account_id).all()
        else:
            # Get all positions for all user's accounts
            user_account_ids = [acc.id for acc in user.broker_accounts]
            positions = Position.query.filter(Position.broker_account_id.in_(user_account_ids)).all()
        
        return jsonify({
            'positions': [position.to_dict() for position in positions]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve positions', 'details': str(e)}), 500

@trading_bp.route('/orders', methods=['GET'])
@jwt_required()
def get_orders():
    """Get all orders for the current user"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get account_id filter if provided
        account_id = request.args.get('account_id', type=int)
        status = request.args.get('status')  # pending, filled, cancelled
        
        query = Order.query
        
        if account_id:
            # Verify user owns this account
            broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
            if not broker_account:
                return jsonify({'error': 'Broker account not found'}), 404
            
            query = query.filter_by(broker_account_id=account_id)
        else:
            # Get all orders for all user's accounts
            user_account_ids = [acc.id for acc in user.broker_accounts]
            query = query.filter(Order.broker_account_id.in_(user_account_ids))
        
        if status:
            query = query.filter_by(status=status)
        
        orders = query.order_by(Order.created_at.desc()).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve orders', 'details': str(e)}), 500

@trading_bp.route('/orders', methods=['POST'])
@jwt_required()
def place_order():
    """Place a new trading order"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['broker_account_id', 'symbol', 'side', 'order_type', 'quantity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        broker_account_id = data['broker_account_id']
        symbol = data['symbol']
        side = data['side']  # 'buy' or 'sell'
        order_type = data['order_type']  # 'market', 'limit', 'stop'
        quantity = data['quantity']
        price = data.get('price')
        stop_price = data.get('stop_price')
        
        # Verify user owns this account
        broker_account = BrokerAccount.query.filter_by(id=broker_account_id, user_id=user.id).first()
        if not broker_account:
            return jsonify({'error': 'Broker account not found'}), 404
        
        # Validate order parameters
        if side not in ['buy', 'sell']:
            return jsonify({'error': 'Side must be "buy" or "sell"'}), 400
        
        if order_type not in ['market', 'limit', 'stop']:
            return jsonify({'error': 'Order type must be "market", "limit", or "stop"'}), 400
        
        if order_type in ['limit', 'stop'] and not price:
            return jsonify({'error': f'{order_type} orders require a price'}), 400
        
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400
        
        # Decrypt credentials
        credentials = json.loads(decrypt_data(broker_account.api_credentials))
        
        # Place order based on broker type
        if broker_account.broker_type == 'tradovate':
            tradovate_service = TradovateService()
            order_result = tradovate_service.place_order(credentials, {
                'symbol': symbol,
                'side': side,
                'order_type': order_type,
                'quantity': quantity,
                'price': price,
                'stop_price': stop_price
            })
        elif broker_account.broker_type == 'topstep':
            topstep_service = TopStepService()
            order_result = topstep_service.place_order(credentials, {
                'symbol': symbol,
                'side': side,
                'order_type': order_type,
                'quantity': quantity,
                'price': price,
                'stop_price': stop_price
            })
        else:
            return jsonify({'error': 'Unknown broker type'}), 400
        
        if not order_result['success']:
            return jsonify({'error': 'Failed to place order', 'details': order_result['error']}), 500
        
        # Create order record
        order = Order(
            broker_account_id=broker_account_id,
            broker_order_id=order_result['order_id'],
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status='pending'
        )
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'message': 'Order placed successfully',
            'order': order.to_dict(),
            'broker_response': order_result['data']
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to place order', 'details': str(e)}), 500

@trading_bp.route('/orders/<int:order_id>', methods=['PUT'])
@jwt_required()
def modify_order(order_id):
    """Modify an existing order"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find the order and verify ownership
        order = Order.query.join(BrokerAccount).filter(
            Order.id == order_id,
            BrokerAccount.user_id == user.id
        ).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status != 'pending':
            return jsonify({'error': 'Can only modify pending orders'}), 400
        
        data = request.get_json()
        
        # Get new parameters
        new_quantity = data.get('quantity', order.quantity)
        new_price = data.get('price', order.price)
        new_stop_price = data.get('stop_price', order.stop_price)
        
        # Decrypt credentials
        credentials = json.loads(decrypt_data(order.broker_account.api_credentials))
        
        # Modify order based on broker type
        if order.broker_account.broker_type == 'tradovate':
            tradovate_service = TradovateService()
            modify_result = tradovate_service.modify_order(credentials, order.broker_order_id, {
                'quantity': new_quantity,
                'price': new_price,
                'stop_price': new_stop_price
            })
        elif order.broker_account.broker_type == 'topstep':
            topstep_service = TopStepService()
            modify_result = topstep_service.modify_order(credentials, order.broker_order_id, {
                'quantity': new_quantity,
                'price': new_price,
                'stop_price': new_stop_price
            })
        else:
            return jsonify({'error': 'Unknown broker type'}), 400
        
        if not modify_result['success']:
            return jsonify({'error': 'Failed to modify order', 'details': modify_result['error']}), 500
        
        # Update order record
        order.quantity = new_quantity
        order.price = new_price
        order.stop_price = new_stop_price
        order.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Order modified successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to modify order', 'details': str(e)}), 500

@trading_bp.route('/orders/<int:order_id>', methods=['DELETE'])
@jwt_required()
def cancel_order(order_id):
    """Cancel an existing order"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Find the order and verify ownership
        order = Order.query.join(BrokerAccount).filter(
            Order.id == order_id,
            BrokerAccount.user_id == user.id
        ).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        if order.status != 'pending':
            return jsonify({'error': 'Can only cancel pending orders'}), 400
        
        # Decrypt credentials
        credentials = json.loads(decrypt_data(order.broker_account.api_credentials))
        
        # Cancel order based on broker type
        if order.broker_account.broker_type == 'tradovate':
            tradovate_service = TradovateService()
            cancel_result = tradovate_service.cancel_order(credentials, order.broker_order_id)
        elif order.broker_account.broker_type == 'topstep':
            topstep_service = TopStepService()
            cancel_result = topstep_service.cancel_order(credentials, order.broker_order_id)
        else:
            return jsonify({'error': 'Unknown broker type'}), 400
        
        if not cancel_result['success']:
            return jsonify({'error': 'Failed to cancel order', 'details': cancel_result['error']}), 500
        
        # Update order status
        order.status = 'cancelled'
        order.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel order', 'details': str(e)}), 500

@trading_bp.route('/trades', methods=['GET'])
@jwt_required()
def get_trades():
    """Get all trades for the current user"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get account_id filter if provided
        account_id = request.args.get('account_id', type=int)
        
        if account_id:
            # Verify user owns this account
            broker_account = BrokerAccount.query.filter_by(id=account_id, user_id=user.id).first()
            if not broker_account:
                return jsonify({'error': 'Broker account not found'}), 404
            
            trades = Trade.query.filter_by(broker_account_id=account_id).order_by(Trade.executed_at.desc()).all()
        else:
            # Get all trades for all user's accounts
            user_account_ids = [acc.id for acc in user.broker_accounts]
            trades = Trade.query.filter(Trade.broker_account_id.in_(user_account_ids)).order_by(Trade.executed_at.desc()).all()
        
        return jsonify({
            'trades': [trade.to_dict() for trade in trades]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve trades', 'details': str(e)}), 500

@trading_bp.route('/account-summary', methods=['GET'])
@jwt_required()
def get_account_summary():
    """Get account summary for all broker accounts"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        account_summaries = []
        
        for broker_account in user.broker_accounts:
            # Get positions for this account
            positions = Position.query.filter_by(broker_account_id=broker_account.id).all()
            
            # Calculate total P&L
            total_unrealized_pnl = sum(float(pos.unrealized_pnl or 0) for pos in positions)
            total_realized_pnl = sum(float(pos.realized_pnl or 0) for pos in positions)
            
            # Get recent trades
            recent_trades = Trade.query.filter_by(broker_account_id=broker_account.id).order_by(Trade.executed_at.desc()).limit(10).all()
            
            # Get pending orders
            pending_orders = Order.query.filter_by(broker_account_id=broker_account.id, status='pending').all()
            
            account_summary = {
                'broker_account': broker_account.to_dict(),
                'positions_count': len(positions),
                'pending_orders_count': len(pending_orders),
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_realized_pnl': total_realized_pnl,
                'total_pnl': total_unrealized_pnl + total_realized_pnl,
                'recent_trades': [trade.to_dict() for trade in recent_trades]
            }
            
            account_summaries.append(account_summary)
        
        return jsonify({
            'account_summaries': account_summaries
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve account summary', 'details': str(e)}), 500

