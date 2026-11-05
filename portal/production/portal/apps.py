from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = 'portal'

    def ready(self):
        from . import checks, private_client_signals  # noqa: F401
