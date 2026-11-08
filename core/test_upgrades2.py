"""Kiểm thử đợt nâng cấp 2: thông báo đẩy, khôi phục sao lưu, chia tiền, lịch học, tự trích tiết kiệm,
ảnh hoá đơn, link lịch .ics."""
import io
import json
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academic.models import ClassSession, Course, Note, Semester, Tag
from core.exports import export_json
from core.models import PushSubscription, ReminderLog, UserProfile
from core.reminders import due_reminders, send_due_reminders
from finance.models import Category, Debt, SavingGoal, Subscription, Transaction, Wallet
from finance.services import charge_due_subscriptions, split_shares
from productivity.models import Goal, Task

User = get_user_model()
VAPID = {'VAPID_PUBLIC_KEY': 'pub', 'VAPID_PRIVATE_KEY': 'priv'}


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u2', password='pw-12345678')
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.wallet = Wallet.objects.create(user=self.user, name='Tiền mặt', balance=Decimal('1000000'))
        self.food = Category.objects.get(user=self.user, name='Ăn uống')
        self.salary = Category.objects.get(user=self.user, name='Lương')


# ── 1. Thông báo đẩy ──
class PushTests(Base):
    def subscribe(self, endpoint='https://push.example.com/abc'):
        return self.client.post(reverse('core:push_subscribe'),
                                json.dumps({'endpoint': endpoint, 'keys': {'p256dh': 'k', 'auth': 'a'}}),
                                content_type='application/json')

    def test_subscribe_validates_and_moves_device_between_accounts(self):
        self.assertEqual(self.subscribe('http://insecure').status_code, 400)
        self.assertEqual(self.client.post(reverse('core:push_subscribe'), '{}', content_type='application/json').status_code, 400)
        self.assertEqual(self.subscribe().status_code, 200)
        other = User.objects.create_user(username='o', password='pw-12345678')
        self.client.force_login(other)
        self.subscribe()
        self.assertEqual(PushSubscription.objects.get().user, other)
        self.client.post(reverse('core:push_unsubscribe'), json.dumps({'endpoint': 'https://push.example.com/abc'}),
                         content_type='application/json')
        self.assertFalse(PushSubscription.objects.exists())

    def test_timed_task_reminder_window(self):
        goal = Goal.objects.create(user=self.user, title='G')
        due = timezone.make_aware(datetime.combine(self.today, time(14, 0)))
        Task.objects.create(goal=goal, title='Nộp bài', due_date=self.today, due_time=time(14, 0))
        keys = lambda now: [k for k, *_ in due_reminders(self.user, now) if k.startswith('task:')]  # noqa: E731
        self.assertEqual(keys(due - timedelta(minutes=30)), [])
        self.assertEqual(len(keys(due - timedelta(minutes=10))), 1)
        self.assertEqual(keys(due + timedelta(hours=3)), [])  # quá cũ, không nhắc

    def test_morning_digest_content(self):
        goal = Goal.objects.create(user=self.user, title='G')
        Task.objects.create(goal=goal, title='Việc hôm nay', due_date=self.today)
        Task.objects.create(goal=goal, title='Cũ', due_date=self.today - timedelta(days=2))
        Debt.objects.create(user=self.user, person='Nam', amount=Decimal('50000'), due_date=self.today)
        morning = timezone.make_aware(datetime.combine(self.today, time(9, 0)))
        digest = [r for r in due_reminders(self.user, morning) if r[0].startswith('digest:')]
        self.assertEqual(len(digest), 1)
        body = digest[0][2]
        for text in ('1 việc hạn hôm nay: Việc hôm nay', '1 việc đã quá hạn', 'Cho Nam mượn còn 50.000 đ'):
            self.assertIn(text, body)
        early = timezone.make_aware(datetime.combine(self.today, time(6, 0)))
        self.assertFalse([r for r in due_reminders(self.user, early) if r[0].startswith('digest:')])

    @override_settings(**VAPID)
    def test_send_once_and_drop_expired_devices(self):
        from pywebpush import WebPushException
        self.subscribe('https://push.example.com/a')
        self.subscribe('https://push.example.com/gone')
        goal = Goal.objects.create(user=self.user, title='G')
        Task.objects.create(goal=goal, title='X', due_date=self.today)
        gone = mock.Mock(status_code=410)

        def fake(subscription_info, **kw):
            if subscription_info['endpoint'].endswith('gone'):
                raise WebPushException('gone', response=gone)

        morning = timezone.make_aware(datetime.combine(self.today, time(9, 0)))
        with mock.patch('pywebpush.webpush', side_effect=fake) as wp:
            self.assertEqual(send_due_reminders(morning), 1)
            self.assertEqual(send_due_reminders(morning), 0)  # không gửi trùng
        self.assertEqual(wp.call_count, 2)
        self.assertEqual(list(PushSubscription.objects.values_list('endpoint', flat=True)), ['https://push.example.com/a'])
        self.assertTrue(ReminderLog.objects.filter(key=f'digest:{self.today}').exists())
        payload = json.loads(wp.call_args_list[0].kwargs['data'])
        self.assertEqual(payload['url'], reverse('core:calendar'))

    @override_settings(VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='')
    def test_not_configured(self):
        self.assertEqual(self.client.post(reverse('core:push_test')).status_code, 503)
        err = io.StringIO()
        call_command('send_reminders', stderr=err)
        self.assertIn('generate_vapid_keys', err.getvalue())

    def test_generate_keys_command(self):
        out = io.StringIO()
        call_command('generate_vapid_keys', stdout=out)
        self.assertIn('DJANGO_VAPID_PUBLIC_KEY=', out.getvalue())


# ── 2. Khôi phục sao lưu ──
class RestoreTests(Base):
    def make_data(self):
        sem = Semester.objects.create(user=self.user, name='HK1', year=2026, term=Semester._meta.get_field('term').choices[0][0], is_current=True)
        course = Course.objects.create(semester=sem, name='Toán')
        ClassSession.objects.create(course=course, weekday=0, start_time=time(7), end_time=time(9))
        goal = Goal.objects.create(user=self.user, title='Học')
        Task.objects.create(goal=goal, title='Ôn', course=course, status='done')
        sub = Subscription.objects.create(user=self.user, name='Netflix', amount=Decimal('100000'), wallet=self.wallet,
                                          start_date=self.today, next_billing_date=self.today)
        charge_due_subscriptions(Subscription.objects.all())
        tag = Tag.objects.create(user=self.user, name='python')
        Note.objects.create(user=self.user, title='N', content='x').tags.add(tag)
        Debt.objects.create(user=self.user, person='Nam', amount=Decimal('200000'), wallet=self.wallet)
        self.wallet.recalculate_balance()
        return sub

    def restore(self, payload, mode='replace', confirm='KHOI PHUC'):
        f = SimpleUploadedFile('b.json', payload.encode(), content_type='application/json')
        return self.client.post(reverse('core:restore'), {'file': f, 'mode': mode, 'confirm': confirm})

    def test_replace_roundtrip(self):
        self.make_data()
        xp = self.user.profile.xp
        backup = export_json(self.user)
        Task.objects.all().delete()
        Wallet.objects.filter(pk=self.wallet.pk).update(balance=0)
        self.assertEqual(self.restore(backup).status_code, 302)
        w = Wallet.objects.get(user=self.user)
        self.assertEqual(w.balance, Decimal('700000'))  # 1tr - Netflix 100k - cho mượn 200k
        task = Task.objects.get(goal__user=self.user)
        self.assertEqual(task.course.name, 'Toán')  # khoá ngoại tạo sau vẫn được gắn
        self.assertEqual(Transaction.objects.get(user=self.user).subscription.name, 'Netflix')
        self.assertEqual(list(Note.objects.get(user=self.user).tags.values_list('name', flat=True)), ['python'])
        self.assertEqual(ClassSession.objects.filter(course__semester__user=self.user).count(), 1)
        self.assertEqual(Debt.objects.get(user=self.user).person, 'Nam')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.xp, xp)  # không cộng XP lần nữa

    def test_replace_requires_confirmation_and_bad_files_rejected(self):
        self.make_data()
        backup = export_json(self.user)
        self.restore(backup, confirm='')
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Wallet.objects.count(), 1)
        r = self.restore('not json', mode='merge')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Wallet.objects.count(), 1)
        self.restore('{"models": 5}', mode='merge')
        self.assertEqual(Wallet.objects.count(), 1)

    def test_merge_from_another_account(self):
        other = User.objects.create_user(username='old', password='pw-12345678')
        Wallet.objects.create(user=other, name='Tiền mặt', balance=Decimal('0'))  # trùng tên ví hiện có
        bank = Wallet.objects.create(user=other, name='VCB', balance=Decimal('0'))
        food = Category.objects.get(user=other, name='Ăn uống')
        Transaction.objects.create(user=other, wallet=bank, category=food, transaction_type='income', amount=Decimal('300'))
        cats = Category.objects.filter(user=self.user).count()
        self.restore(export_json(other), mode='merge')
        self.assertEqual(Category.objects.filter(user=self.user).count(), cats)  # danh mục mặc định gộp chung
        self.assertEqual(sorted(Wallet.objects.filter(user=self.user).values_list('name', flat=True)), ['Tiền mặt', 'VCB'])
        txn = Transaction.objects.get(user=self.user)
        self.assertEqual((txn.wallet.name, txn.category, txn.wallet.balance), ('VCB', self.food, Decimal('300')))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1000000'))  # ví hiện có không bị đụng

    def test_tampered_file_cannot_touch_other_users(self):
        victim = User.objects.create_user(username='victim', password='pw-12345678')
        v_wallet = Wallet.objects.create(user=victim, name='Ví nạn nhân', balance=Decimal('5000'))
        data = json.loads(export_json(self.user))
        data['models']['finance.Transaction'] = [{
            'model': 'finance.transaction', 'pk': 999,
            'fields': {'user': victim.pk, 'wallet': v_wallet.pk, 'transaction_type': 'expense', 'amount': '5000',
                       'date': str(self.today), 'note': 'hack', 'receipt': f'receipts/{victim.pk}/secret.jpg'},
        }]
        self.restore(json.dumps(data), mode='merge')
        self.assertFalse(Transaction.objects.filter(note='hack').exists())  # ví không có trong file -> bỏ qua
        data['models']['finance.Wallet'] = [{'model': 'finance.wallet', 'pk': v_wallet.pk,
                                             'fields': {'user': victim.pk, 'name': 'Ví mới', 'balance': '0', 'initial_balance': '0'}}]
        self.restore(json.dumps(data), mode='merge')
        txn = Transaction.objects.get(note='hack')
        self.assertEqual((txn.user, txn.wallet.user, txn.receipt.name), (self.user, self.user, ''))
        v_wallet.refresh_from_db()
        self.assertEqual(v_wallet.balance, Decimal('5000'))
        self.assertEqual(Transaction.objects.filter(user=victim).count(), 0)


# ── 3. Chia tiền nhóm ──
class SplitTests(Base):
    def test_shares(self):
        self.assertEqual(split_shares(Decimal('100000'), 2, True), (Decimal('33334'), [Decimal('33333')] * 2))
        self.assertEqual(split_shares(Decimal('100001'), 2, False), (Decimal('0'), [Decimal('50001'), Decimal('50000')]))

    def test_split_creates_expense_and_debts(self):
        r = self.client.post(reverse('finance:debt_split'), {
            'title': 'Lẩu', 'total': '800000', 'people': 'Nam, Lan\nMinh', 'include_me': 'on',
            'wallet': self.wallet.pk, 'category': self.food.pk, 'date': self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('200000'))
        self.assertEqual(Transaction.objects.get().amount, Decimal('200000'))
        self.assertEqual(sorted(Debt.objects.values_list('person', 'amount')),
                         [('Lan', Decimal('200000')), ('Minh', Decimal('200000')), ('Nam', Decimal('200000'))])
        self.assertEqual(self.wallet.compute_balance(), self.wallet.balance)

    def test_split_validation(self):
        self.client.post(reverse('finance:debt_split'), {'title': 'x', 'total': '1', 'people': 'A, B',
                                                         'wallet': self.wallet.pk, 'date': self.today.isoformat()})
        self.assertFalse(Debt.objects.exists())


# ── 4. Lịch học ──
class ScheduleTests(Base):
    def setUp(self):
        super().setUp()
        self.sem = Semester.objects.create(user=self.user, name='HK1', year=2026, term=Semester._meta.get_field('term').choices[0][0], is_current=True)
        self.course = Course.objects.create(semester=self.sem, name='Giải tích')

    def test_add_session_and_show_today(self):
        r = self.client.post(reverse('academic:schedule'), {'course': self.course.pk, 'weekday': self.today.weekday(),
                                                            'start_time': '07:00', 'end_time': '09:00', 'room': 'A2'})
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse('core:dashboard'))
        self.assertContains(r, 'Hôm nay học gì')
        self.assertContains(r, 'Giải tích')
        r = self.client.get(reverse('core:calendar'))
        self.assertTrue(any(e['kind'] == 'class' for d in r.context['agenda'] for e in d['events']))

    def test_end_after_start_and_semester_window(self):
        r = self.client.post(reverse('academic:schedule'), {'course': self.course.pk, 'weekday': 0,
                                                            'start_time': '09:00', 'end_time': '08:00'})
        self.assertEqual(r.status_code, 200)
        s = ClassSession.objects.create(course=self.course, weekday=0, start_time=time(7), end_time=time(9))
        monday = date(2026, 11, 9)
        self.assertTrue(s.runs_on(monday))
        self.sem.start_date, self.sem.end_date = date(2026, 1, 1), date(2026, 5, 31)
        self.sem.save()
        s.refresh_from_db()
        self.assertFalse(s.runs_on(monday))

    def test_old_semester_without_dates_hidden(self):
        from academic.services_schedule import sessions_on
        self.sem.is_current = False
        self.sem.save()
        ClassSession.objects.create(course=self.course, weekday=self.today.weekday(), start_time=time(7), end_time=time(9))
        self.assertEqual(sessions_on(self.user, self.today), [])


# ── 5. Tự trích tiết kiệm ──
class AutoSaveTests(Base):
    def test_income_moves_percent_to_goal_and_awards_xp_once(self):
        goal = SavingGoal.objects.create(user=self.user, name='Laptop', target_amount=Decimal('1500000'))
        Subscription.objects.create(user=self.user, name='Lương', transaction_type='income', amount=Decimal('10000000'),
                                    wallet=self.wallet, category=self.salary, saving_goal=goal, saving_percent=10,
                                    start_date=self.today, next_billing_date=self.today - timedelta(days=31),
                                    billing_cycle='monthly')
        xp = self.user.profile.xp
        charge_due_subscriptions(Subscription.objects.all())  # 2 kỳ: bù kỳ trước + kỳ này
        goal.refresh_from_db()
        self.assertEqual(goal.current_amount, Decimal('2000000'))
        self.assertTrue(goal.is_completed)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.xp - xp, 50)

    def test_form_rules(self):
        goal = SavingGoal.objects.create(user=self.user, name='Quỹ', target_amount=Decimal('1000'))
        base = {'name': 'X', 'amount': '1000', 'wallet': self.wallet.pk, 'billing_cycle': 'monthly',
                'start_date': self.today.isoformat(), 'next_billing_date': (self.today + timedelta(days=3)).isoformat()}
        self.client.post(reverse('finance:subscription_list'), {**base, 'transaction_type': 'expense', 'saving_goal': goal.pk, 'saving_percent': 10})
        self.client.post(reverse('finance:subscription_list'), {**base, 'transaction_type': 'income', 'saving_goal': goal.pk, 'saving_percent': 0})
        self.assertFalse(Subscription.objects.exists())
        self.client.post(reverse('finance:subscription_list'), {**base, 'transaction_type': 'income', 'saving_goal': goal.pk, 'saving_percent': 20})
        self.assertEqual(Subscription.objects.get().saving_percent, 20)


# ── 6. Ảnh hoá đơn ──
class ReceiptTests(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.tmp)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def image(self, size=(3000, 2000), fmt='JPEG', exif=True):
        from PIL import Image
        img = Image.new('RGB', size, (200, 30, 30))
        buf = io.BytesIO()
        kwargs = {}
        if exif:
            ex = Image.Exif()
            ex[0x010F] = 'CameraMaker'
            ex[0x8825] = {2: (21.0, 1.0, 0.0)}  # GPS
            kwargs['exif'] = ex.tobytes()
        img.save(buf, fmt, **kwargs)
        return SimpleUploadedFile('r.jpg', buf.getvalue(), content_type='image/jpeg')

    def add(self, upload):
        return self.client.post(reverse('finance:transaction_list'), {
            'transaction_type': 'expense', 'amount': '50000', 'wallet': self.wallet.pk, 'date': self.today.isoformat(),
            'note': 'Ăn trưa', 'receipt': upload,
        })

    def test_upload_resized_exif_stripped_private(self):
        from PIL import Image
        self.assertEqual(self.add(self.image()).status_code, 302)
        txn = Transaction.objects.get()
        with txn.receipt.open('rb') as f:
            img = Image.open(f)
            self.assertLessEqual(max(img.size), 1600)
            self.assertEqual(len(img.getexif()), 0)
        self.assertTrue(txn.receipt.path.startswith(self.tmp))  # đúng thư mục riêng tư đang cấu hình
        url = reverse('finance:transaction_receipt', args=[txn.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertNotIn('/media/', txn.receipt.name)
        other = User.objects.create_user(username='spy', password='pw-12345678')
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_rejects_non_images_and_cleans_up_files(self):
        self.add(SimpleUploadedFile('x.jpg', b'not an image', content_type='image/jpeg'))
        self.assertFalse(Transaction.objects.exists())
        self.add(self.image(exif=False))
        txn = Transaction.objects.get()
        storage, name = txn.receipt.storage, txn.receipt.name
        self.assertTrue(storage.exists(name))
        self.client.post(reverse('finance:transaction_edit', args=[txn.pk]), {
            'transaction_type': 'expense', 'amount': '50000', 'wallet': self.wallet.pk, 'date': self.today.isoformat(),
            'note': 'x', 'receipt': self.image(size=(100, 100), exif=False),
        })
        txn.refresh_from_db()
        self.assertFalse(storage.exists(name))  # ảnh cũ bị thay -> xoá
        new_name = txn.receipt.name
        self.client.post(reverse('finance:transaction_delete', args=[txn.pk]))
        self.assertFalse(storage.exists(new_name))


# ── 7. Link lịch .ics ──
class IcsTests(Base):
    def test_token_feed_and_reset(self):
        self.client.post(reverse('core:calendar_token_reset'))
        token = UserProfile.objects.get(user=self.user).calendar_token
        self.assertGreaterEqual(len(token), 20)
        goal = Goal.objects.create(user=self.user, title='G', deadline=self.today + timedelta(days=3))
        Task.objects.create(goal=goal, title='Họp nhóm, chuẩn bị; slide', due_date=self.today, due_time=time(14, 30))
        sem = Semester.objects.create(user=self.user, name='HK', year=2026, term=Semester._meta.get_field('term').choices[0][0], is_current=True)
        ClassSession.objects.create(course=Course.objects.create(semester=sem, name='Vật lý ' * 12), weekday=2,
                                    start_time=time(7), end_time=time(9))
        self.client.logout()
        r = self.client.get(reverse('core:calendar_feed', args=[token]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r['Content-Type'].startswith('text/calendar'))
        body = r.content.decode()
        self.assertTrue(body.startswith('BEGIN:VCALENDAR\r\n'))
        self.assertIn('SUMMARY:Họp nhóm\\, chuẩn bị\\; slide', body)
        from datetime import timezone as dt_tz
        self.assertIn('DTSTART:' + timezone.make_aware(datetime.combine(self.today, time(14, 30))).astimezone(
            dt_tz.utc).strftime('%Y%m%dT%H%M%SZ'), body)
        self.assertIn('RRULE:FREQ=WEEKLY;UNTIL=', body)
        self.assertTrue(all(len(line.encode()) <= 75 for line in body.split('\r\n')))
        self.assertEqual(self.client.get(reverse('core:calendar_feed', args=['x' * 32])).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(reverse('core:calendar_token_reset'))
        self.assertEqual(self.client.get(reverse('core:calendar_feed', args=[token])).status_code, 404)
        self.client.post(reverse('core:calendar_token_reset'), {'action': 'disable'})
        self.assertEqual(UserProfile.objects.get(user=self.user).calendar_token, '')


class FormHygieneTests(Base):
    def test_pages_have_no_duplicate_ids(self):
        import re
        from collections import Counter
        for name in ('finance:transaction_list', 'finance:debt_list', 'academic:gpa_tracker', 'library:shelf'):
            html = self.client.get(reverse(name)).content.decode()
            dup = [k for k, v in Counter(re.findall(r'\sid="([^"]+)"', html)).items() if v > 1]
            self.assertEqual(dup, [], name)

    def test_transaction_form_defaults_to_local_date(self):
        from datetime import timezone as dt_tz
        # 23:30 UTC = 6:30 sáng hôm sau ở Việt Nam: form phải điền ngày Việt Nam
        fake = datetime(2026, 3, 9, 23, 30, tzinfo=dt_tz.utc)
        with mock.patch('django.utils.timezone.now', return_value=fake):
            html = self.client.get(reverse('finance:transaction_list')).content.decode()
        self.assertIn('value="2026-03-10"', html)


# ── Deploy: ảnh lưu trong database, đường link cron ──
class DatabaseStorageTests(Base):
    def test_save_open_delete_roundtrip(self):
        from core.models import StoredFile
        from core.storage import DatabaseStorage
        store = DatabaseStorage()
        name = store.save('avatars/a.png', SimpleUploadedFile('a.png', b'PNGDATA', content_type='image/png'))
        name2 = store.save('avatars/a.png', SimpleUploadedFile('a.png', b'OTHER'))
        self.assertNotEqual(name, name2)
        self.assertEqual(store.open(name).read(), b'PNGDATA')
        self.assertEqual(store.size(name), 7)
        self.assertEqual(store.url(name), '/media/avatars/a.png')
        store.delete(name)
        self.assertFalse(store.exists(name))
        self.assertEqual(StoredFile.objects.count(), 1)

    def test_names_always_use_forward_slashes(self):
        from core.storage import DatabaseStorage
        name = DatabaseStorage().save('library\\covers\\c.jpg', SimpleUploadedFile('c.jpg', b'X'))
        self.assertEqual(name, 'library/covers/c.jpg')
        self.assertTrue(DatabaseStorage().exists('library/covers/c.jpg'))

    def test_private_files_are_not_served_publicly(self):
        from core.storage import DatabaseStorage
        from core.views_deploy import db_media
        from django.http import Http404
        from django.test import RequestFactory
        DatabaseStorage(private=True).save('receipts/1/x.jpg', SimpleUploadedFile('x.jpg', b'SECRET'))
        DatabaseStorage().save('avatars/ok.png', SimpleUploadedFile('ok.png', b'PUBLIC', content_type='image/png'))
        rf = RequestFactory()
        with self.assertRaises(Http404):
            db_media(rf.get('/'), 'receipts/1/x.jpg')
        resp = db_media(rf.get('/'), 'avatars/ok.png')
        self.assertEqual((resp.status_code, resp.content, resp['Content-Type']), (200, b'PUBLIC', 'image/png'))
        with self.assertRaises(ValueError):
            DatabaseStorage(private=True).url('receipts/1/x.jpg')


SECRET = 'cron-secret-for-tests-1234567890'


class CronTests(Base):
    @override_settings(CRON_SECRET=SECRET)
    def test_wrong_or_missing_secret_is_404(self):
        self.client.logout()
        self.assertEqual(self.client.post('/cron/wrong-secret-wrong-secret-xx/').status_code, 404)
        with override_settings(CRON_SECRET=''):
            self.assertEqual(self.client.post('/cron//').status_code, 404)

    @override_settings(CRON_SECRET=SECRET, **VAPID)
    def test_runs_reminders_and_subscriptions(self):
        self.client.logout()
        Subscription.objects.create(user=self.user, name='Netflix', amount=Decimal('100000'), wallet=self.wallet,
                                    category=self.food, transaction_type='expense', billing_cycle='monthly',
                                    start_date=self.today, next_billing_date=self.today)
        with mock.patch('core.reminders.send_due_reminders', return_value=2) as sent:
            resp = self.client.post(f'/cron/{SECRET}/')
        self.assertEqual(resp.json(), {'ok': True, 'charged': 1, 'reminders': 2})
        sent.assert_called_once()
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('900000'))
