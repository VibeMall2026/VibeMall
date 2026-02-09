from django.apps import AppConfig

class HubConfig(AppConfig):
    name = 'Hub'

    def ready(self):
        import Hub.signals
