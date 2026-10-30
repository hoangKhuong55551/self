from django.apps import AppConfig

class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'library'
    verbose_name = 'Thư viện Sách, Phim & Game'

    def ready(self):
        import library.signals  # noqa: F401
