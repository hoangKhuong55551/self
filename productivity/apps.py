from django.apps import AppConfig

class ProductivityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'productivity'
    verbose_name = 'Hiệu suất & Thói quen'

    def ready(self):
        import productivity.signals  # noqa: F401
