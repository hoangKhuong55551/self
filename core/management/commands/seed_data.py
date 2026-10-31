from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from finance.models import Wallet, Category, Transaction, Budget, Subscription, WishlistItem
from productivity.models import Goal, Task, Habit, HabitLog
from academic.models import Semester, Course, Tag, Note, CodeSnippet

User = get_user_model()


class Command(BaseCommand):
    help = "Khoi tao du lieu mau (seed data) sinh dong cho demo do an."

    def handle(self, *args, **options):
        username = 'student'
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': 'student@university.edu.vn',
                'first_name': 'Hoang',
                'last_name': 'Khuong',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        user.set_password('admin123')
        user.save()

        # Gamification profile
        profile = user.profile
        profile.level = 3
        profile.xp = 420
        profile.hp = 85
        profile.longest_streak = 14
        profile.save()

        today = timezone.now().date()

        # 1. FINANCE SEED
        w_bank, _ = Wallet.objects.get_or_create(
            user=user, name='Vietcombank',
            defaults={'balance': Decimal('12500000'), 'currency': 'VND'}
        )
        w_cash, _ = Wallet.objects.get_or_create(
            user=user, name='Vi Tien Mat',
            defaults={'balance': Decimal('1500000'), 'currency': 'VND'}
        )
        w_momo, _ = Wallet.objects.get_or_create(
            user=user, name='Vi MoMo',
            defaults={'balance': Decimal('850000'), 'currency': 'VND'}
        )

        cat_food, _ = Category.objects.get_or_create(user=user, name='An uong', type='expense', defaults={'color': '#ef4444'})
        cat_study, _ = Category.objects.get_or_create(user=user, name='Hoc tap & Sach', type='expense', defaults={'color': '#3b82f6'})
        cat_salary, _ = Category.objects.get_or_create(user=user, name='Luong & Freelance', type='income', defaults={'color': '#10b981'})
        cat_tech, _ = Category.objects.get_or_create(user=user, name='Thiet bi cong nghe', type='expense', defaults={'color': '#8b5cf6'})

        # Transactions
        Transaction.objects.get_or_create(
            user=user, wallet=w_bank, category=cat_salary, transaction_type='income', amount=Decimal('8000000'),
            date=today - timedelta(days=5), note='Thanh toan du an Web Freelance'
        )
        Transaction.objects.get_or_create(
            user=user, wallet=w_cash, category=cat_food, transaction_type='expense', amount=Decimal('45000'),
            date=today, note='An trua com tam'
        )
        Transaction.objects.get_or_create(
            user=user, wallet=w_momo, category=cat_study, transaction_type='expense', amount=Decimal('220000'),
            date=today - timedelta(days=1), note='Mua sach Clean Code tieng Viet'
        )

        # Budgets
        Budget.objects.get_or_create(
            user=user, category=cat_food, month=today.month, year=today.year,
            defaults={'amount': Decimal('3000000')}
        )
        Budget.objects.get_or_create(
            user=user, category=cat_study, month=today.month, year=today.year,
            defaults={'amount': Decimal('1500000')}
        )

        # Subscriptions
        Subscription.objects.get_or_create(
            user=user, name='Spotify Premium Sinh Vien', wallet=w_momo, category=cat_study,
            defaults={
                'amount': Decimal('29500'), 'billing_cycle': 'monthly',
                'start_date': today - timedelta(days=60), 'next_billing_date': today + timedelta(days=12),
                'url': 'https://spotify.com'
            }
        )
        Subscription.objects.get_or_create(
            user=user, name='VPS Cloudflare & DigitalOcean', wallet=w_bank, category=cat_study,
            defaults={
                'amount': Decimal('140000'), 'billing_cycle': 'monthly',
                'start_date': today - timedelta(days=120), 'next_billing_date': today + timedelta(days=3),
                'url': 'https://digitalocean.com'
            }
        )

        # Wishlist
        WishlistItem.objects.get_or_create(
            user=user, name='Ban phim co Keychron K2 Pro',
            defaults={
                'price': Decimal('2100000'), 'priority': 3, 'wallet': w_bank,
                'target_date': today + timedelta(days=30), 'description': 'Switch Brown go em tay de code do an'
            }
        )

        # 2. PRODUCTIVITY SEED
        g1, _ = Goal.objects.get_or_create(
            user=user, title='Bao ve do an tot nghiep Django dat diem A/A+',
            defaults={'deadline': today + timedelta(days=45), 'color': '#6366f1'}
        )
        Task.objects.get_or_create(
            goal=g1, title='Thiet ke database schema va signals lien thong',
            defaults={'status': 'done', 'quadrant': 'do', 'estimated_pomodoros': 4}
        )
        Task.objects.get_or_create(
            goal=g1, title='Xay dung giao dien Dashboard va Pomodoro Timer',
            defaults={'status': 'in_progress', 'quadrant': 'do', 'estimated_pomodoros': 3}
        )
        Task.objects.get_or_create(
            goal=g1, title='Chuan bi slide thuyet trinh va quay video demo',
            defaults={'status': 'todo', 'quadrant': 'schedule', 'estimated_pomodoros': 5}
        )
        g1.recalculate_progress()

        # Habits
        h_code, _ = Habit.objects.get_or_create(
            user=user, name='Code Django / LeetCode 1 gio',
            defaults={'frequency': 'daily', 'target_per_day': 1, 'icon': '💻'}
        )
        h_read, _ = Habit.objects.get_or_create(
            user=user, name='Doc 20 trang sach chuyen nganh',
            defaults={'frequency': 'daily', 'target_per_day': 1, 'icon': '📚'}
        )
        h_gym, _ = Habit.objects.get_or_create(
            user=user, name='Chay bo / The thao 30 phut',
            defaults={'frequency': 'daily', 'target_per_day': 1, 'icon': '🏃'}
        )

        # Tao log 7 ngay qua cho habit
        for i in range(7):
            past_date = today - timedelta(days=i)
            HabitLog.objects.get_or_create(habit=h_code, date=past_date, defaults={'count': 1, 'completed': True})
            if i % 2 == 0:
                HabitLog.objects.get_or_create(habit=h_read, date=past_date, defaults={'count': 1, 'completed': True})

        # 3. ACADEMIC SEED
        sem, _ = Semester.objects.get_or_create(
            user=user, name='Hoc ky 1 (2025 - 2026)', year=2025, term='spring',
            defaults={'is_current': True}
        )
        Course.objects.get_or_create(
            semester=sem, name='Phat trien Ung dung Web voi Python/Django',
            defaults={'code': 'IT4409', 'credits': 3, 'grade': 4.0, 'is_completed': True}
        )
        Course.objects.get_or_create(
            semester=sem, name='Kien truc Phan mem & Design Patterns',
            defaults={'code': 'IT4420', 'credits': 3, 'grade': 3.7, 'is_completed': True}
        )
        Course.objects.get_or_create(
            semester=sem, name='He thong Co so Du lieu Nang cao',
            defaults={'code': 'IT3090', 'credits': 3, 'grade': 3.5, 'is_completed': True}
        )

        tag_django, _ = Tag.objects.get_or_create(user=user, name='Django', defaults={'color': '#092e20'})
        tag_db, _ = Tag.objects.get_or_create(user=user, name='Database', defaults={'color': '#336791'})

        n1, _ = Note.objects.get_or_create(
            user=user, title='Kien truc Loose Coupling voi Django Signals',
            defaults={
                'content': 'Django Signals cho phep cac Model tuong tac bat dong bo ma khong can import truc tiep lan nhau, giup codebase dat chuan Single Responsibility Principle (SRP).',
                'is_pinned': True
            }
        )
        n1.tags.add(tag_django)

        cs1, _ = CodeSnippet.objects.get_or_create(
            user=user, title='F() Expression chong Race Condition trong Django ORM',
            defaults={
                'language': 'python',
                'code': 'from django.db.models import F\nWallet.objects.filter(pk=wallet_id).update(balance=F("balance") - amount)',
                'description': 'Dam bao toan ven so du vi khi co nhieu giao dich xay ra dong thoi tai muc Database.'
            }
        )
        cs1.tags.add(tag_django, tag_db)

        self.stdout.write(self.style.SUCCESS(
            f"Khoi tao seed data thanh cong! Tai khoan demo:\n"
            f"User: {username}\n"
            f"Pass: admin123\n"
            f"URL : http://127.0.0.1:8000/"
        ))
