"""
Django settings for Life OS project.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Đọc biến môi trường từ .env (không commit file này, xem .env.example)
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY phải được đặt khi DJANGO_DEBUG=False')
    SECRET_KEY = 'django-insecure-dev-only-key'

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1' if not DEBUG else '*')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
# Render tự đặt biến này = tên miền của web (vd lifeos.onrender.com)
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Chặn dò mật khẩu (khoá tạm sau nhiều lần đăng nhập sai)
    'axes',
    # Life OS Apps
    'core.apps.CoreConfig',
    'finance.apps.FinanceConfig',
    'productivity.apps.ProductivityConfig',
    'academic.apps.AcademicConfig',
    'library.apps.LibraryConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Phục vụ file tĩnh khi chạy production (không cần nginx)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom middleware
    'core.middleware.SubscriptionCheckMiddleware',
    # Đặt cuối để bắt được mọi lần đăng nhập thất bại
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.user_profile_context',
                'core.context_processors.notifications_context',
                'core.context_processors.site_settings',
            ],
            'libraries': {
                'core_tags': 'core.templatetags.core_tags',
            },
            'builtins': [
                'core.templatetags.core_tags',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database: SQLite khi chạy trên máy; đặt DATABASE_URL (Postgres, vd Neon) khi deploy
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(
        DATABASE_URL, conn_max_age=60, conn_health_checks=True,
        ssl_require=env_bool('DJANGO_DB_SSL', True),
    )}
    # An toàn cả khi dùng chuỗi kết nối qua pooler (PgBouncer) của Neon
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# File riêng tư (ảnh hoá đơn): không phục vụ qua URL tĩnh, chỉ qua view có kiểm tra quyền
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

# Nơi lưu ảnh tải lên: 'filesystem' (thư mục media/) hoặc 'db' (trong database, cho host
# không có ổ đĩa lâu dài như Render miễn phí). Xem core/storage.py
FILE_STORAGE = os.environ.get('DJANGO_FILE_STORAGE', 'filesystem').strip().lower()
STORAGES = {
    'default': {'BACKEND': 'core.storage.DatabaseStorage' if FILE_STORAGE == 'db'
                else 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage' if not DEBUG
                    else 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Khoá bí mật cho đường link /cron/<khoá>/ (máy hẹn giờ gọi vào để gửi nhắc việc, trừ tiền định kỳ)
CRON_SECRET = os.environ.get('DJANGO_CRON_SECRET', '')

# Web Push (thông báo đẩy). Tạo khoá: python manage.py generate_vapid_keys
VAPID_PUBLIC_KEY = os.environ.get('DJANGO_VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('DJANGO_VAPID_PRIVATE_KEY', '')
VAPID_SUBJECT = os.environ.get('DJANGO_VAPID_SUBJECT', 'mailto:admin@lifeos.local')
# Gửi tóm tắt việc trong ngày lúc mấy giờ (giờ địa phương)
REMINDER_DIGEST_HOUR = 8
REMINDER_MINUTES_BEFORE = 15

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Auth settings
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# django-axes: sai 5 lần (cùng username + IP) thì khoá 15 phút; đăng nhập đúng sẽ reset bộ đếm
AXES_FAILURE_LIMIT = int(os.environ.get('DJANGO_LOGIN_FAILURE_LIMIT', '5'))
AXES_COOLOFF_TIME = timedelta(minutes=int(os.environ.get('DJANGO_LOGIN_COOLOFF_MINUTES', '15')))
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'registration/locked_out.html'
# Sau reverse proxy (nginx, Render...) IP thật nằm trong X-Forwarded-For
AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] if env_bool('DJANGO_BEHIND_PROXY') else ['REMOTE_ADDR']

# Trừ tiền subscription đến hạn ngay khi user mở trang (tiện khi không có cron).
# Có cron chạy `manage.py process_subscriptions` mỗi ngày thì đặt False.
CHARGE_SUBSCRIPTIONS_ON_REQUEST = env_bool('DJANGO_CHARGE_SUBSCRIPTIONS_ON_REQUEST', True)

# Tắt để chỉ mình bạn dùng (tạo tài khoản bằng `createsuperuser`), tránh người lạ tự đăng ký
ALLOW_REGISTRATION = env_bool('DJANGO_ALLOW_REGISTRATION', True)

# Đường dẫn trang admin — nên đổi sang chuỗi khó đoán khi deploy
ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'admin/').strip('/') + '/'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Cache trong bộ nhớ tiến trình (đủ cho 1 server; khi chạy nhiều worker nên đổi sang Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'lifeos',
    }
}

# Băm mật khẩu nhanh khi chạy test (không dùng cho môi trường thật)
if 'test' in sys.argv[1:2]:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    # Client.login() trong test không truyền request nên tắt axes; test khoá đăng nhập tự bật lại
    AXES_ENABLED = False
    # DB test rollback sau mỗi test nhưng cache thì không, nên tắt cache để test không ảnh hưởng nhau
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
    # Test không cần collectstatic: bỏ cảnh báo thiếu thư mục staticfiles của whitenoise
    import warnings
    warnings.filterwarnings('ignore', message='No directory at')

# Bảo mật khi chạy production (DEBUG=False)
if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool('DJANGO_SECURE_COOKIES', True)
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', False)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '0'))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
