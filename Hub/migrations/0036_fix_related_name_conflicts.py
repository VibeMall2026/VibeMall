# Generated manually to fix related_name conflicts

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0035_new_features_models'),
    ]

    operations = [
        # Fix AdminUserRole.assigned_by related_name conflict
        migrations.AlterField(
            model_name='adminuserrole',
            name='assigned_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_roles_assigned', to=settings.AUTH_USER_MODEL),
        ),
    ]