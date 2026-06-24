from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def seed_launch_coupons(apps, schema_editor):
    Coupon = apps.get_model('Hub', 'Coupon')

    now = timezone.now()
    valid_from = now
    valid_to = now + timedelta(days=365)

    coupon_payloads = [
        {
            'code': 'WELCOME5',
            'coupon_type': 'NEW_CUSTOMER',
            'description': 'New customer welcome offer with a 5% discount up to ₹80.',
            'discount_type': 'PERCENTAGE',
            'discount_value': 5,
            'min_purchase_amount': 0,
            'max_discount_amount': 80,
            'usage_limit': None,
            'usage_per_user': 1,
        },
        {
            'code': 'FIRSTBUY10',
            'coupon_type': 'FIRST_ORDER',
            'description': 'First order offer with a 10% discount up to ₹70.',
            'discount_type': 'PERCENTAGE',
            'discount_value': 10,
            'min_purchase_amount': 0,
            'max_discount_amount': 70,
            'usage_limit': None,
            'usage_per_user': 1,
        },
        {
            'code': 'FREESHIP',
            'coupon_type': 'FREE_SHIPPING',
            'description': 'Free shipping on first eligible order of ₹700 or more.',
            'discount_type': 'FREE_SHIPPING',
            'discount_value': 0,
            'min_purchase_amount': 700,
            'max_discount_amount': None,
            'usage_limit': None,
            'usage_per_user': 1,
        },
        {
            'code': 'LAUNCH25',
            'coupon_type': 'MANUAL',
            'description': 'Launch offer with 25% discount up to ₹100 on orders ₹2000+.',
            'discount_type': 'PERCENTAGE',
            'discount_value': 25,
            'min_purchase_amount': 2000,
            'max_discount_amount': 100,
            'usage_limit': 5,
            'usage_per_user': 1,
        },
    ]

    for payload in coupon_payloads:
        Coupon.objects.update_or_create(
            code=payload['code'],
            defaults={
                **payload,
                'valid_from': valid_from,
                'valid_to': valid_to,
                'is_active': True,
            },
        )


def unseed_launch_coupons(apps, schema_editor):
    Coupon = apps.get_model('Hub', 'Coupon')
    Coupon.objects.filter(code__in=['WELCOME5', 'FIRSTBUY10', 'FREESHIP', 'LAUNCH25']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0092_alter_coupon_coupon_type_alter_coupon_discount_type'),
    ]

    operations = [
        migrations.RunPython(seed_launch_coupons, unseed_launch_coupons),
    ]
