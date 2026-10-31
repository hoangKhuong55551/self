from decimal import Decimal

from django.conf import settings
from django.db import migrations
from django.db.models import Sum

from finance.defaults import create_default_categories


def forwards(apps, schema_editor):
    Wallet = apps.get_model('finance', 'Wallet')
    Category = apps.get_model('finance', 'Category')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    # Giữ nguyên số dư hiện tại: ban đầu = số dư - (thu - chi)
    for wallet in Wallet.objects.all():
        def total(kind):
            return wallet.transactions.filter(transaction_type=kind).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        wallet.initial_balance = wallet.balance - (total('income') - total('expense'))
        wallet.save(update_fields=['initial_balance'])

    for user in User.objects.all():
        if not Category.objects.filter(user=user).exists():
            create_default_categories(Category, user.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_wallet_initial_balance_transfer_goal_link'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
