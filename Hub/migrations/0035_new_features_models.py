# Generated migration for new feature models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Hub', '0034_sitesettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('CREATE', 'Created'), ('UPDATE', 'Updated'), ('DELETE', 'Deleted'), ('VIEW', 'Viewed'), ('EXPORT', 'Exported'), ('IMPORT', 'Imported'), ('LOGIN', 'Login'), ('LOGOUT', 'Logout')], max_length=20)),
                ('model_name', models.CharField(help_text='Model that was modified (e.g., Product, Order)', max_length=100)),
                ('object_id', models.PositiveIntegerField(blank=True, help_text='ID of the object modified', null=True)),
                ('object_name', models.CharField(blank=True, help_text='Name/description of the object', max_length=255)),
                ('changes', models.JSONField(blank=True, default=dict, help_text='JSON of what changed (old vs new)')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('admin_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='DiscountCoupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('discount_type', models.CharField(choices=[('PERCENTAGE', 'Percentage Discount'), ('FIXED', 'Fixed Amount Discount'), ('FREE_SHIPPING', 'Free Shipping')], max_length=20)),
                ('discount_value', models.DecimalField(decimal_places=2, help_text='Percentage or fixed amount', max_digits=10)),
                ('max_discount_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Max discount cap for percentage discounts', max_digits=10, null=True)),
                ('min_purchase_amount', models.DecimalField(decimal_places=2, default=0, help_text='Minimum purchase required', max_digits=10)),
                ('max_uses', models.PositiveIntegerField(blank=True, help_text='Total uses allowed (null = unlimited)', null=True)),
                ('max_uses_per_customer', models.PositiveIntegerField(default=1, help_text='Uses per customer')),
                ('current_uses', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('EXPIRED', 'Expired')], default='ACTIVE', max_length=20)),
                ('valid_from', models.DateTimeField()),
                ('valid_until', models.DateTimeField()),
                ('applicable_categories', models.CharField(blank=True, help_text='Comma-separated category names (blank = all)', max_length=500)),
                ('applicable_products', models.CharField(blank=True, help_text='Comma-separated product IDs (blank = all)', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_coupons', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LowStockAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_id', models.PositiveIntegerField(db_index=True)),
                ('product_name', models.CharField(max_length=255)),
                ('current_stock', models.PositiveIntegerField()),
                ('threshold_stock', models.PositiveIntegerField(help_text='Stock level that triggers alert')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('SENT', 'Sent'), ('ACKNOWLEDGED', 'Acknowledged')], default='PENDING', max_length=20)),
                ('alert_sent_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SalesReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(choices=[('DAILY', 'Daily Report'), ('WEEKLY', 'Weekly Report'), ('MONTHLY', 'Monthly Report'), ('YEARLY', 'Yearly Report'), ('CUSTOM', 'Custom Report')], max_length=20)),
                ('report_date', models.DateField(db_index=True)),
                ('total_sales', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_customers', models.PositiveIntegerField(default=0)),
                ('average_order_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('top_products', models.JSONField(default=list, help_text='Top 5 products by sales')),
                ('top_categories', models.JSONField(default=list, help_text='Top 5 categories by sales')),
                ('payment_methods_breakdown', models.JSONField(default=dict, help_text='Sales by payment method')),
                ('report_data', models.JSONField(default=dict, help_text='Complete report data')),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-report_date'],
                'unique_together': {('report_type', 'report_date')},
            },
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('template_type', models.CharField(choices=[('ORDER_CONFIRMATION', 'Order Confirmation'), ('SHIPPING_UPDATE', 'Shipping Update'), ('DELIVERY_CONFIRMATION', 'Delivery Confirmation'), ('LOW_STOCK_ALERT', 'Low Stock Alert'), ('ABANDONED_CART', 'Abandoned Cart'), ('NEWSLETTER', 'Newsletter'), ('CUSTOM', 'Custom')], max_length=50)),
                ('subject', models.CharField(max_length=255)),
                ('body', models.TextField(help_text='Use {{variable}} for dynamic content')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='BulkProductImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('csv_file', models.FileField(upload_to='bulk_imports/')),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('successful_imports', models.PositiveIntegerField(default=0)),
                ('failed_imports', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('error_log', models.JSONField(blank=True, default=list, help_text='List of errors encountered')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('imported_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AdminRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('permissions', models.JSONField(default=list, help_text='List of permission codes')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AdminUserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('admin_user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='admin_role', to=settings.AUTH_USER_MODEL)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_roles_assigned', to=settings.AUTH_USER_MODEL)),
                ('role', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='Hub.adminrole')),
            ],
            options={
                'verbose_name': 'Admin User Role',
                'verbose_name_plural': 'Admin User Roles',
            },
        ),
        migrations.AddIndex(
            model_name='salesreport',
            index=models.Index(fields=['-report_date'], name='Hub_salesre_report__idx'),
        ),
        migrations.AddIndex(
            model_name='salesreport',
            index=models.Index(fields=['report_type', '-report_date'], name='Hub_salesre_report_t_idx'),
        ),
        migrations.AddIndex(
            model_name='lowstockalert',
            index=models.Index(fields=['product_id', '-created_at'], name='Hub_lowstoc_product_idx'),
        ),
        migrations.AddIndex(
            model_name='lowstockalert',
            index=models.Index(fields=['status', '-created_at'], name='Hub_lowstoc_status_idx'),
        ),
        migrations.AddIndex(
            model_name='discountcoupon',
            index=models.Index(fields=['code'], name='Hub_discount_code_idx'),
        ),
        migrations.AddIndex(
            model_name='discountcoupon',
            index=models.Index(fields=['status', 'valid_until'], name='Hub_discount_status_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['admin_user', '-timestamp'], name='Hub_activity_user_idx'),
        ),
    ]
