import requests
import json
from datetime import datetime, timedelta
from src.models.user import db, Position, Order, Trade

class TradovateService:
    def __init__(self):
        self.demo_base_url = "https://demo.tradovateapi.com/v1"
        self.live_base_url = "https://live.tradovateapi.com/v1"
        self.md_base_url = "https://md.tradovateapi.com/v1"
        
    def get_access_token(self, credentials, is_live=False):
        """Get access token from Tradovate API"""
        try:
            base_url = self.live_base_url if is_live else self.demo_base_url
            
            auth_data = {
                "name": credentials['username'],
                "password": credentials['password'],
                "appId": "TradingPlatform",
                "appVersion": "1.0",
                "cid": 8,  # Default client ID
                "sec": credentials['secret'],
                "deviceId": credentials.get('device_id', 'trading-platform-device')
            }
            
            response = requests.post(
                f"{base_url}/auth/accesstokenrequest",
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                json=auth_data,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'access_token': data.get('accessToken'),
                    'md_access_token': data.get('mdAccessToken'),
                    'expiration_time': data.get('expirationTime'),
                    'user_id': data.get('userId'),
                    'has_live': data.get('hasLive', False)
                }
            else:
                return {
                    'success': False,
                    'error': f"Authentication failed: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Connection error: {str(e)}"
            }
    
    def test_connection(self, credentials):
        """Test connection to Tradovate API"""
        try:
            # Try to get access token
            auth_result = self.get_access_token(credentials)
            
            if not auth_result['success']:
                return auth_result
            
            access_token = auth_result['access_token']
            
            # Test API call to get user info
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.demo_base_url}/user/me",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                user_data = response.json()
                
                # Get account information
                accounts_response = requests.get(
                    f"{self.demo_base_url}/account/list",
                    headers=headers,
                    timeout=30
                )
                
                account_info = {}
                if accounts_response.status_code == 200:
                    accounts = accounts_response.json()
                    if accounts:
                        account = accounts[0]  # Use first account
                        account_info = {
                            'account_id': str(account.get('id', '')),
                            'account_name': account.get('name', ''),
                            'balance': account.get('cashBalance', 0),
                            'equity': account.get('netLiquidationValue', 0),
                            'margin_used': account.get('marginUsed', 0),
                            'margin_available': account.get('marginAvailable', 0)
                        }
                
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'account_info': account_info
                }
            else:
                return {
                    'success': False,
                    'error': f"API test failed: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Connection test failed: {str(e)}"
            }
    
    def sync_account_data(self, credentials, broker_account):
        """Sync account data from Tradovate"""
        try:
            # Get access token
            auth_result = self.get_access_token(credentials)
            
            if not auth_result['success']:
                return auth_result
            
            access_token = auth_result['access_token']
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            # Get account information
            accounts_response = requests.get(
                f"{self.demo_base_url}/account/list",
                headers=headers,
                timeout=30
            )
            
            if accounts_response.status_code != 200:
                return {
                    'success': False,
                    'error': f"Failed to get account data: {accounts_response.text}"
                }
            
            accounts = accounts_response.json()
            if not accounts:
                return {
                    'success': False,
                    'error': "No accounts found"
                }
            
            account = accounts[0]  # Use first account
            
            # Update broker account with latest data
            broker_account.balance = account.get('cashBalance', 0)
            broker_account.equity = account.get('netLiquidationValue', 0)
            broker_account.margin_used = account.get('marginUsed', 0)
            broker_account.margin_available = account.get('marginAvailable', 0)
            
            # Get positions
            positions_response = requests.get(
                f"{self.demo_base_url}/position/list",
                headers=headers,
                timeout=30
            )
            
            positions_data = []
            if positions_response.status_code == 200:
                positions = positions_response.json()
                
                # Update positions in database
                for pos_data in positions:
                    if pos_data.get('netPos', 0) != 0:  # Only active positions
                        # Check if position already exists
                        existing_position = Position.query.filter_by(
                            broker_account_id=broker_account.id,
                            symbol=pos_data.get('contractName', '')
                        ).first()
                        
                        if existing_position:
                            # Update existing position
                            existing_position.quantity = abs(pos_data.get('netPos', 0))
                            existing_position.side = 'long' if pos_data.get('netPos', 0) > 0 else 'short'
                            existing_position.current_price = pos_data.get('price', 0)
                            existing_position.unrealized_pnl = pos_data.get('unrealizedPnL', 0)
                            existing_position.updated_at = datetime.utcnow()
                        else:
                            # Create new position
                            new_position = Position(
                                broker_account_id=broker_account.id,
                                symbol=pos_data.get('contractName', ''),
                                side='long' if pos_data.get('netPos', 0) > 0 else 'short',
                                quantity=abs(pos_data.get('netPos', 0)),
                                entry_price=pos_data.get('price', 0),
                                current_price=pos_data.get('price', 0),
                                unrealized_pnl=pos_data.get('unrealizedPnL', 0),
                                opened_at=datetime.utcnow()
                            )
                            db.session.add(new_position)
                        
                        positions_data.append({
                            'symbol': pos_data.get('contractName', ''),
                            'side': 'long' if pos_data.get('netPos', 0) > 0 else 'short',
                            'quantity': abs(pos_data.get('netPos', 0)),
                            'unrealized_pnl': pos_data.get('unrealizedPnL', 0)
                        })
            
            # Get orders
            orders_response = requests.get(
                f"{self.demo_base_url}/order/list",
                headers=headers,
                timeout=30
            )
            
            orders_data = []
            if orders_response.status_code == 200:
                orders = orders_response.json()
                
                for order_data in orders:
                    orders_data.append({
                        'id': order_data.get('id'),
                        'symbol': order_data.get('contractName', ''),
                        'side': order_data.get('action', '').lower(),
                        'quantity': order_data.get('qty', 0),
                        'price': order_data.get('price', 0),
                        'status': order_data.get('orderStatus', '').lower()
                    })
            
            db.session.commit()
            
            return {
                'success': True,
                'data': {
                    'account': {
                        'balance': broker_account.balance,
                        'equity': broker_account.equity,
                        'margin_used': broker_account.margin_used,
                        'margin_available': broker_account.margin_available
                    },
                    'positions': positions_data,
                    'orders': orders_data
                }
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f"Sync failed: {str(e)}"
            }
    
    def place_order(self, credentials, order_data):
        """Place an order through Tradovate API"""
        try:
            # Get access token
            auth_result = self.get_access_token(credentials)
            
            if not auth_result['success']:
                return auth_result
            
            access_token = auth_result['access_token']
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            # Convert order data to Tradovate format
            tradovate_order = {
                "accountSpec": credentials.get('account_id', ''),
                "contractName": order_data['symbol'],
                "action": order_data['side'].upper(),
                "orderQty": order_data['quantity'],
                "orderType": order_data['order_type'].upper()
            }
            
            if order_data.get('price'):
                tradovate_order['price'] = order_data['price']
            
            if order_data.get('stop_price'):
                tradovate_order['stopPrice'] = order_data['stop_price']
            
            response = requests.post(
                f"{self.demo_base_url}/order/placeorder",
                headers=headers,
                json=tradovate_order,
                timeout=30
            )
            
            if response.status_code == 200:
                order_response = response.json()
                return {
                    'success': True,
                    'order_id': str(order_response.get('orderId', '')),
                    'data': order_response
                }
            else:
                return {
                    'success': False,
                    'error': f"Order placement failed: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Order placement error: {str(e)}"
            }
    
    def modify_order(self, credentials, order_id, modifications):
        """Modify an existing order"""
        try:
            # Get access token
            auth_result = self.get_access_token(credentials)
            
            if not auth_result['success']:
                return auth_result
            
            access_token = auth_result['access_token']
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            modify_data = {
                "orderId": order_id
            }
            
            if modifications.get('quantity'):
                modify_data['orderQty'] = modifications['quantity']
            
            if modifications.get('price'):
                modify_data['price'] = modifications['price']
            
            if modifications.get('stop_price'):
                modify_data['stopPrice'] = modifications['stop_price']
            
            response = requests.post(
                f"{self.demo_base_url}/order/modifyorder",
                headers=headers,
                json=modify_data,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"Order modification failed: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Order modification error: {str(e)}"
            }
    
    def cancel_order(self, credentials, order_id):
        """Cancel an existing order"""
        try:
            # Get access token
            auth_result = self.get_access_token(credentials)
            
            if not auth_result['success']:
                return auth_result
            
            access_token = auth_result['access_token']
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            }
            
            cancel_data = {
                "orderId": order_id
            }
            
            response = requests.post(
                f"{self.demo_base_url}/order/cancelorder",
                headers=headers,
                json=cancel_data,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"Order cancellation failed: {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Order cancellation error: {str(e)}"
            }

