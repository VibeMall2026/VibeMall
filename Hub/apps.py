from django.apps import AppConfig

class HubConfig(AppConfig):
    name = 'Hub'

    def ready(self):
        import Hub.signals

        # Registers the connection_created hook that puts SQLite into WAL mode.
        # Imported here so it is in place before the first query, whichever
        # process starts — web, Telegram listener, draft worker or a command.
        import Hub.db_pragmas  # noqa: F401
