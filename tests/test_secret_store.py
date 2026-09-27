from cryptography.fernet import Fernet
import pytest

from app.core.errors import AppError
from app.core.secret_store import decrypt_secret, encrypt_secret


def test_secret_store_encrypts_without_plaintext_round_trip():
    key = Fernet.generate_key().decode()
    encrypted = encrypt_secret("callback-secret", key)
    assert encrypted != "callback-secret"
    assert decrypt_secret(encrypted, key) == "callback-secret"


def test_secret_store_rejects_wrong_key():
    key = Fernet.generate_key().decode()
    other_key = Fernet.generate_key().decode()
    encrypted = encrypt_secret("callback-secret", key)
    with pytest.raises(AppError) as error:
        decrypt_secret(encrypted, other_key)
    assert error.value.code == "CREDENTIAL_DECRYPTION_FAILED"


def test_secret_store_accepts_previous_key_during_rotation():
    previous_key = Fernet.generate_key().decode()
    current_key = Fernet.generate_key().decode()
    encrypted = encrypt_secret("callback-secret", previous_key)
    assert decrypt_secret(encrypted, current_key, previous_key) == "callback-secret"
