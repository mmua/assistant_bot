import time
import jwt
import json
import requests
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

@dataclass
class YandexServiceAccount:
    private_key: str
    key_id: str
    service_account_id: str

class YandexAuthManager:
    """Manages Yandex Cloud authentication using JWT."""
    
    def __init__(self, service_account_file: str):
        """Initialize with service account details from JSON file."""
        self.service_account = self._load_service_account(service_account_file)
        self._iam_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    def _load_service_account(self, json_file: str) -> YandexServiceAccount:
        """Load service account details from JSON file."""
        with open(json_file, 'r') as f:
            data = json.load(f)
            return YandexServiceAccount(
                private_key=data['private_key'],
                key_id=data['id'],
                service_account_id=data['service_account_id']
            )

    def _prepare_private_key(self, pem_data: str) -> str:
        """Convert private key to proper PEM format if needed."""
        if not pem_data.startswith('-----BEGIN PRIVATE KEY-----'):
            # Add PEM headers and footers if they're missing
            pem_lines = ['-----BEGIN PRIVATE KEY-----']
            # Split the base64 string into 64-character lines
            pem_lines.extend([pem_data[i:i+64] for i in range(0, len(pem_data), 64)])
            pem_lines.append('-----END PRIVATE KEY-----')
            return '\n'.join(pem_lines)
        return pem_data

    def _generate_jwt(self) -> str:
        """Generate a JWT token for Yandex Cloud."""
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.service_account.service_account_id,
            'iat': now,
            'exp': now + 3600
        }

        # Prepare private key in proper format
        private_key_pem = self._prepare_private_key(self.service_account.private_key)
        
        try:
            # Load the private key for use with PyJWT
            key = load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
        except ValueError as e:
            raise ValueError(f"Invalid private key format: {e}")

        return jwt.encode(
            payload,
            key,
            algorithm='PS256',
            headers={'kid': self.service_account.key_id}
        )

    def _get_iam_token(self) -> str:
        """Exchange JWT for IAM token."""
        jwt_token = self._generate_jwt()
        response = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            json={'jwt': jwt_token}
        )
        response.raise_for_status()
        result = response.json()
        return result['iamToken']

    def get_token(self) -> str:
        """Get a valid IAM token, refreshing if necessary."""
        now = time.time()
        if not self._iam_token or not self._token_expires_at or now >= self._token_expires_at:
            self._iam_token = self._get_iam_token()
            self._token_expires_at = now + 3000  # Expire 60 seconds before actual expiration
        return self._iam_token
