import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecureStorage:
    def __init__(self, storage_path="secure_data.enc"):
        self.storage_path = storage_path
        self.key = None
        self.fernet = None
        
    def _get_key(self, password):
        """Derive a key from the password using PBKDF2"""
        salt = b'notes_organizer_salt'  # Fixed salt for this application
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def initialize(self, password):
        """Initialize the storage with a password"""
        self.key = self._get_key(password)
        self.fernet = Fernet(self.key)
        
        # Create empty storage if it doesn't exist
        if not os.path.exists(self.storage_path):
            self.save_data({})

    def save_data(self, data):
        """Encrypt and save data to file"""
        if not self.fernet:
            raise Exception("Storage not initialized. Call initialize() first.")
            
        # Convert data to JSON and encrypt
        json_data = json.dumps(data)
        encrypted_data = self.fernet.encrypt(json_data.encode())
        
        # Save encrypted data
        with open(self.storage_path, 'wb') as f:
            f.write(encrypted_data)

    def load_data(self):
        """Load and decrypt data from file"""
        if not self.fernet:
            raise Exception("Storage not initialized. Call initialize() first.")
            
        if not os.path.exists(self.storage_path):
            return {}
            
        # Load and decrypt data
        with open(self.storage_path, 'rb') as f:
            encrypted_data = f.read()
            
        try:
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except:
            # If decryption fails, return empty dict
            return {}

    def get_value(self, key, default=None):
        """Get a value from secure storage"""
        data = self.load_data()
        return data.get(key, default)

    def set_value(self, key, value):
        """Set a value in secure storage"""
        data = self.load_data()
        data[key] = value
        self.save_data(data)

    def delete_value(self, key):
        """Delete a value from secure storage"""
        data = self.load_data()
        if key in data:
            del data[key]
            self.save_data(data)

    def clear_storage(self):
        """Clear all data from secure storage"""
        self.save_data({}) 