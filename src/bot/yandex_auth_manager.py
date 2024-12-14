import time
import jwt
from dataclasses import dataclass
from typing import Optional

import requests

@dataclass
class YandexServiceAccount:
    private_key: str
    key_id: str
    service_account_id: str

class YandexAuthManager:
    """Manages Yandex Cloud authentication using JWT."""
    
    def __init__(self, service_account_id: str, key_id: str, private_key: str):
        """Initialize with service account details from JSON file."""
        self.service_account = YandexServiceAccount(
                private_key=private_key,
                key_id=key_id,
                service_account_id=service_account_id
            )
        self._iam_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    def _generate_jwt(self) -> str:
        """Generate a JWT token for Yandex Cloud."""
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.service_account.service_account_id,
            'iat': now,
            'exp': now + 7200
        }

        return jwt.encode(
            payload,
            self.service_account.private_key,
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
            self._token_expires_at = now + 6000  # Expire 600 seconds before actual expiration
        return self._iam_token
