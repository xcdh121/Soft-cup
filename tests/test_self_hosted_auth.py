import sys
import unittest
from pathlib import Path

import jwt

API_SRC = Path(__file__).resolve().parents[1] / "src" / "edu-api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from security import (  # noqa: E402
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class SelfHostedAuthSecurityTest(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self):
        first = hash_password("correct horse battery staple")
        second = hash_password("correct horse battery staple")

        self.assertNotEqual(first, second)
        self.assertNotIn("correct horse", first)
        self.assertTrue(verify_password("correct horse battery staple", first))
        self.assertFalse(verify_password("wrong password", first))
        self.assertFalse(verify_password("anything", "not-a-valid-hash"))

    def test_access_token_is_issued_and_validated(self):
        secret = "a" * 64
        token, expires_in = create_access_token(
            user_id="user-123",
            username="test_user",
            secret=secret,
            expires_minutes=60,
        )

        payload = decode_access_token(token, secret)
        self.assertEqual(payload["sub"], "user-123")
        self.assertEqual(payload["username"], "test_user")
        self.assertEqual(expires_in, 3600)

        with self.assertRaises(jwt.InvalidTokenError):
            decode_access_token(token, "b" * 64)


if __name__ == "__main__":
    unittest.main()
