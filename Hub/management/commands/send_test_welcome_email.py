from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from Hub.email_utils import send_welcome_email_with_terms


class Command(BaseCommand):
    help = 'Send the welcome email with Terms & Conditions PDF to an existing user for testing.'

    def add_arguments(self, parser):
        parser.add_argument('--email', help='Registered user email address to receive the test email.')
        parser.add_argument('--username', help='Registered username to receive the test email.')

    def handle(self, *args, **options):
        email = (options.get('email') or '').strip()
        username = (options.get('username') or '').strip()

        if not email and not username:
            raise CommandError('Provide either --email or --username.')

        User = get_user_model()
        lookup = {'email__iexact': email} if email else {'username__iexact': username}

        try:
            user = User.objects.get(**lookup)
        except User.DoesNotExist as exc:
            raise CommandError('No user found for the supplied identifier.') from exc
        except User.MultipleObjectsReturned as exc:
            raise CommandError('Multiple users matched the supplied identifier. Use a more specific value.') from exc

        sent = send_welcome_email_with_terms(user, request=None)
        if not sent:
            raise CommandError('Welcome email send failed. Check email logs and server logs for details.')

        self.stdout.write(self.style.SUCCESS(f'Welcome email sent to {user.email}'))