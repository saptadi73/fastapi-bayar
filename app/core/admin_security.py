import hashlib
import hmac
import secrets

COOKIE_NAME = "payment_admin_session"
ROLES = {
    "SUPER_ADMIN": {"admin.users.read", "admin.users.manage", "admin.roles.read", "admin.audit.read"},
    "INTEGRATION_ADMIN": set(),
    "FINANCE": set(),
    "AUDITOR": {"admin.audit.read"},
}
# Only implemented permissions are returned; future modules never imply access.
for role in ("SUPER_ADMIN", "INTEGRATION_ADMIN"):
    ROLES[role].update({"admin.clients.read", "admin.clients.manage", "admin.clients.rotate_secret"})
ROLES["AUDITOR"].add("admin.clients.read")
ROLES["SUPER_ADMIN"].add("admin.portal_users.read")
for role in ("SUPER_ADMIN", "INTEGRATION_ADMIN"):
    ROLES[role].update({"admin.services.read", "admin.services.manage"})
ROLES["AUDITOR"].add("admin.services.read")
for role in ("SUPER_ADMIN", "FINANCE", "AUDITOR"):
    ROLES[role].add("admin.payments.read")
for role in ("SUPER_ADMIN", "FINANCE"):
    ROLES[role].update({"admin.reconciliation.read", "admin.reconciliation.request"})
ROLES["AUDITOR"].add("admin.reconciliation.read")
for role in ("SUPER_ADMIN", "FINANCE"):
    ROLES[role].update({"admin.refunds.read", "admin.refunds.request", "admin.refunds.approve"})
ROLES["AUDITOR"].add("admin.refunds.read")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token: str) -> str:
    return digest("admin-csrf:" + token)


def hash_password(password: str) -> str:
    if not 15 <= len(password) <= 128:
        raise ValueError("Password admin wajib 15-128 karakter")
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"pbkdf2_sha256$600000${salt}${value}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or rounds != "600000" or len(password) > 128:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
