from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0054_add_subcategory_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='subcategory',
            name='icon_class',
            field=models.CharField(blank=True, help_text="FontAwesome icon class (e.g., 'fas fa-tshirt')", max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='icon_image',
            field=models.ImageField(blank=True, help_text='Upload sub-category icon image (PNG recommended)', null=True, upload_to='subcategory_icons/'),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='background_gradient',
            field=models.CharField(default='linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%)', help_text='CSS gradient for icon background', max_length=200),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='icon_color',
            field=models.CharField(default='#0288d1', help_text='Icon color (hex code) - Only used for FontAwesome icons', max_length=20),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='icon_size',
            field=models.PositiveIntegerField(default=48, help_text='Icon size in pixels (used for image width/height or FontAwesome size)'),
        ),
    ]
