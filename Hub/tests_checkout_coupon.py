import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Cart, Coupon, Product, UserProfile


def _tiny_image(name="test.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class CheckoutCouponWiringTests(TestCase):
    """
    The desktop coupon box was dead markup: checkout_desktop_alt.html ships no
    <script>, and updateFinalTotal() was called six times without ever being
    defined. These guard both regressions.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="co_buyer", password="pass12345")
        # The checkout template reads user_profile.mobile_number; a user with
        # no profile makes it blow up before any of the coupon markup renders.
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Coupon Product", image=_tiny_image("c.gif"), price=Decimal("1200.00"),
            stock=10, is_active=True,
        )
        Cart.objects.create(user=self.user, product=self.product, quantity=1)

        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code="SAVE10",
            description="10% off your order",
            discount_type="PERCENTAGE",
            discount_value=Decimal("10.00"),
            min_purchase_amount=Decimal("100.00"),
            is_active=True,
            valid_from=now - timezone.timedelta(days=1),
            valid_to=now + timezone.timedelta(days=30),
        )
        self.client.login(username="co_buyer", password="pass12345")

    def _page(self):
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    # ── the reported bug ─────────────────────────────────────────────────────

    def test_available_coupons_button_has_a_handler(self):
        html = self._page()
        self.assertIn('id="viewAvailableCoupons"', html)
        # Before the fix this button existed with no JS referencing it at all.
        self.assertIn("viewCouponsBtn.addEventListener('click'", html)

    def test_apply_and_remove_buttons_have_handlers(self):
        html = self._page()
        self.assertIn("applyCouponBtn.addEventListener('click'", html)
        self.assertIn("removeCouponBtn.addEventListener('click'", html)

    def test_panel_and_list_targets_exist(self):
        html = self._page()
        self.assertIn('id="availableCouponsPanel"', html)
        self.assertIn('id="availableCouponsList"', html)
        self.assertIn('function renderAvailableCoupons()', html)

    # ── the undefined-function bug ───────────────────────────────────────────

    def test_update_final_total_is_defined(self):
        html = self._page()
        self.assertIn('function updateFinalTotal()', html)

    def test_no_call_to_update_final_total_inside_the_mobile_block(self):
        """
        The mobile IIFE calls updateMobileFinalTotal; two listeners still
        pointed at the desktop name and threw ReferenceError on click.
        """
        html = self._page()
        # The mobile block is the one that defines updateMobileFinalTotal. The
        # desktop block legitimately references updateFinalTotal, so the check
        # has to be scoped rather than run against the whole page.
        mobile = next(
            block for block in html.split('</script>')
            if 'function updateMobileFinalTotal' in block
        )
        self.assertNotIn("'change', updateFinalTotal", mobile)
        self.assertNotIn("'input', updateFinalTotal", mobile)

    def test_every_call_site_resolves(self):
        html = self._page()
        called = len(re.findall(r'\bupdateFinalTotal\s*\(\)', html))
        defined = len(re.findall(r'function\s+updateFinalTotal\s*\(', html))
        self.assertGreater(called, 0)
        self.assertEqual(defined, 1, "updateFinalTotal must be defined exactly once")

    # ── template comments must not reach the browser ─────────────────────────

    def test_no_template_comment_text_is_rendered(self):
        """
        {# #} is single-line only: a multi-line one is not a comment at all and
        Django prints it as page copy. One had been left above the phone field
        and showed up mid-page for shoppers.
        """
        html = self._page()
        for leak in ('firstof, not', 'VariableDoesNotExist', 'ignore_failures',
                     'a failed lookup inside a filter'):
            self.assertNotIn(leak, html, f"template comment leaked: {leak!r}")
        # the field the comment documented must still be there
        self.assertIn('id="phoneField"', html)

    # ── only one implementation may wire the coupon controls ─────────────────

    def test_only_one_coupon_implementation_claims_the_controls(self):
        """
        base.html loads assets/js/checkout-coupons.js, which binds the same ids
        as the inline block. Two click handlers on #viewAvailableCoupons toggle
        the panel open and shut again, which reads as "the button does nothing".
        Both sides must respect the shared claim flag.
        """
        html = self._page()
        self.assertIn('window.__vmCheckoutCouponsInitialized = true;', html)
        self.assertIn('const couponsAlreadyWired', html)
        # every coupon listener must sit behind the claim
        for guarded in ('!couponsAlreadyWired && viewCouponsBtn',
                        '!couponsAlreadyWired && applyCouponBtn',
                        '!couponsAlreadyWired && removeCouponBtn'):
            self.assertIn(guarded, html)

    def test_inline_block_renders_before_the_external_coupon_script(self):
        """The claim flag only helps if the inline block gets to set it first."""
        html = self._page()
        inline_at = html.find('DESKTOP COUPONS + FINAL TOTAL')
        external_at = html.find('checkout-coupons.js')
        self.assertNotEqual(inline_at, -1)
        self.assertNotEqual(external_at, -1)
        self.assertLess(inline_at, external_at)

    # ── the Apply button must actually look like a button ────────────────────

    def test_available_coupon_card_apply_button_is_styled(self):
        """
        .vm-checkout-d-coupon-card button only set min-width, so Apply rendered
        as a bare browser default next to the styled Remove button on the
        applied-coupon card. It must carry the same treatment.
        """
        from pathlib import Path

        from django.conf import settings

        css = Path(settings.BASE_DIR, 'Hub', 'static', 'assets', 'css',
                   'checkout-desktop-alt.css').read_text(encoding='utf-8')
        rule = css.split('.vm-checkout-d-coupon-card button {', 1)
        self.assertEqual(len(rule), 2, "no rule for the coupon-card button")
        block = rule[1].split('}', 1)[0]
        for prop in ('background', 'color', 'height', 'text-transform'):
            self.assertIn(prop, block, f"Apply button is missing {prop}")

    def test_coupon_card_markup_matches_the_stylesheet(self):
        """The renderer's class names have to be the ones the CSS targets."""
        html = self._page()
        self.assertIn('vm-checkout-d-coupon-card', html)
        self.assertIn('vm-checkout-d-coupon-meta', html)

    # ── data plumbing ────────────────────────────────────────────────────────

    def test_available_coupons_payload_is_rendered(self):
        html = self._page()
        self.assertIn('id="available-coupons-data"', html)
        self.assertIn('SAVE10', html)

    def test_coupon_totals_targets_exist(self):
        html = self._page()
        for element_id in ('coupon_discount_row', 'coupon_discount_amount',
                           'final_total_display', 'appliedCouponId'):
            self.assertIn(f'id="{element_id}"', html)

    # ── the API the JS calls ─────────────────────────────────────────────────

    def test_validate_coupon_endpoint_applies_the_coupon(self):
        response = self.client.post(
            reverse('validate_coupon'),
            data='{"code": "SAVE10", "cart_total": 1200}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['code'], 'SAVE10')
        self.assertEqual(Decimal(str(data['discount_amount'])), Decimal('120.00'))

    def test_validate_coupon_rejects_unknown_code(self):
        response = self.client.post(
            reverse('validate_coupon'),
            data='{"code": "NOPE", "cart_total": 1200}',
            content_type='application/json',
        )
        self.assertFalse(response.json()['valid'])

    def test_validate_coupon_enforces_minimum_purchase(self):
        self.coupon.min_purchase_amount = Decimal('5000.00')
        self.coupon.save()
        response = self.client.post(
            reverse('validate_coupon'),
            data='{"code": "SAVE10", "cart_total": 1200}',
            content_type='application/json',
        )
        self.assertFalse(response.json()['valid'])
