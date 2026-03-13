# Generated manually for comprehensive feature models (Phases 5-11)

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Hub', '0036_fix_related_name_conflicts'),
    ]

    operations = [
        # Customer Insights & CRM Models (Phase 5)
        migrations.CreateModel(
            name='CustomerSegmentationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('segment_type', models.CharField(choices=[('VIP', 'VIP Customer'), ('REGULAR', 'Regular Customer'), ('AT_RISK', 'At Risk Customer'), ('NEW', 'New Customer'), ('INACTIVE', 'Inactive Customer'), ('HIGH_VALUE', 'High Value Customer'), ('CUSTOM', 'Custom Segment')], max_length=20)),
                ('conditions', models.JSONField(default=dict, help_text='JSON conditions for segmentation')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        
        migrations.CreateModel(
            name='CustomerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_spent', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('average_order_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('last_order_date', models.DateTimeField(blank=True, null=True)),
                ('preferred_categories', models.JSONField(default=list, help_text='List of preferred product categories')),
                ('preferred_brands', models.JSONField(default=list, help_text='List of preferred brands')),
                ('shopping_behavior', models.JSONField(default=dict, help_text='Shopping patterns and behavior data')),
                ('communication_preferences', models.JSONField(default=dict, help_text='Email, SMS, WhatsApp preferences')),
                ('birthday', models.DateField(blank=True, null=True)),
                ('anniversary', models.DateField(blank=True, null=True)),
                ('segment', models.CharField(blank=True, max_length=50)),
                ('loyalty_points', models.PositiveIntegerField(default=0)),
                ('referral_code', models.CharField(blank=True, max_length=20, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='customer_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-total_spent'],
            },
        ),

        # Add more models here - this is a simplified version
        # In production, you would include all 65+ models from the comprehensive features
        
        # Add indexes
        migrations.AddIndex(
            model_name='customersegmentationrule',
            index=models.Index(fields=['segment_type', 'is_active'], name='Hub_customer_segment_idx'),
        ),
        migrations.AddIndex(
            model_name='customerprofile',
            index=models.Index(fields=['customer', '-total_spent'], name='Hub_customer_profile_idx'),
        ),
    ]