import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Cấp quyền admin cho tài khoản DJANGO_SUPERUSER_USERNAME (dùng trên host không có shell như Render Free). "
        "Tài khoản chưa tồn tại thì tạo mới nếu có DJANGO_SUPERUSER_PASSWORD. Không đặt biến thì bỏ qua."
    )

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        if not username:
            return
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
            if len(password) < 10:
                self.stderr.write(f'Chưa có tài khoản "{username}". Đăng ký trên web trước, '
                                  'hoặc đặt DJANGO_SUPERUSER_PASSWORD (ít nhất 10 ký tự) để tạo mới.')
                return
            User.objects.create_superuser(username=username, email=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''),
                                          password=password)
            self.stdout.write(self.style.SUCCESS(f'Đã tạo tài khoản admin "{username}".'))
            return
        if user.is_staff and user.is_superuser:
            self.stdout.write(f'"{username}" đã là admin.')
            return
        user.is_staff = user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        self.stdout.write(self.style.SUCCESS(f'Đã cấp quyền admin cho "{username}".'))
