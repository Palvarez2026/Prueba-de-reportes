"""
Autenticacion simple por rol (clave compartida por rol, sin usuarios individuales).
Pensado para un equipo chico: 3 roles -> 3 claves. El admin puede rotar las claves
desde /admin.html sin depender de un despliegue nuevo.

OJO: el filesystem de Render es efimero. Si cambias una clave desde /admin.html,
ese cambio se pierde en el proximo redeploy y vuelve a las claves por defecto
definidas en DEFAULT_PASSWORDS mas abajo (mismo comportamiento que gantt.json /
data.json). Si quieres que una clave nueva quede "de fabrica", pide que se
actualice DEFAULT_PASSWORDS en el codigo.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

AUTH_PATH = Path(__file__).parent / "auth.json"
SECRET_PATH = Path(__file__).parent / ".secret_key"

ROLES = ["admin", "director", "supervisor"]

# Claves por defecto "de fabrica" (se usan la primera vez que corre el backend,
# o si auth.json se pierde por un redeploy). CAMBIALAS desde /admin.html apenas
# tengas la app arriba.
DEFAULT_PASSWORDS = {
    "admin": "andes2026",
    "director": "director2026",
    "supervisor": "supervisor2026",
}

# Que paginas puede ver cada rol (usado tambien por el frontend via /api/me)
PAGE_ACCESS = {
    "index.html": ["admin", "director"],
    "resumen_diario.html": ["admin", "director"],
    "gantt.html": ["admin", "director"],
    "ingreso_diario.html": ["admin", "supervisor"],
    "admin.html": ["admin"],
}

DEFAULT_LANDING = {
    "admin": "/index.html",
    "director": "/index.html",
    "supervisor": "/ingreso_diario.html",
}

SESSION_MAX_AGE = 8 * 3600  # 8 horas


def _get_secret() -> bytes:
    if SECRET_PATH.exists():
        return SECRET_PATH.read_bytes()
    secret = os.urandom(32)
    SECRET_PATH.write_bytes(secret)
    return secret


_SECRET = _get_secret()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        dk = base64.b64decode(dk_b64)
    except Exception:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(dk, test)


def load_auth() -> dict:
    if not AUTH_PATH.exists():
        default = {rol: _hash_password(pw) for rol, pw in DEFAULT_PASSWORDS.items()}
        AUTH_PATH.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(AUTH_PATH.read_text())


def save_auth(data: dict) -> None:
    AUTH_PATH.write_text(json.dumps(data, indent=2))


def check_login(rol: str, clave: str) -> bool:
    data = load_auth()
    if rol not in data:
        return False
    return _verify_password(clave, data[rol])


def set_password(rol: str, nueva_clave: str) -> None:
    if rol not in ROLES:
        raise KeyError(f"Rol desconocido: {rol}")
    if not nueva_clave or len(nueva_clave) < 4:
        raise ValueError("La clave debe tener al menos 4 caracteres")
    data = load_auth()
    data[rol] = _hash_password(nueva_clave)
    save_auth(data)


def make_token(rol: str) -> str:
    payload = f"{rol}:{int(time.time()) + SESSION_MAX_AGE}"
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + sig


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload_b64, sig = token.split(".")
        payload = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        expected_sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        rol, exp = payload.rsplit(":", 1)
        if int(exp) < time.time():
            return None
        if rol not in ROLES:
            return None
        return rol
    except Exception:
        return None
