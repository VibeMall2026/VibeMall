from django.db import migrations, models


def update_contact_email(apps, schema_editor):
    SiteSettings = apps.get_model('Hub', 'SiteSettings')
    SiteSettings.objects.filter(contact_email='support@vibemall.com').update(
        contact_email='info.vibemall@gmail.com'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('Hub', '0080_rtocase_rtohistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='contact_email',
            field=models.EmailField(default='info.vibemall@gmail.com', max_length=254),
        ),
        migrations.RunPython(update_contact_email, migrations.RunPython.noop),
    ]
