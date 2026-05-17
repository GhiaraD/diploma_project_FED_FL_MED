"""
Teste unitare pentru services/node/api/app/security.py și schemas.py

Acoperă logica pură din SecurityManager (fără DB sau Redis real):
  - verify_password / get_password_hash
  - validate_password_strength
  - create_access_token / verify_token
  - has_permission
  - get_user_permissions
  - check_rate_limit (cu Redis mock)
  - revoke_token (cu Redis mock)

Și validarea schemelor Pydantic:
  - UserCreate — validare email, parolă, rol, node_id
  - ApiKeyCreate — validare expires_days, permissions
  - PasswordChange — validare min_length

Strategia de import:
  - Stub-urile pentru flwr și node_core sunt în conftest.py
  - Redis e mock-uit per test
  - SQLAlchemy folosește SQLite in-memory

Rulare:
    pytest tests/test_node_api_security.py -v
"""
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import cu cale absolută (evită conflicte cu sys.path și __init__.py)
# ---------------------------------------------------------------------------

_API_DIR = Path(__file__).parent.parent / "services" / "node" / "api"
sys.path.insert(0, str(_API_DIR))

# Stub pentru celery (folosit de tasks.py, nu direct de security.py,
# dar config.py îl importă indirect)
import types as _types
_celery_stub = _types.ModuleType("celery")
_celery_stub.Celery = MagicMock
sys.modules.setdefault("celery", _celery_stub)

# Stub pentru redis (security.py încearcă să se conecteze la Redis la import)
_redis_stub = _types.ModuleType("redis")
_mock_redis_cls = MagicMock()
_mock_redis_instance = MagicMock()
_mock_redis_instance.ping.side_effect = Exception("no redis in tests")
_mock_redis_cls.return_value = _mock_redis_instance
_redis_stub.Redis = _mock_redis_cls
sys.modules.setdefault("redis", _redis_stub)

# Stub pentru jose (JWT)
try:
    from jose import jwt as _jose_jwt  # noqa — verificăm dacă e disponibil
except ImportError:
    _jose_stub = _types.ModuleType("jose")
    _jose_jwt_stub = _types.ModuleType("jose.jwt")
    _jose_stub.JWTError = Exception
    _jose_stub.jwt = MagicMock()
    sys.modules.setdefault("jose", _jose_stub)
    sys.modules.setdefault("jose.jwt", _jose_jwt_stub)

# Stub pentru bcrypt dacă nu e instalat
try:
    import bcrypt as _bcrypt  # noqa
except ImportError:
    _bcrypt_stub = _types.ModuleType("bcrypt")
    _bcrypt_stub.checkpw = MagicMock(return_value=True)
    _bcrypt_stub.hashpw = MagicMock(return_value=b"$2b$12$fakehash")
    _bcrypt_stub.gensalt = MagicMock(return_value=b"$2b$12$fakesalt")
    sys.modules.setdefault("bcrypt", _bcrypt_stub)

# Importăm modulele cu importlib
def _load_module(name, rel_path):
    path = _API_DIR / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# config.py creează directoare la import — redirectăm STORAGE_ROOT spre /tmp
import os as _os
_os.environ.setdefault("STORAGE_ROOT", "/tmp/test_fed_med_fl_node_api")
_os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_config = _load_module("app.config", "app/config.py")
_database = _load_module("app.database", "app/database.py")

_security = _load_module("app.security", "app/security.py")
_schemas = _load_module("app.schemas", "app/schemas.py")

SecurityManager = _security.SecurityManager


# ===========================================================================
# SecurityManager.verify_password / get_password_hash
# ===========================================================================

class TestPasswordHashing:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_hash_and_verify_roundtrip(self):
        password = "MySecurePass@2026"
        hashed = self.sm.get_password_hash(password)
        assert self.sm.verify_password(password, hashed)

    def test_wrong_password_fails_verification(self):
        hashed = self.sm.get_password_hash("CorrectPass@2026")
        assert not self.sm.verify_password("WrongPass@2026", hashed)

    def test_hash_is_string(self):
        hashed = self.sm.get_password_hash("TestPass@2026!")
        assert isinstance(hashed, str)

    def test_hash_is_not_plaintext(self):
        password = "TestPass@2026!"
        hashed = self.sm.get_password_hash(password)
        assert hashed != password

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt folosește salt aleatoriu — hash-urile trebuie să difere."""
        password = "TestPass@2026!"
        h1 = self.sm.get_password_hash(password)
        h2 = self.sm.get_password_hash(password)
        assert h1 != h2

    def test_verify_returns_false_for_empty_hash(self):
        result = self.sm.verify_password("SomePass@2026", "not_a_valid_hash")
        assert result is False

    def test_long_password_truncated_to_72_bytes(self):
        """bcrypt trunchiază la 72 bytes — parola lungă trebuie să funcționeze."""
        long_pass = "A" * 100 + "@2026aB"
        hashed = self.sm.get_password_hash(long_pass)
        assert self.sm.verify_password(long_pass, hashed)


# ===========================================================================
# SecurityManager.validate_password_strength
# ===========================================================================

class TestValidatePasswordStrength:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_valid_strong_password(self):
        ok, msg = self.sm.validate_password_strength("StrongPass@2026!")
        assert ok is True
        assert msg == ""

    def test_too_short_fails(self):
        ok, msg = self.sm.validate_password_strength("Short@1A")
        assert ok is False
        assert "12 characters" in msg

    def test_no_uppercase_fails(self):
        ok, msg = self.sm.validate_password_strength("nouppercase@2026!")
        assert ok is False
        assert "uppercase" in msg.lower()

    def test_no_lowercase_fails(self):
        ok, msg = self.sm.validate_password_strength("NOLOWERCASE@2026!")
        assert ok is False
        assert "lowercase" in msg.lower()

    def test_no_digit_fails(self):
        ok, msg = self.sm.validate_password_strength("NoDigitPass@!")
        assert ok is False
        assert "number" in msg.lower()

    def test_no_special_char_fails(self):
        ok, msg = self.sm.validate_password_strength("NoSpecialChar2026A")
        assert ok is False
        assert "special" in msg.lower()

    def test_exactly_12_chars_valid(self):
        ok, _ = self.sm.validate_password_strength("Abcdef@1234!")
        assert ok is True

    def test_11_chars_invalid(self):
        ok, _ = self.sm.validate_password_strength("Abcdef@123!")
        assert ok is False

    @given(
        length=st.integers(min_value=1, max_value=11),
    )
    @hyp_settings(max_examples=30)
    def test_short_passwords_always_fail(self, length):
        """Orice parolă sub 12 caractere trebuie să eșueze."""
        password = "A" * max(1, length - 3) + "a1!"
        password = password[:length]
        ok, _ = self.sm.validate_password_strength(password)
        assert ok is False


# ===========================================================================
# SecurityManager.get_user_permissions
# ===========================================================================

class TestGetUserPermissions:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_admin_has_wildcard(self):
        perms = self.sm.get_user_permissions("admin")
        assert "*" in perms

    def test_doctor_has_read_models(self):
        perms = self.sm.get_user_permissions("doctor")
        assert "read:models" in perms

    def test_researcher_has_write_training(self):
        perms = self.sm.get_user_permissions("researcher")
        assert "write:training" in perms

    def test_viewer_cannot_write(self):
        perms = self.sm.get_user_permissions("viewer")
        write_perms = [p for p in perms if p.startswith("write:")]
        assert len(write_perms) == 0

    def test_unknown_role_returns_empty(self):
        perms = self.sm.get_user_permissions("unknown_role")
        assert perms == []

    def test_returns_list(self):
        for role in ["admin", "doctor", "researcher", "viewer"]:
            assert isinstance(self.sm.get_user_permissions(role), list)


# ===========================================================================
# SecurityManager.has_permission
# ===========================================================================

class TestHasPermission:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_wildcard_grants_everything(self):
        assert self.sm.has_permission(["*"], "read:models") is True
        assert self.sm.has_permission(["*"], "write:training") is True
        assert self.sm.has_permission(["*"], "anything:at:all") is True

    def test_exact_match(self):
        assert self.sm.has_permission(["read:models", "write:inference"], "read:models") is True

    def test_missing_permission_denied(self):
        assert self.sm.has_permission(["read:models"], "write:models") is False

    def test_empty_permissions_denied(self):
        assert self.sm.has_permission([], "read:models") is False

    def test_wildcard_prefix_match(self):
        """'read:*' trebuie să permită orice permisiune care începe cu 'read:'."""
        assert self.sm.has_permission(["read:*"], "read:models") is True
        assert self.sm.has_permission(["read:*"], "read:datasets") is True
        assert self.sm.has_permission(["read:*"], "write:models") is False

    def test_admin_permissions_grant_all(self):
        admin_perms = self.sm.get_user_permissions("admin")
        assert self.sm.has_permission(admin_perms, "read:models") is True
        assert self.sm.has_permission(admin_perms, "write:training") is True
        assert self.sm.has_permission(admin_perms, "delete:everything") is True

    def test_viewer_cannot_write_training(self):
        viewer_perms = self.sm.get_user_permissions("viewer")
        assert self.sm.has_permission(viewer_perms, "write:training") is False

    def test_researcher_can_write_federated(self):
        researcher_perms = self.sm.get_user_permissions("researcher")
        assert self.sm.has_permission(researcher_perms, "write:federated") is True


# ===========================================================================
# SecurityManager.create_access_token / verify_token
# ===========================================================================

class TestJWTTokens:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_create_token_returns_string(self):
        token = self.sm.create_access_token({"sub": "user123", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_returns_payload(self):
        data = {"sub": "user123", "email": "test@node1.com", "role": "doctor"}
        token = self.sm.create_access_token(data)
        payload = self.sm.verify_token(token)
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@node1.com"

    def test_token_contains_jti(self):
        token = self.sm.create_access_token({"sub": "u1"})
        payload = self.sm.verify_token(token)
        assert "jti" in payload

    def test_token_contains_exp(self):
        token = self.sm.create_access_token({"sub": "u1"})
        payload = self.sm.verify_token(token)
        assert "exp" in payload

    def test_token_contains_iat(self):
        token = self.sm.create_access_token({"sub": "u1"})
        payload = self.sm.verify_token(token)
        assert "iat" in payload

    def test_expired_token_raises(self):
        token = self.sm.create_access_token(
            {"sub": "u1"},
            expires_delta=timedelta(seconds=-1)  # già scaduto
        )
        with pytest.raises(Exception):
            self.sm.verify_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            self.sm.verify_token("not.a.valid.token")

    def test_custom_expiry_respected(self):
        """Token cu expiry custom trebuie să conțină exp corect."""
        delta = timedelta(hours=2)
        before = datetime.utcnow()
        token = self.sm.create_access_token({"sub": "u1"}, expires_delta=delta)
        payload = self.sm.verify_token(token)
        after = datetime.utcnow()

        exp = datetime.utcfromtimestamp(payload["exp"])
        assert exp > before + timedelta(hours=1, minutes=55)
        assert exp < after + timedelta(hours=2, minutes=5)

    def test_two_tokens_have_different_jti(self):
        t1 = self.sm.create_access_token({"sub": "u1"})
        t2 = self.sm.create_access_token({"sub": "u1"})
        p1 = self.sm.verify_token(t1)
        p2 = self.sm.verify_token(t2)
        assert p1["jti"] != p2["jti"]


# ===========================================================================
# SecurityManager.check_rate_limit (Redis mock)
# ===========================================================================

class TestCheckRateLimit:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_allowed_when_redis_unavailable(self):
        """Fără Redis, rate limiting e dezactivat → always allowed."""
        original = _security.redis_client
        _security.redis_client = None
        try:
            allowed, info = self.sm.check_rate_limit("user1", "admin", "/api/health")
            assert allowed is True
        finally:
            _security.redis_client = original

    def test_allowed_when_under_limit(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # nicio cerere anterioară
        mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline

        original = _security.redis_client
        _security.redis_client = mock_redis
        try:
            allowed, info = self.sm.check_rate_limit("user1", "doctor", "/api/models")
            assert allowed is True
        finally:
            _security.redis_client = original

    def test_blocked_when_over_general_limit(self):
        mock_redis = MagicMock()
        # Simulăm că userul a depășit limita (viewer = 30 req/min)
        mock_redis.get.return_value = "31"

        original = _security.redis_client
        _security.redis_client = mock_redis
        try:
            allowed, info = self.sm.check_rate_limit("user1", "viewer", "/api/models")
            assert allowed is False
            assert info["limit_type"] == "general"
        finally:
            _security.redis_client = original

    def test_rate_limits_differ_by_role(self):
        """Admin are limită mai mare decât viewer."""
        assert self.sm.rate_limits["admin"] > self.sm.rate_limits["viewer"]
        assert self.sm.rate_limits["doctor"] > self.sm.rate_limits["viewer"]


# ===========================================================================
# SecurityManager.revoke_token (Redis mock)
# ===========================================================================

class TestRevokeToken:

    def setup_method(self):
        self.sm = SecurityManager()

    def test_returns_false_without_redis(self):
        original = _security.redis_client
        _security.redis_client = None
        try:
            result = self.sm.revoke_token("some-jti")
            assert result is False
        finally:
            _security.redis_client = original

    def test_returns_false_when_session_not_found(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # sesiunea nu există

        original = _security.redis_client
        _security.redis_client = mock_redis
        try:
            result = self.sm.revoke_token("nonexistent-jti")
            assert result is False
        finally:
            _security.redis_client = original

    def test_returns_true_when_session_found_and_ttl_positive(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"user_id": "u1"}'
        mock_redis.ttl.return_value = 3600  # 1 oră rămasă

        original = _security.redis_client
        _security.redis_client = mock_redis
        try:
            result = self.sm.revoke_token("valid-jti")
            assert result is True
            mock_redis.setex.assert_called_once()
            mock_redis.delete.assert_called_once()
        finally:
            _security.redis_client = original

    def test_returns_false_when_ttl_zero(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"user_id": "u1"}'
        mock_redis.ttl.return_value = 0  # token deja expirat

        original = _security.redis_client
        _security.redis_client = mock_redis
        try:
            result = self.sm.revoke_token("expired-jti")
            assert result is False
        finally:
            _security.redis_client = original


# ===========================================================================
# Schemas — validare Pydantic
# ===========================================================================

class TestUserCreateSchema:

    def test_valid_user_create(self):
        user = _schemas.UserCreate(
            email="admin@node1.fed-med-fl.com",
            password="StrongPass@2026!",
            role="admin",
            node_id="node1",
        )
        assert user.email == "admin@node1.fed-med-fl.com"
        assert user.role == "admin"

    def test_invalid_email_raises(self):
        with pytest.raises(Exception):
            _schemas.UserCreate(
                email="not-an-email",
                password="StrongPass@2026!",
                role="admin",
                node_id="node1",
            )

    def test_invalid_role_raises(self):
        with pytest.raises(Exception):
            _schemas.UserCreate(
                email="user@node1.com",
                password="StrongPass@2026!",
                role="superuser",  # invalid
                node_id="node1",
            )

    def test_invalid_node_id_raises(self):
        with pytest.raises(Exception):
            _schemas.UserCreate(
                email="user@node1.com",
                password="StrongPass@2026!",
                role="admin",
                node_id="node99",  # invalid
            )

    def test_password_too_short_raises(self):
        with pytest.raises(Exception):
            _schemas.UserCreate(
                email="user@node1.com",
                password="short",
                role="admin",
                node_id="node1",
            )

    def test_all_valid_roles_accepted(self):
        for role in ["admin", "doctor", "researcher", "viewer"]:
            user = _schemas.UserCreate(
                email=f"{role}@node1.com",
                password="StrongPass@2026!",
                role=role,
                node_id="node1",
            )
            assert user.role == role

    def test_all_valid_node_ids_accepted(self):
        for node_id in ["node1", "node2", "node3", "central"]:
            user = _schemas.UserCreate(
                email=f"user@{node_id}.com",
                password="StrongPass@2026!",
                role="admin",
                node_id=node_id,
            )
            assert user.node_id == node_id


class TestApiKeyCreateSchema:

    def test_valid_api_key_create(self):
        key = _schemas.ApiKeyCreate(
            node_id="node1",
            permissions=["read:models", "write:federated"],
            expires_days=365,
        )
        assert key.node_id == "node1"
        assert key.expires_days == 365

    def test_default_expires_days(self):
        key = _schemas.ApiKeyCreate(
            node_id="node2",
            permissions=["read:models"],
        )
        assert key.expires_days == 365

    def test_expires_days_too_low_raises(self):
        with pytest.raises(Exception):
            _schemas.ApiKeyCreate(
                node_id="node1",
                permissions=[],
                expires_days=0,  # min=1
            )

    def test_expires_days_too_high_raises(self):
        with pytest.raises(Exception):
            _schemas.ApiKeyCreate(
                node_id="node1",
                permissions=[],
                expires_days=3651,  # max=3650
            )

    def test_invalid_node_id_raises(self):
        with pytest.raises(Exception):
            _schemas.ApiKeyCreate(
                node_id="node99",
                permissions=[],
            )


class TestPasswordChangeSchema:

    def test_valid_password_change(self):
        pc = _schemas.PasswordChange(
            current_password="OldPass@2026!",
            new_password="NewPass@2026!",
        )
        assert pc.current_password == "OldPass@2026!"

    def test_new_password_too_short_raises(self):
        with pytest.raises(Exception):
            _schemas.PasswordChange(
                current_password="OldPass@2026!",
                new_password="short",  # min_length=12
            )


class TestTrainRequestSchema:

    def test_defaults(self):
        req = _schemas.TrainRequest(dataset_id="ds_001")
        assert req.model_name == "resnet18"
        assert req.num_epochs == 10
        assert req.batch_size == 32
        assert req.learning_rate == 0.001

    def test_custom_values(self):
        req = _schemas.TrainRequest(
            dataset_id="ds_002",
            model_name="efficientnet_b0",
            num_epochs=5,
            batch_size=16,
        )
        assert req.model_name == "efficientnet_b0"
        assert req.num_epochs == 5


class TestFLStartRequestSchema:

    def test_valid_fl_start(self):
        req = _schemas.FLStartRequest(
            num_rounds=10,
            num_epochs=2,
            model_name="efficientnet_b0",
            learning_rate=0.001,
            min_fit_clients=4,
            min_available_clients=4,
        )
        assert req.num_rounds == 10

    def test_num_rounds_too_low_raises(self):
        with pytest.raises(Exception):
            _schemas.FLStartRequest(num_rounds=0)

    def test_num_rounds_too_high_raises(self):
        with pytest.raises(Exception):
            _schemas.FLStartRequest(num_rounds=101)

    def test_learning_rate_zero_raises(self):
        with pytest.raises(Exception):
            _schemas.FLStartRequest(learning_rate=0.0)
