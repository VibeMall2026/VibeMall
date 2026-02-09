from django.core.management.base import BaseCommand
from Hub.models import Order

class Command(BaseCommand):
    help = 'Fix payment status for DELIVERED orders that still show PENDING payment'

    def handle(self, *args, **options):
        # Find all DELIVERED orders with PENDING payment status
        orders = Order.objects.filter(order_status='DELIVERED', payment_status='PENDING')
        count = orders.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✓ No orders need fixing. All DELIVERED orders have PAID payment status.'))
            return
        
        # Update all of them to PAID
        orders.update(payment_status='PAID')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Successfully updated {count} order(s) from PENDING to PAID payment status'
            )
        )
        
        # Show the fixed orders
        fixed_orders = Order.objects.filter(order_status='DELIVERED', payment_status='PAID')[:10]
        self.stdout.write('\nSample of fixed orders:')
        for order in fixed_orders:
            self.stdout.write(f'  - Order #{order.order_number}: {order.order_status} / {order.payment_status}')
