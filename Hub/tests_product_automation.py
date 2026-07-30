"""
Regression tests for the Telegram -> AI -> approval pipeline.

Runs without an AI key: the rule-based path is exercised directly, and the AI
client is stubbed where a provider response is needed. Media is written to a
temporary MEDIA_ROOT so the real media tree is never touched.

    python manage.py test Hub.tests_product_automation
"""

from __future__ import annotations

import io
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image, ImageDraw

from Hub.automation import pipeline
from Hub.automation.ai.extraction import category_keys, category_options
from Hub.automation.ingest import ingest, settle_seconds
from Hub.automation.parsing.rules import extract_rules, strip_price_mentions
from Hub.automation.publisher import (
    PublishError,
    build_care_info,
    build_description,
    next_sku,
    publish,
    sku_prefix,
)
from Hub.automation.sources.base import IncomingMedia, IncomingProduct
from Hub.automation.sources.telegram_bot import BOT_COMMAND
from Hub.views import normalize_sku
from Hub.models import (
    CategoryIcon,
    Product,
    ProductDraft,
    ProductDraftImage,
    ProductImage,
    ProductSEO,
    ProductVariant,
    Reel,
)

MEDIA = tempfile.mkdtemp(prefix='vm-automation-tests-')


def photo(shade: int = 60, footer: int = 0) -> bytes:
    """A product photo, optionally with a supplier code strip at the bottom."""
    width, height = 600, 800
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([170, 70, 430, height - footer - 5], fill=(shade, 20, 90))
    if footer:
        draw.text((14, height - footer + 20), 's-558186268', fill=(30, 30, 30))
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=92)
    return buffer.getvalue()


def clip() -> bytes:
    return b'\x00\x00\x00 ftypmp42' + b'\x00' * 3000


def send(chat: str, n: int, *, text: str = '', media=None, group: str = '') -> ProductDraft | None:
    return ingest(
        IncomingProduct(
            source='telegram',
            message_id=f'{chat}:{n}',
            chat_id=chat,
            text=text,
            media=media or [],
            group_id=group,
        )
    )


def image_media(n: int, *, shade: int = 60, footer: int = 0) -> IncomingMedia:
    return IncomingMedia(data=photo(shade, footer), filename=f'p{n}.jpg', source_file_id=f'f{n}')


def video_media(n: int) -> IncomingMedia:
    return IncomingMedia(
        data=clip(), filename=f'v{n}.mp4', source_file_id=f'v{n}',
        kind=IncomingMedia.KIND_VIDEO, duration=12, width=720, height=1280,
    )


def age(draft: ProductDraft, seconds: int) -> None:
    """Backdate a draft so time-gated logic can be exercised deterministically."""
    ProductDraft.objects.filter(pk=draft.pk).update(
        last_message_at=timezone.now() - timedelta(seconds=seconds)
    )


@override_settings(MEDIA_ROOT=MEDIA, AUTOMATION_AI_PROVIDER='none')
class IngestGroupingTests(TestCase):
    """Messages belonging to one product must land in one draft."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_album_parts_merge(self):
        for n in range(1, 6):
            send('-1', n, media=[image_media(n, shade=60 + n * 10)], group='album-1')
        self.assertEqual(ProductDraft.objects.count(), 1)
        self.assertEqual(ProductDraft.objects.get().images.count(), 5)

    def test_photos_sent_individually_then_description(self):
        for n in range(1, 16):
            send('-2', n, media=[image_media(n, shade=40 + n * 8)])
        send('-2', 16, text='Purple Sharara Suit\nPrice 1999')
        self.assertEqual(ProductDraft.objects.count(), 1)
        draft = ProductDraft.objects.get()
        self.assertEqual(draft.images.count(), 15)
        self.assertIn('Purple Sharara', draft.raw_text)

    def test_description_then_photos(self):
        send('-3', 1, text='Red Lehenga\nPrice 3499')
        for n in range(2, 12):
            send('-3', n, media=[image_media(n, shade=40 + n * 8)])
        self.assertEqual(ProductDraft.objects.count(), 1)
        self.assertEqual(ProductDraft.objects.get().images.count(), 10)

    def test_second_description_starts_new_product(self):
        send('-4', 1, media=[image_media(1)])
        send('-4', 2, text='Product A\nPrice 999')
        send('-4', 3, text='Product B\nPrice 1499')
        self.assertEqual(ProductDraft.objects.count(), 2)

    def test_pause_between_products_splits_them(self):
        send('-5', 1, media=[image_media(1)])
        first = ProductDraft.objects.get()
        send('-5', 2, text='Product A\nPrice 999')
        age(first, 120)
        send('-5', 3, media=[image_media(2, shade=200)])
        self.assertEqual(ProductDraft.objects.count(), 2)

    def test_description_closes_the_product_even_with_no_pause(self):
        """
        The supplier's rhythm is photos -> description -> next product, sent
        back to back. The photo after a description opens the next item, so it
        must not be swept into the finished draft however fast it follows.
        """
        send('-5b', 1, media=[image_media(1, shade=40)])
        send('-5b', 2, media=[image_media(2, shade=60)])
        send('-5b', 3, text='Black Georgette Kurti\nPrice 1999')
        send('-5b', 4, media=[image_media(3, shade=200)])
        send('-5b', 5, media=[image_media(4, shade=220)])
        send('-5b', 6, text='Cream Sharara Suit\nPrice 2499')

        self.assertEqual(ProductDraft.objects.count(), 2)
        black, cream = ProductDraft.objects.order_by('created_at')
        self.assertEqual(black.images.count(), 2)
        self.assertEqual(cream.images.count(), 2)
        self.assertIn('Georgette', black.raw_text)
        self.assertIn('Sharara', cream.raw_text)

    def test_videos_join_the_product(self):
        send('-6', 1, media=[image_media(1)])
        send('-6', 2, media=[video_media(2)])
        send('-6', 3, text='Suit with reel\nPrice 1299')
        draft = ProductDraft.objects.get()
        self.assertEqual(draft.images.count(), 1)
        self.assertEqual(draft.videos.count(), 1)

    def test_redelivered_message_is_ignored(self):
        send('-7', 1, text='Kurti\nPrice 799', media=[image_media(1)])
        again = send('-7', 1, text='Kurti\nPrice 799', media=[image_media(1)])
        self.assertIsNone(again)
        self.assertEqual(ProductDraft.objects.count(), 1)

    def test_identical_photos_are_deduplicated(self):
        for n in range(1, 4):
            send('-8', n, media=[IncomingMedia(data=photo(60), filename=f'{n}.jpg', source_file_id=f'd{n}')])
        send('-8', 9, text='Kurti\nPrice 799')
        draft = ProductDraft.objects.get()
        age(draft, 300)
        pipeline.process_once()
        draft.refresh_from_db()
        self.assertEqual(draft.images.count(), 1, 'identical photos should collapse to one')

    def test_bot_commands_are_not_products(self):
        for command in ('/start', '/help@VibeMallBot', '/stop'):
            self.assertTrue(BOT_COMMAND.match(command))
        for real in ('Cotton Kurti', 'Price 799', '/start now please'):
            self.assertFalse(BOT_COMMAND.match(real))


@override_settings(MEDIA_ROOT=MEDIA, AUTOMATION_AI_PROVIDER='none')
class WorkerGatingTests(TestCase):
    """A draft must not be processed while more messages may still arrive."""

    def test_draft_is_held_while_supplier_is_still_sending(self):
        send('-10', 1, media=[image_media(1)])
        draft = ProductDraft.objects.get()
        age(draft, 15)
        self.assertIsNone(pipeline.claim_next(), 'claimed too early')
        age(draft, 300)
        self.assertIsNotNone(pipeline.claim_next())

    def test_completed_draft_is_claimed_without_waiting(self):
        """
        Once the description lands the product is closed, so the long quiet
        window no longer applies. Claiming promptly is also what stops the next
        product's photos from ever reaching this draft.
        """
        send('-10b', 1, media=[image_media(1)])
        send('-10b', 2, text='Kurti\nPrice 799')
        draft = ProductDraft.objects.get()
        age(draft, settle_seconds() + 2)
        self.assertIsNotNone(pipeline.claim_next(), 'a finished draft should not wait')

    def test_failed_draft_backs_off_then_fails_permanently(self):
        send('-11', 1, text='Kurti\nPrice 799')
        draft = ProductDraft.objects.get()
        age(draft, 300)
        claimed = pipeline.claim_next()
        pipeline.reschedule(claimed, 'boom')
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, ProductDraft.STATUS_QUEUED)
        self.assertIsNotNone(claimed.next_attempt_at)

        claimed.attempts = 99
        claimed.save(update_fields=['attempts'])
        pipeline.reschedule(claimed, 'boom again')
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, ProductDraft.STATUS_FAILED)

    def test_stale_claim_is_reclaimed(self):
        send('-12', 1, text='Kurti\nPrice 799')
        draft = ProductDraft.objects.get()
        draft.status = ProductDraft.STATUS_PROCESSING
        draft.claimed_at = timezone.now() - timedelta(hours=2)
        draft.save()
        self.assertEqual(pipeline.reclaim_stale(), 1)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ProductDraft.STATUS_QUEUED)


class RuleExtractionTests(TestCase):
    """The deterministic pass is what guards prices and sizes."""

    def test_single_price_is_the_original_price(self):
        for text, expected in (
            ('Cotton Kurti\nPrice 799', '799'),
            ('Saree\n1299/-', '1299'),
            ('Gown\nRs. 2,499', '2499'),
        ):
            rules = extract_rules(text)
            self.assertIsNone(rules.price, f'selling price should be blank for: {text}')
            self.assertEqual(str(rules.old_price), expected)

    def test_mrp_and_offer_price_map_to_both_fields(self):
        rules = extract_rules('Sharara\nMRP Rs. 2999\nOffer Price 1499/-')
        self.assertEqual(str(rules.price), '1499')
        self.assertEqual(str(rules.old_price), '2999')

    def test_sizes_ignore_stray_letters_and_measurements(self):
        rules = extract_rules("Women's Premium Kurti\nAvailable in M XXL")
        self.assertEqual(rules.sizes, ['M', 'XXL'], "apostrophe-s must not become size S")

        rules = extract_rules('Suit\nSizes: XS, S, M, L, XL\nSize chart: 34 36 38 40')
        self.assertEqual(rules.sizes, ['XS', 'S', 'M', 'L', 'XL'], 'chart values are not sizes')

    def test_fabric_block_and_bottomwear_label(self):
        rules = extract_rules(
            'Catalog Name:*Georgette Kurti*\n'
            'Kurta Fabric: Georgette\nBottomwear Fabric: Georgette\nDupatta Fabric: Vichitra'
        )
        self.assertEqual(rules.name, 'Georgette Kurti')
        self.assertEqual(rules.fabric_components.get('bottom_fabric'), 'Georgette')
        self.assertEqual(rules.fabric_components.get('dupatta_fabric'), 'Vichitra')

    def test_compound_colour_is_not_split(self):
        rules = extract_rules('Gown\nColors Red, Navy Blue')
        self.assertIn('Navy Blue', rules.colors)
        self.assertNotIn('Navy', rules.colors)

    def test_prices_are_stripped_from_copy(self):
        cleaned = strip_price_mentions('Kurti\nPrice 799\nEmbroidery work\nRs. 1299 only')
        self.assertNotIn('799', cleaned)
        self.assertNotIn('1299', cleaned)
        self.assertIn('Embroidery work', cleaned)


class ContentLayoutTests(TestCase):
    """Description and Care Guide must not duplicate or leak markup."""

    RECORD = {
        'description': 'Crafted for festive gatherings.',
        'highlights': ['Three-piece set', 'Pink floral embroidery'],
        'product_type': 'Kurta Pant Set', 'fabric': 'Georgette', 'material': 'Silk Blend',
        'sleeve_type': '3/4 Sleeves', 'neck_type': 'Round Neck', 'fit': 'Regular Fit',
        'occasion': 'Festive', 'wash_care': 'Dry Clean', 'package_contents': '1 Kurta',
        'country_of_origin': 'India',
    }

    def test_description_is_plain_text(self):
        text = build_description(self.RECORD)
        self.assertNotIn('<', text, 'markup would be escaped and shown literally')
        self.assertIn('Key Highlights', text)
        self.assertIn('Sleeve Type: 3/4 Sleeves', text)

    def test_nothing_follows_the_occasion_line(self):
        text = build_description(self.RECORD)
        tail = text.split('Occasion: Festive')[-1].strip()
        self.assertEqual(tail, '', 'Occasion closes the specification block')

    def test_fabric_is_not_repeated_in_the_description(self):
        text = build_description(self.RECORD)
        self.assertNotIn('Fabric: Georgette', text, 'fabric belongs to the Care Guide')
        self.assertNotIn('Material:', text)

    def test_care_guide_reads_as_instructions(self):
        care = build_care_info(self.RECORD)
        self.assertIn('Dry Clean', care)
        self.assertIn('Do not bleach', care)
        self.assertIn('Dry in shade', care)
        self.assertIn('Storage', care)
        self.assertIn('1 Kurta', care)
        self.assertNotIn('Sleeve Type', care, 'styling attributes are not care instructions')
        self.assertNotIn('Occasion', care)

    def test_care_guide_does_not_repeat_one_fabric_per_component(self):
        care = build_care_info({
            'fabric': 'Georgette', 'material': 'Georgette', 'top_fabric': 'Georgette',
            'bottom_fabric': 'Georgette', 'dupatta_fabric': 'Georgette',
        })
        self.assertEqual(care.count('Georgette'), 1)

    def test_delicate_fabric_is_never_sent_to_a_machine(self):
        care = build_care_info({'fabric': 'Georgette', 'work_type': 'Embroidered'})
        self.assertIn('Dry clean recommended', care)
        self.assertNotIn('Machine wash', care)
        self.assertIn('from the reverse', care, 'embroidery needs iron protection')

    def test_cotton_takes_an_ordinary_machine_wash(self):
        care = build_care_info({'fabric': 'Cotton'})
        self.assertIn('Machine wash cold', care)


class CategorySourceTests(TestCase):
    """The AI must choose from the categories this store actually has."""

    def test_options_come_from_the_storefront_categories(self):
        CategoryIcon.objects.create(name='Women Wear', category_key='Women Wear', is_active=True)
        CategoryIcon.objects.create(name='Mens Wear', category_key='Means Wear', is_active=True)
        CategoryIcon.objects.create(name='Retired', category_key='OLD', is_active=False)

        keys = category_keys()
        self.assertIn('Women Wear', keys)
        self.assertIn('Means Wear', keys)
        self.assertNotIn('OLD', keys, 'inactive categories are not sold')
        self.assertNotIn(
            'FURNITURE', keys,
            "Product.CATEGORY_CHOICES is a stale template list — offering it left "
            "a kurti with no correct answer, so the model picked Furniture",
        )

    def test_labels_are_supplied_because_keys_are_not_self_explanatory(self):
        CategoryIcon.objects.create(name='Mens Wear', category_key='Means Wear', is_active=True)
        self.assertIn(('Means Wear', 'Mens Wear'), category_options())

    def test_falls_back_when_no_categories_are_configured(self):
        self.assertTrue(category_keys(), 'never hand the model an empty enum')


class AutoSkuTests(TestCase):
    """SKUs are serialised per sub-category so codes stay traceable."""

    def test_prefix_is_readable_letters_from_the_sub_category(self):
        self.assertEqual(sku_prefix('Kurtis'), 'KURTIS')
        self.assertEqual(sku_prefix('Top_Pallazo set'), 'TOPPALLAZO')
        self.assertEqual(sku_prefix('lehenga choli'), 'LEHENGACHO')
        self.assertEqual(sku_prefix('Necklace&Chain'), 'NECKLACECH')

    def test_unset_sub_category_still_yields_a_code(self):
        self.assertEqual(sku_prefix(''), 'PROD')
        self.assertTrue(next_sku('').startswith('PROD-'))

    def test_serial_starts_at_one_and_increments(self):
        self.assertEqual(next_sku('Kurtis'), 'KURTIS-0001')
        Product.objects.create(name='A', price=10, sku='KURTIS-0001')
        self.assertEqual(next_sku('Kurtis'), 'KURTIS-0002')

    def test_serial_continues_from_the_highest_not_the_count(self):
        Product.objects.create(name='A', price=10, sku='KURTIS-0007')
        self.assertEqual(
            next_sku('Kurtis'), 'KURTIS-0008',
            'deleting a product must not re-issue a code that was already used',
        )

    def test_sub_categories_are_numbered_independently(self):
        Product.objects.create(name='A', price=10, sku='KURTIS-0001')
        self.assertEqual(next_sku('Sarees'), 'SAREES-0001')


class PricingTests(TestCase):
    """Cost + margin = selling price, recomputed server-side."""

    def _record(self, **post):
        from django.test import RequestFactory

        from Hub.views_product_automation import _apply_pricing

        request = RequestFactory().post('/', post)
        record = {}
        _apply_pricing(request, record)
        return record

    def test_selling_price_is_cost_plus_margin(self):
        record = self._record(base_price='600', margin='299')
        self.assertEqual(record['price'], '899')
        self.assertEqual(record['margin'], '299')
        self.assertEqual(record['base_price'], '600')

    def test_a_posted_total_never_overrides_the_sum(self):
        record = self._record(base_price='600', margin='299', price='1')
        self.assertEqual(
            record['price'], '899',
            'a stale total from the browser must not book the wrong profit',
        )

    def test_margin_defaults_to_zero(self):
        self.assertEqual(self._record(base_price='500')['price'], '500')

    def test_rupee_symbols_and_separators_are_tolerated(self):
        self.assertEqual(self._record(base_price='₹1,200', margin='300')['price'], '1500')

    def test_cost_is_derived_when_only_a_selling_price_is_known(self):
        from django.test import RequestFactory

        from Hub.views_product_automation import _apply_pricing

        record = {'price': '899'}
        _apply_pricing(RequestFactory().post('/', {'margin': '299'}), record)
        self.assertEqual(record['base_price'], '600')
        self.assertEqual(record['price'], '899', 'the typed selling price stands')


class SkuTests(TestCase):
    """``Product.sku`` is unique but nullable — blank must not collide."""

    def test_blank_skus_do_not_collide(self):
        self.assertIsNone(normalize_sku(''))
        self.assertIsNone(normalize_sku('   '))

    def test_taken_sku_is_suffixed(self):
        Product.objects.create(name='A', price=10, sku='T-1')
        self.assertEqual(normalize_sku('T-1'), 'T-1-1')

    def test_a_product_keeps_its_own_sku_when_edited(self):
        product = Product.objects.create(name='A', price=10, sku='T-1')
        self.assertEqual(
            normalize_sku('T-1', exclude_pk=product.pk), 'T-1',
            'editing a product must not rename its own SKU on every save',
        )


@override_settings(MEDIA_ROOT=MEDIA, AUTOMATION_AI_PROVIDER='none')
class PublishTests(TestCase):
    """Approval writes the full set of live rows, atomically."""

    def setUp(self):
        self.user = User.objects.create_user('pub_admin', is_staff=True, is_superuser=True)

    def _ready_draft(self, chat='-20', footer=0, with_video=False):
        media = [image_media(1, footer=footer)]
        if with_video:
            media.append(video_media(2))
        send(chat, 1, media=media)
        send(chat, 2, text='Purple Sharara Suit\nMRP 2999\nOffer Price 1499\n'
                           'Sizes M L XL\nFabric Georgette\nStyle code T-1\nStock 30')
        draft = ProductDraft.objects.get()
        age(draft, 300)
        pipeline.process_once()
        draft.refresh_from_db()
        return draft

    def test_publish_creates_product_images_variants_and_seo(self):
        draft = self._ready_draft()
        draft.category = 'GENZ_TRENDS'
        draft.sub_category = 'Sharara'
        draft.save()

        product = publish(draft, user=self.user)

        self.assertEqual(product.price, 1499)
        self.assertEqual(product.old_price, 2999)
        self.assertEqual(product.discount_percent, 50)
        self.assertEqual(product.category, 'GENZ_TRENDS')
        self.assertTrue(product.image, 'main image must be set')
        self.assertTrue(ProductVariant.objects.filter(product_id=product.id).exists())
        self.assertTrue(ProductSEO.objects.filter(product_id=product.id).exists())

        draft.refresh_from_db()
        self.assertEqual(draft.status, ProductDraft.STATUS_PUBLISHED)
        self.assertEqual(draft.published_product_id, product.id)

    def test_publish_requires_a_category_and_a_price(self):
        draft = self._ready_draft()
        with self.assertRaises(PublishError):
            publish(draft, user=self.user)

        draft.category = 'GENZ_TRENDS'
        record = dict(draft.parsed)
        record['price'] = ''
        draft.parsed = record
        draft.save()
        with self.assertRaises(PublishError):
            publish(draft, user=self.user)

    def test_failure_midway_rolls_everything_back(self):
        """The 'no partial products' guarantee: a late failure undoes the lot."""
        from unittest.mock import patch

        draft = self._ready_draft()
        draft.category = 'GENZ_TRENDS'
        draft.save()

        before_products = Product.objects.count()
        before_images = ProductImage.objects.count()
        before_variants = ProductVariant.objects.count()

        # create_seo runs after the product, its images and its variants, so
        # failing there proves the whole transaction unwinds.
        with patch('Hub.automation.publisher.create_seo', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                publish(draft, user=self.user)

        self.assertEqual(Product.objects.count(), before_products, 'product rolled back')
        self.assertEqual(ProductImage.objects.count(), before_images, 'images rolled back')
        self.assertEqual(ProductVariant.objects.count(), before_variants, 'variants rolled back')
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ProductDraft.STATUS_PUBLISHED)

    def test_video_becomes_a_reel(self):
        draft = self._ready_draft(with_video=True)
        draft.category = 'GENZ_TRENDS'
        draft.save()
        product = publish(draft, user=self.user)
        reels = Reel.objects.filter(product=product)
        self.assertEqual(reels.count(), 1)
        self.assertTrue(reels.first().video_file)

    def test_supplier_code_strip_is_cropped_out(self):
        draft = self._ready_draft(footer=70)
        image = draft.images.first()
        self.assertGreater(image.suggested_crop_bottom_px, 0, 'code strip should be detected')
        self.assertEqual(image.crop_bottom_px, image.suggested_crop_bottom_px)

    def test_return_policy_is_applied(self):
        draft = self._ready_draft()
        draft.category = 'GENZ_TRENDS'
        record = dict(draft.parsed)
        record.update({'is_returnable': False, 'return_days': 0, 'return_policy': 'Final sale'})
        draft.parsed = record
        draft.save()
        product = publish(draft, user=self.user)
        self.assertFalse(product.is_returnable)
        self.assertEqual(product.return_policy, 'Final sale')
        self.assertNotIn('COD', product.get_payment_methods_list())

    def test_hero_colour_is_listed_first(self):
        """
        The storefront tags the main thumbnail with the product's first colour.
        If the hero is not that colour the colour filter hides it on load — the
        bug where a published product showed no main image at all.
        """
        draft = self._ready_draft(chat='-24')
        draft.category = 'GENZ_TRENDS'
        record = dict(draft.parsed)
        record['colors'] = ['Red', 'Cream']
        draft.parsed = record
        draft.save()

        main = draft.images.filter(role='main').first() or draft.images.first()
        main.role = 'main'
        main.color = 'Cream'
        main.save(update_fields=['role', 'color'])

        product = publish(draft, user=self.user)
        self.assertTrue(
            product.color.startswith('Cream'),
            f"hero colour must lead the list, got {product.color!r}",
        )
        self.assertIn('Red', product.color, 'other colours are kept')

    def test_colourless_hero_leaves_the_colour_order_alone(self):
        draft = self._ready_draft(chat='-25')
        draft.category = 'GENZ_TRENDS'
        record = dict(draft.parsed)
        record['colors'] = ['Red', 'Cream']
        draft.parsed = record
        draft.save()
        draft.images.update(color='')

        product = publish(draft, user=self.user)
        self.assertEqual(product.color, 'Red, Cream')

    def test_duplicate_repost_is_flagged(self):
        draft = self._ready_draft(chat='-21')
        draft.category = 'GENZ_TRENDS'
        draft.save()
        publish(draft, user=self.user)

        send('-22', 1, media=[image_media(1)])
        send('-22', 2, text='Purple Sharara Suit\nMRP 2999\nOffer Price 1499\nStyle code T-1')
        second = ProductDraft.objects.exclude(pk=draft.pk).get()
        age(second, 300)
        pipeline.process_once()
        second.refresh_from_db()
        self.assertEqual(second.status, ProductDraft.STATUS_DUPLICATE)
        self.assertIsNotNone(second.duplicate_of_id)


@override_settings(MEDIA_ROOT=MEDIA, AUTOMATION_AI_PROVIDER='none')
class AdminScreenTests(TestCase):
    """Every admin route must render and every action must work."""

    def setUp(self):
        self.user = User.objects.create_user('screen_admin', is_staff=True, is_superuser=True)
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)
        CategoryIcon.objects.create(name='GenZ Trends', category_key='GENZ_TRENDS', is_active=True)

        send('-30', 1, media=[image_media(1, footer=70)])
        send('-30', 2, text='Purple Sharara Suit\nMRP 2999\nOffer Price 1499\nSizes M L\nStock 5')
        self.draft = ProductDraft.objects.get()
        age(self.draft, 300)
        pipeline.process_once()
        self.draft.refresh_from_db()

    def get(self, url):
        return self.client.get(url, secure=True)

    def post(self, url, data):
        return self.client.post(url, data, secure=True)

    def test_queue_and_review_render(self):
        self.assertEqual(self.get('/admin-panel/product-drafts/').status_code, 200)
        self.assertEqual(self.get('/admin-panel/product-drafts/?status=all').status_code, 200)
        self.assertEqual(self.get('/admin-panel/product-drafts/status/').status_code, 200)

        response = self.get(f'/admin-panel/product-drafts/{self.draft.pk}/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', 'replace')
        for needle in ('Select Category', 'Approve &amp; Publish', 'Delete Draft',
                       'Return available', 'Crop', 'role_'):
            self.assertIn(needle, body, f'review screen missing {needle!r}')

    def test_image_role_override_keeps_one_of_each(self):
        # The draft is already PENDING, so new messages would start their own
        # draft rather than join this one; stage the extra images directly.
        for n in (2, 3):
            extra = ProductDraftImage(draft=self.draft, order=n)
            extra.image.save(f'extra{n}.jpg', ContentFile(photo(40 + n * 40)), save=True)
        images = list(self.draft.images.all().order_by('id'))
        self.assertGreaterEqual(len(images), 3)

        self.post(
            f'/admin-panel/product-drafts/{self.draft.pk}/',
            {
                'action': 'save_crops',
                f'role_{images[0].pk}': 'main',
                f'role_{images[1].pk}': 'description',
                f'role_{images[2].pk}': 'main',
            },
        )
        roles = [i.role for i in self.draft.images.all().order_by('id')]
        self.assertEqual(roles[0], 'main')
        self.assertEqual(roles[1], 'description')
        self.assertEqual(roles[2], 'gallery', 'a second main must be demoted')

    def test_approve_publishes(self):
        response = self.post(
            f'/admin-panel/product-drafts/{self.draft.pk}/',
            {
                'action': 'approve', 'category': 'GENZ_TRENDS', 'sub_category': 'Sharara',
                'name': 'Purple Sharara Suit', 'price': '1499', 'old_price': '2999',
                'stock': '5', 'sizes': 'M, L', 'colors': 'Purple',
                'is_returnable': '1', 'return_days': '7',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ProductDraft.STATUS_PUBLISHED)

    def test_review_screen_offers_the_meesho_toggle_and_price_boxes(self):
        body = self.get(f'/admin-panel/product-drafts/{self.draft.pk}/').content.decode('utf-8', 'replace')
        for needle in ('supplier_meesho', 'supplier_market', 'Meesho', 'Market',
                       'base_price', 'name="margin"', 'Selling Price', 'MRP',
                       'generateSku'):
            self.assertIn(needle, body, f'review screen missing {needle!r}')

    def test_approve_stores_cost_margin_and_selling_price(self):
        self.post(
            f'/admin-panel/product-drafts/{self.draft.pk}/',
            {
                'action': 'approve', 'category': 'GENZ_TRENDS', 'sub_category': 'Kurtis',
                'name': 'Purple Sharara Suit', 'base_price': '600', 'margin': '299',
                'price': '1', 'old_price': '2999', 'stock': '5',
                'is_returnable': '1', 'return_days': '7',
            },
        )
        self.draft.refresh_from_db()
        product = self.draft.published_product
        self.assertIsNotNone(product)
        self.assertEqual(product.price, Decimal('899'), 'selling price is cost + margin')
        self.assertEqual(product.margin, Decimal('299'))
        self.assertEqual(product.old_price, Decimal('2999'))
        self.assertEqual(
            product.price - product.margin, Decimal('600'),
            'the edit page re-derives the cost this way',
        )

    def test_approve_fills_a_blank_sku_from_the_sub_category(self):
        self.post(
            f'/admin-panel/product-drafts/{self.draft.pk}/',
            {
                'action': 'approve', 'category': 'GENZ_TRENDS', 'sub_category': 'Kurtis',
                'name': 'Purple Sharara Suit', 'base_price': '600', 'margin': '299',
                'sku': '', 'stock': '5', 'is_returnable': '1', 'return_days': '7',
            },
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.published_product.sku, 'KURTIS-0001')

    def test_next_sku_endpoint_answers_the_review_screen(self):
        response = self.get('/admin-panel/product-drafts/next-sku/?sub_category=Sarees')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sku'], 'SAREES-0001')

    def test_reject_and_requeue(self):
        self.post(f'/admin-panel/product-drafts/{self.draft.pk}/', {'action': 'reject'})
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ProductDraft.STATUS_REJECTED)

        self.post(f'/admin-panel/product-drafts/{self.draft.pk}/', {'action': 'requeue'})
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ProductDraft.STATUS_QUEUED)

    def test_delete_single_and_bulk(self):
        pk = self.draft.pk
        self.assertEqual(self.post(f'/admin-panel/product-drafts/{pk}/delete/', {}).status_code, 302)
        self.assertFalse(ProductDraft.objects.filter(pk=pk).exists())

        send('-31', 1, text='Another\nPrice 100')
        send('-32', 1, text='And another\nPrice 200')
        self.assertEqual(ProductDraft.objects.count(), 2)
        self.post('/admin-panel/product-drafts/bulk-delete/', {'status': 'all'})
        self.assertEqual(ProductDraft.objects.count(), 0)

    def test_bulk_delete_never_removes_published_drafts(self):
        self.draft.status = ProductDraft.STATUS_PUBLISHED
        self.draft.save(update_fields=['status'])
        self.post('/admin-panel/product-drafts/bulk-delete/', {'status': 'all'})
        self.assertTrue(ProductDraft.objects.filter(pk=self.draft.pk).exists())

    def test_admin_routes_require_staff(self):
        self.client.logout()
        plain = User.objects.create_user('shopper', password='x')
        self.client.force_login(plain)
        response = self.get('/admin-panel/product-drafts/')
        self.assertIn(response.status_code, (302, 403), 'non-staff must not reach the queue')


@override_settings(GEMINI_API_KEY='test-key')
class GeminiRotationTests(TestCase):
    """Free-tier quota is per model, so a 429 should move on, not sleep."""

    def _client(self):
        from Hub.automation.ai.gemini import GeminiClient
        return GeminiClient()

    def _response(self, status, payload=None):
        from unittest.mock import Mock
        response = Mock()
        response.status_code = status
        response.json.return_value = payload or {}
        response.text = ''
        return response

    def _ok(self):
        return self._response(200, {
            'candidates': [{'content': {'parts': [{'text': '{"name": "Kurti"}'}]}}],
            'usageMetadata': {'totalTokenCount': 100},
        })

    def _rate_limited(self):
        return self._response(429, {'error': {
            'message': 'You exceeded your current quota',
            'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '39s'}],
        }})

    def test_rotation_starts_with_the_configured_model(self):
        client = self._client()
        rotation = client.model_rotation()
        self.assertEqual(rotation[0], client.model)
        self.assertEqual(len(rotation), len(set(rotation)), 'no model tried twice')

    def test_a_rate_limited_model_falls_through_to_the_next(self):
        from unittest.mock import patch

        client = self._client()
        expected = client.model_rotation()[1]  # before the call reorders it

        responses = [self._rate_limited(), self._ok()]
        with patch.object(client.session, 'post', side_effect=responses) as post, \
             patch('Hub.automation.ai.gemini.time.sleep') as slept:
            result = client.complete_json(system='s', content=[], schema={'type': 'object'})

        self.assertEqual(result['name'], 'Kurti')
        self.assertEqual(post.call_count, 2)
        slept.assert_not_called()
        self.assertEqual(
            client.model, expected,
            'the model that answered should be the one reported',
        )

    def test_only_sleeps_once_every_model_is_exhausted(self):
        from unittest.mock import patch

        client = self._client()
        depth = len(client.model_rotation())
        with patch.object(client.session, 'post', return_value=self._rate_limited()), \
             patch('Hub.automation.ai.gemini.time.sleep') as slept:
            with self.assertRaises(Exception):
                client.complete_json(system='s', content=[], schema={'type': 'object'})

        self.assertTrue(slept.called, 'a full sweep of 429s should back off')
        self.assertEqual(slept.call_args_list[0][0][0], 41, "obey Google's retryDelay")
        self.assertGreaterEqual(depth, 2, 'rotation needs somewhere to fall through to')

    def test_a_retired_model_is_skipped_not_waited_on(self):
        from unittest.mock import patch

        client = self._client()
        with patch.object(client.session, 'post', side_effect=[self._response(404), self._ok()]), \
             patch('Hub.automation.ai.gemini.time.sleep') as slept:
            result = client.complete_json(system='s', content=[], schema={'type': 'object'})

        self.assertEqual(result['name'], 'Kurti')
        slept.assert_not_called()

    def test_a_rejected_request_fails_immediately(self):
        from unittest.mock import patch

        from Hub.automation.ai.gemini import GeminiUnavailable

        client = self._client()
        with patch.object(client.session, 'post', return_value=self._response(400)) as post:
            with self.assertRaises(GeminiUnavailable):
                client.complete_json(system='s', content=[], schema={'type': 'object'})
        self.assertEqual(post.call_count, 1, 'a bad request will not fix itself')


class OllamaProviderTests(TestCase):
    """The Ollama client must present the same surface as the hosted ones."""

    def _client(self):
        from Hub.automation.ai.ollama import OllamaClient
        return OllamaClient()

    def test_content_blocks_are_flattened_for_ollama(self):
        from Hub.automation.ai.ollama import OllamaClient

        texts, images = OllamaClient._split_content([
            {'type': 'text', 'text': 'Image index 0:'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'QUJD'}},
            {'type': 'text', 'text': 'Classify these.'},
        ])
        self.assertEqual(texts, ['Image index 0:', 'Classify these.'])
        self.assertEqual(images, ['QUJD'])

    def test_thinking_tags_are_stripped(self):
        client = self._client()
        parsed = client._parse({
            'message': {'content': '<think>weighing options</think>{"name": "Kurti"}'},
            'prompt_eval_count': 10, 'eval_count': 5,
        })
        self.assertEqual(parsed['name'], 'Kurti')
        self.assertEqual(client.total_tokens, 15)

    def test_json_wrapped_in_prose_is_recovered(self):
        parsed = self._client()._parse({
            'message': {'content': 'Here is the record:\n{"name": "Saree"}\nHope that helps.'},
        })
        self.assertEqual(parsed['name'], 'Saree')

    def test_empty_response_is_an_error(self):
        with self.assertRaises(ValueError):
            self._client()._parse({'message': {'content': '   '}, 'done_reason': 'length'})

    def test_pipeline_skips_vision_for_a_text_only_model(self):
        """A text-only model must not be sent images it cannot read."""
        from unittest.mock import patch

        send('-40', 1, media=[image_media(1)])
        send('-40', 2, text='Kurti\nPrice 799')
        draft = ProductDraft.objects.get()
        age(draft, 300)

        class TextOnly:
            model = 'qwen3:8b'
            supports_vision = False
            total_tokens = 0

            def complete_json(self, **kwargs):
                raise AssertionError('extraction is stubbed separately')

        with patch('Hub.automation.pipeline.is_configured', return_value=True), \
             patch('Hub.automation.pipeline.get_client', return_value=TextOnly()), \
             patch('Hub.automation.pipeline.analyse_images') as vision, \
             patch('Hub.automation.pipeline.extract', return_value=({'name': 'Kurti', 'warnings': []}, False)):
            pipeline.process_once()

        vision.assert_not_called()
        draft.refresh_from_db()
        self.assertEqual(draft.status, ProductDraft.STATUS_PENDING)
        self.assertTrue(
            any('text-only' in e['message'] for e in draft.events),
            'the skip should be recorded on the draft',
        )
