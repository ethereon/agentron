import secrets

from datetime import datetime


_CROCKFORD_32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def generate_crockford_id(length: int) -> str:
    return ''.join(secrets.choice(_CROCKFORD_32) for _ in range(length))


def generate_session_id() -> str:
    date_prefix = datetime.now().strftime('%y%m%d')
    random_part = generate_crockford_id(length=10).lower()
    return f'{date_prefix}-{random_part}'
