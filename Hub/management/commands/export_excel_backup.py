"""
Django Management Command to Export Data to Excel
Usage: python manage.py export_excel_backup
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from Hub.models import Order, OrderItem, Product, User as CustomUser
import pandas as pd
from datetime import datetime
import os

class Command(BaseCommand):
    help = 'Export User, Order, Payment and Product data to Excel backup files'

    def _excel_safe(self, df):
        for col in df.columns:
            if pd.api.types.is_datetime64tz_dtype(df[col]):
                df[col] = df[col].dt.tz_localize(None)
        return df

    def _auto_adjust_sheet_columns(self, worksheet):
        if worksheet.max_column == 0:
            return

        for column_cells in worksheet.iter_cols(min_row=1, max_row=worksheet.max_row, min_col=1, max_col=worksheet.max_column):
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                if cell.value is None:
                    continue
                try:
                    max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    continue

            adjusted_width = min(max(max_length + 2, 12), 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    def _auto_adjust_workbook(self, writer):
        for worksheet in writer.book.worksheets:
            self._auto_adjust_sheet_columns(worksheet)

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='./backups/excel',
            help='Directory to save Excel files'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        
        # Create backup directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Export all data
            self.stdout.write("🔄 Exporting User Data...")
            self.export_users(output_dir, timestamp)
            
            self.stdout.write("🔄 Exporting Order Data...")
            self.export_orders(output_dir, timestamp)
            
            self.stdout.write("🔄 Exporting Payment Data...")
            self.export_payments(output_dir, timestamp)
            
            self.stdout.write("🔄 Exporting Product Data...")
            self.export_products(output_dir, timestamp)
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Excel backup completed successfully!\n'
                f'📁 Location: {output_dir}\n'
                f'⏰ Timestamp: {timestamp}'
            ))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during export: {str(e)}')
            )

    def export_users(self, output_dir, timestamp):
        """Export user data to Excel"""
        try:
            users = User.objects.all().values(
                'id', 'username', 'email', 'first_name', 'last_name',
                'is_active', 'date_joined', 'last_login'
            )
            
            df = pd.DataFrame(users)
            
            # Add additional user profile data if available
            user_profiles = []
            for user in User.objects.all():
                try:
                    profile = user.userprofile
                    user_profiles.append({
                        'user_id': user.id,
                        'phone': profile.phone if hasattr(profile, 'phone') else '',
                        'city': profile.city if hasattr(profile, 'city') else '',
                        'state': profile.state if hasattr(profile, 'state') else '',
                    })
                except:
                    pass
            
            if user_profiles:
                profiles_df = pd.DataFrame(user_profiles)
                df = df.merge(profiles_df, left_on='id', right_on='user_id', how='left')

            df = self._excel_safe(df)
            
            file_path = f"{output_dir}/users_backup_{timestamp}.xlsx"
            
            # Create Excel file with formatting
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Users', index=False)
                self._auto_adjust_workbook(writer)
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Users exported: {file_path}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Error exporting users: {str(e)}')
            )

    def export_orders(self, output_dir, timestamp):
        """Export order data to Excel"""
        try:
            orders = Order.objects.all().values(
                'id', 'order_number', 'user__username', 'user__email',
                'total_amount', 'payment_status', 'order_status',
                'created_at', 'updated_at', 'delivery_date'
            )
            
            df_orders = pd.DataFrame(orders)
            df_orders = self._excel_safe(df_orders)
            
            # Export to Excel with multiple sheets
            file_path = f"{output_dir}/orders_backup_{timestamp}.xlsx"
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Orders Summary
                df_orders.to_excel(writer, sheet_name='Orders', index=False)
                
                # Sheet 2: Order Details (Items)
                order_items = OrderItem.objects.all().values(
                    'order__order_number', 'product__name', 'quantity',
                    'product_price', 'subtotal'
                )
                df_items = pd.DataFrame(order_items)
                df_items = self._excel_safe(df_items)
                df_items.to_excel(writer, sheet_name='Order Items', index=False)
                
                # Sheet 3: Order Status Summary
                status_summary = Order.objects.values('order_status').annotate(
                    count=Count('id')
                )
                df_status = pd.DataFrame(status_summary)
                df_status = self._excel_safe(df_status)
                df_status.to_excel(writer, sheet_name='Status Summary', index=False)
                self._auto_adjust_workbook(writer)
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Orders exported: {file_path}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Error exporting orders: {str(e)}')
            )

    def export_payments(self, output_dir, timestamp):
        """Export payment/transaction data to Excel"""
        try:
            payments = Order.objects.all().values(
                'id', 'order_number', 'user__username',
                'total_amount', 'payment_status', 'payment_method',
                'created_at'
            )
            
            df_payments = pd.DataFrame(payments)
            df_payments = self._excel_safe(df_payments)
            
            file_path = f"{output_dir}/payments_backup_{timestamp}.xlsx"
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: All Payments
                df_payments.to_excel(writer, sheet_name='Payments', index=False)
                
                # Sheet 2: Payment Summary
                payment_summary = Order.objects.values('payment_status').annotate(
                    count=Count('id'),
                    total_amount=Sum('total_amount')
                )
                df_summary = pd.DataFrame(payment_summary)
                df_summary = self._excel_safe(df_summary)
                df_summary.to_excel(writer, sheet_name='Payment Summary', index=False)
                self._auto_adjust_workbook(writer)
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Payments exported: {file_path}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Error exporting payments: {str(e)}')
            )

    def export_products(self, output_dir, timestamp):
        """Export product data to Excel"""
        try:
            products = Product.objects.all().values(
                'id', 'name', 'category', 'price',
                'stock', 'sold', 'is_active'
            )
            
            df_products = pd.DataFrame(products)
            df_products = self._excel_safe(df_products)
            
            file_path = f"{output_dir}/products_backup_{timestamp}.xlsx"
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: All Products
                df_products.to_excel(writer, sheet_name='Products', index=False)
                
                # Sheet 2: Stock Status
                stock_status = Product.objects.values('category').annotate(
                    total_products=Count('id'),
                    total_stock=Sum('stock'),
                    total_sold=Sum('sold')
                )
                df_stock = pd.DataFrame(stock_status)
                df_stock = self._excel_safe(df_stock)
                df_stock.to_excel(writer, sheet_name='Stock Status', index=False)
                
                # Sheet 3: Low Stock Products
                low_stock = Product.objects.filter(stock__lte=10).values(
                    'name', 'category', 'stock', 'price'
                )
                df_low = pd.DataFrame(low_stock)
                df_low = self._excel_safe(df_low)
                df_low.to_excel(writer, sheet_name='Low Stock Alert', index=False)
                self._auto_adjust_workbook(writer)
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Products exported: {file_path}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Error exporting products: {str(e)}')
            )
