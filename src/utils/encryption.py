from cryptography.fernet import Fernet
import base64
import os

# Generate a key for encryption (in production, this should be stored securely)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', 'your-encryption-key-here-change-in-production')

def get_fernet_key():
    """Get or generate a Fernet encryption key"""
    # In production, this should be stored in environment variables or a secure key management system
    if len(ENCRYPTION_KEY) < 32:
        # Pad the key to 32 bytes for Fernet
        padded_key = ENCRYPTION_KEY.ljust(32, '0')[:32]
    else:
        padded_key = ENCRYPTION_KEY[:32]
    
    # Encode to base64 for Fernet
    key = base64.urlsafe_b64encode(padded_key.encode())
    return Fernet(key)

def encrypt_data(data):
    """Encrypt sensitive data"""
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        fernet = get_fernet_key()
        encrypted_data = fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        raise Exception(f"Encryption failed: {str(e)}")

def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    try:
        if isinstance(encrypted_data, str):
            encrypted_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
        
        fernet = get_fernet_key()
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode('utf-8')
    except Exception as e:
        raise Exception(f"Decryption failed: {str(e)}")

def generate_new_key():
    """Generate a new encryption key (for key rotation)"""
    return Fernet.generate_key().decode('utf-8')

