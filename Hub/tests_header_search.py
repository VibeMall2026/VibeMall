from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserProfile


@override_settings(SECURE_SSL_REDIRECT=False)
class HeaderSearchDropdownTests(TestCase):
    """
    The suggestions panel is styled entirely by header-custom.css: absolute
    positioning, a white card, and display:none until it opens. That file was
    linked only from header.html, while partials/vm_copy_header.html renders the
    same panel and is included from base.html - so typing in the search box on
    those pages dropped unstyled product rows straight into the page flow.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="hs_user", password="pass12345")
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})

    def _pages(self):
        """Pages that render the copy header. Logged in - some require it."""
        self.client.login(username="hs_user", password="pass12345")
        for name in ('shop', 'cart', 'order_list'):
            yield name, self.client.get(reverse(name))

    def test_every_page_with_the_panel_also_loads_its_styles(self):
        for name, response in self._pages():
            with self.subTest(page=name):
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                if 'SearchResults' not in html:
                    continue  # page does not render the panel at all
                self.assertIn(
                    'header-custom.css', html,
                    f'{name} renders the search suggestions panel without the '
                    f'stylesheet that positions and hides it',
                )

    def test_stylesheet_hides_the_panel_until_it_opens(self):
        """
        Without display:none the panel is visible the moment results land in it.
        """
        from pathlib import Path

        from django.conf import settings

        css = Path(settings.BASE_DIR, 'Hub', 'static', 'assets', 'css',
                   'header-custom.css').read_text(encoding='utf-8')
        rule = css.split('.search-results {', 1)[1].split('}', 1)[0]
        self.assertIn('display: none', rule)
        self.assertIn('position: absolute', rule)
        self.assertIn('.search-results.is-open', css)
