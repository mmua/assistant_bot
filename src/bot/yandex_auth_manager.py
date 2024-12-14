import logging
import time
import json
import jwt
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

    def _generate_jwt(self) -> str:
        """Generate a JWT token for Yandex Cloud."""
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.service_account.service_account_id,
            'iat': now,
            'exp': now + 3600
        }

        try:
            # Generate the JWT
            jwt_token = jwt.encode(
                payload,
                self.service_account.private_key,
                algorithm='PS256',
                headers={'kid': self.service_account.key_id}
            )
            
            return jwt_token
            
        except Exception as e:
            logging.error(f"Error generating JWT: {e}")
            raise

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
    