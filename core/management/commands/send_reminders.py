import time

from django.core.management.base import BaseCommand

from core.push import is_configured
from core.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Gửi thông báo nhắc việc (Web Push). --loop: chạy liên tục, kiểm tra mỗi phút."

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='Chạy liên tục (Ctrl+C để dừng)')
        parser.add_argument('--interval', type=int, default=60, help='Số giây giữa hai lần kiểm tra (mặc định 60)')

    def handle(self, *args, **options):
        if not is_configured():
            self.stderr.write(self.style.ERROR(
                'Chưa có khoá VAPID. Chạy "python manage.py generate_vapid_keys" và thêm vào .env.'))
            return
        while True:
            count = send_due_reminders()
            if count or not options['loop']:
                self.stdout.write(self.style.SUCCESS(f'Đã gửi {count} lời nhắc.'))
            if not options['loop']:
                return
            time.sleep(max(options['interval'], 10))
