"""Environment or mounted-secret values; never log values or secret paths."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


def secret_value(name, default=''):
    value=os.environ.get(name)
    filename=os.environ.get(name+'_FILE')
    if value and filename:
        raise ImproperlyConfigured(f'Configure only {name} or its mounted-secret file, not both.')
    if filename:
        try:
            data=Path(filename).read_bytes()
            if not data or len(data)>8192:
                raise ValueError('Invalid secret size.')
            return data.decode('utf-8').rstrip('\r\n')
        except (OSError,ValueError,UnicodeError):
            raise ImproperlyConfigured(f'Cannot read configured {name} secret.') from None
    return value if value is not None else default
