"""
Django Management Command: Create Backup
Local-first backup system for VibeMall.
"""

import os
import logging
from datetime import datetime

import pandas as pd
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count
from django.utils import timezone

from Hub.models import (
    BackupConfiguration,
    BackupLog,
    BackupCleanupRequest,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ReturnRequest,
    PayoutTransaction,
    PointsTransaction,
    Reel,
)
from Hub.backup_utils import (
    ensure_backup_directories,
    get_month_folder,
    send_backup_notification_email,
    send_cleanup_confirmation_email,
)

logger = logging.getLogger(__name__)

DEFAULT_TYPES = [
    "users",
    "orders",
    "payments",
    "transactions",
    "products",
    "returns",
    "analytics",
    "product_media",
]


class Command(BaseCommand):
    help = "Create local monthly/special/ITR backups in D:\\VibeMallBackUp"

    def add_arguments(self, parser):
        parser.add_argument("--type", default="manual", choices=["manual", "scheduled", "on-demand", "special", "itr-report"])
        parser.add_argument("--frequency", default="monthly", choices=["daily", "weekly", "biweekly", "monthly", "custom"])
        parser.add_argument("--mode", default="regular", choices=["regular", "special", "itr"])
        parser.add_argument("--data-types", default=",".join(DEFAULT_TYPES), help="Comma separated: users,orders,payments,transactions,products,returns,analytics,product_media")
        parser.add_argument("--output-dir", default=None)
        parser.add_argument("--from-date", default=None, help="YYYY-MM-DD")
        parser.add_argument("--to-date", default=None, help="YYYY-MM-DD")
        parser.add_argument("--no-email", action="store_true")
        parser.add_argument("--no-cleanup-request", action="store_true")

    def handle(self, *args, **options):
        try:
            config, _ = BackupConfiguration.objects.get_or_create(pk=1)

            mode = options["mode"].upper()
            backup_type = options["type"].upper().replace("-", "_")
            frequency = options["frequency"].upper()
            data_types = [item.strip().lower() for item in options["data_types"].split(",") if item.strip()]
            if not data_types:
                data_types = DEFAULT_TYPES

            date_from = self._parse_date(options.get("from_date"))
            date_to = self._parse_date(options.get("to_date"), end_of_day=True)

            root, regular_root, special_root = ensure_backup_directories(config)
            base_root = regular_root if mode == "REGULAR" else special_root
            if options.get("output_dir"):
                base_root = options["output_dir"]
                os.makedirs(base_root, exist_ok=True)

            month_dir, month_label = get_month_folder(base_root)

            backup_log = BackupLog.objects.create(
                backup_type=backup_type,
                backup_scope=mode,
                backup_frequency=frequency,
                status="IN_PROGRESS",
                backup_data_types=",".join(data_types),
                monthly_folder_label=month_label,
                local_file_path=month_dir,
            )

            files = self._export_selected_files(month_dir, backup_log, data_types, date_from, date_to)
            if not files:
                raise CommandError("No backup files generated.")

            backup_log.status = "SUCCESS"
            backup_log.end_time = timezone.now()
            backup_log.file_size_mb = self._calc_total_size_mb(files)
            backup_log.save()

            config.last_backup_at = timezone.now()
            config.save(update_fields=["last_backup_at", "updated_at"])

            if not options["no_email"]:
                recipients = config.get_notification_emails()
                if recipients:
                    sent = send_backup_notification_email(backup_log, files, recipients)
                    backup_log.email_sent = sent
                    backup_log.save(update_fields=["email_sent", "updated_at"])

            if mode == "REGULAR" and not options["no_cleanup_request"]:
                self._create_cleanup_request_if_needed(config, backup_log, regular_root, month_label)

            self.stdout.write(self.style.SUCCESS(f"Backup #{backup_log.id} completed at: {month_dir}"))

        except Exception as exc:
            logger.error("Backup creation failed: %s", exc, exc_info=True)
            if "backup_log" in locals():
                backup_log.status = "FAILED"
                backup_log.error_message = str(exc)
                backup_log.end_time = timezone.now()
                backup_log.save()
            raise CommandError(f"Backup failed: {exc}")

    def _parse_date(self, value, end_of_day=False):
        if not value:
            return None
        dt = datetime.strptime(value, "%Y-%m-%d")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return timezone.make_aware(dt)

    def _export_selected_files(self, output_dir, backup_log, data_types, date_from, date_to):
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        files = {}

        if "users" in data_types:
            path, count = self.export_users(output_dir, timestamp, date_from, date_to)
            if path:
                files["users"] = path
                backup_log.users_count = count

        if "orders" in data_types:
            path, count = self.export_orders(output_dir, timestamp, date_from, date_to)
            if path:
                files["orders"] = path
                backup_log.orders_count = count

        if "payments" in data_types:
            path, count = self.export_payments(output_dir, timestamp, date_from, date_to)
            if path:
                files["payments"] = path
                backup_log.payments_count = count

        if "transactions" in data_types:
            path, count = self.export_transactions(output_dir, timestamp, date_from, date_to)
            if path:
                files["transactions"] = path
                backup_log.transactions_count = count

        if "products" in data_types:
            path, count = self.export_products(output_dir, timestamp, date_from, date_to)
            if path:
                files["products"] = path
                backup_log.products_count = count

        if "returns" in data_types:
            path, count = self.export_returns(output_dir, timestamp, date_from, date_to)
            if path:
                files["returns"] = path
                backup_log.returns_count = count

        if "analytics" in data_types:
            path = self.export_analytics(output_dir, timestamp, date_from, date_to)
            if path:
                files["analytics"] = path

        if "product_media" in data_types:
            path = self.export_product_media(output_dir, timestamp)
            if path:
                files["product_media"] = path

        backup_log.save()
        return files

    def _date_filter(self, queryset, field_name, date_from, date_to):
        if date_from:
            queryset = queryset.filter(**{f"{field_name}__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{field_name}__lte": date_to})
        return queryset

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
                value = cell.value
                if value is None:
                    continue
                try:
                    max_length = max(max_length, len(str(value)))
                except Exception:
                    continue

            adjusted_width = min(max(max_length + 2, 12), 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    def _auto_adjust_workbook(self, writer):
        for worksheet in writer.book.worksheets:
            self._auto_adjust_sheet_columns(worksheet)

    def export_users(self, output_dir, timestamp, date_from=None, date_to=None):
        qs = User.objects.all().order_by("id")
        qs = self._date_filter(qs, "date_joined", date_from, date_to)
        rows = list(qs.values("id", "username", "email", "first_name", "last_name", "is_active", "date_joined", "last_login"))
        if not rows:
            return None, 0

        df = self._excel_safe(pd.DataFrame(rows))
        path = os.path.join(output_dir, f"users_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Users", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(df)

    def export_orders(self, output_dir, timestamp, date_from=None, date_to=None):
        orders = Order.objects.select_related("user").all().order_by("-created_at")
        orders = self._date_filter(orders, "created_at", date_from, date_to)
        if not orders.exists():
            return None, 0

        order_rows, item_rows = [], []
        for order in orders:
            order_rows.append({
                "Order Number": order.order_number,
                "User": order.user.username,
                "Email": order.user.email,
                "Subtotal": float(order.subtotal),
                "Tax": float(order.tax),
                "Shipping": float(order.shipping_cost),
                "Coupon Discount": float(order.coupon_discount),
                "Total": float(order.total_amount),
                "Order Status": order.order_status,
                "Payment Status": order.payment_status,
                "Payment Method": order.payment_method,
                "Order Date": order.order_date,
                "Created At": order.created_at,
            })
            for item in order.items.all():
                item_rows.append({
                    "Order Number": order.order_number,
                    "Product Name": item.product_name,
                    "Product ID": item.product_id,
                    "Quantity": item.quantity,
                    "Unit Price": float(item.product_price),
                    "Subtotal": float(item.subtotal),
                })

        orders_df = self._excel_safe(pd.DataFrame(order_rows))
        items_df = self._excel_safe(pd.DataFrame(item_rows))
        path = os.path.join(output_dir, f"orders_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            orders_df.to_excel(writer, sheet_name="Orders", index=False)
            items_df.to_excel(writer, sheet_name="OrderItems", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(orders_df)

    def export_payments(self, output_dir, timestamp, date_from=None, date_to=None):
        orders = Order.objects.all().order_by("-created_at")
        orders = self._date_filter(orders, "created_at", date_from, date_to)
        if not orders.exists():
            return None, 0

        rows = []
        for order in orders:
            rows.append({
                "Order Number": order.order_number,
                "Payment Status": order.payment_status,
                "Payment Method": order.payment_method,
                "Amount": float(order.total_amount),
                "Razorpay Order ID": order.razorpay_order_id,
                "Razorpay Payment ID": order.razorpay_payment_id,
                "Created At": order.created_at,
            })
        df = self._excel_safe(pd.DataFrame(rows))
        path = os.path.join(output_dir, f"payments_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Payments", index=False)
            summary = df.groupby("Payment Status", dropna=False)["Amount"].agg(["count", "sum"]).reset_index()
            summary.to_excel(writer, sheet_name="StatusSummary", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(df)

    def export_transactions(self, output_dir, timestamp, date_from=None, date_to=None):
        payouts = PayoutTransaction.objects.select_related("reseller").all().order_by("-initiated_at")
        payouts = self._date_filter(payouts, "initiated_at", date_from, date_to)

        points = PointsTransaction.objects.select_related("user").all().order_by("-created_at")
        points = self._date_filter(points, "created_at", date_from, date_to)

        payout_rows = [{
            "Reseller": p.reseller.username,
            "Amount": float(p.amount),
            "Method": p.payout_method,
            "Status": p.status,
            "Transaction ID": p.transaction_id,
            "Initiated": p.initiated_at,
            "Completed": p.completed_at,
        } for p in payouts]

        point_rows = [{
            "User": pt.user.username,
            "Points": pt.points,
            "Type": pt.transaction_type,
            "Description": pt.description,
            "Created At": pt.created_at,
        } for pt in points]

        if not payout_rows and not point_rows:
            return None, 0

        path = os.path.join(output_dir, f"transactions_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            self._excel_safe(pd.DataFrame(payout_rows)).to_excel(writer, sheet_name="PayoutTransactions", index=False)
            self._excel_safe(pd.DataFrame(point_rows)).to_excel(writer, sheet_name="PointsTransactions", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(payout_rows) + len(point_rows)

    def export_products(self, output_dir, timestamp, date_from=None, date_to=None):
        products = Product.objects.all().order_by("-id")
        if not products.exists():
            return None, 0

        rows = [{
            "Product ID": p.id,
            "Name": p.name,
            "SKU": p.sku,
            "Category": p.get_category_display() if p.category else "",
            "Sub Category": p.sub_category,
            "Price": float(p.price),
            "Old Price": float(p.old_price) if p.old_price else None,
            "Stock": p.stock,
            "Sold": p.sold,
            "Active": p.is_active,
            "Brand": p.brand,
            "Image": p.image.url if p.image else "",
            "Description": p.description,
        } for p in products]
        df = pd.DataFrame(rows)

        path = os.path.join(output_dir, f"products_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Products", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(df)

    def export_product_media(self, output_dir, timestamp):
        product_images = ProductImage.objects.select_related("product").all().order_by("product_id", "order")
        reels = Reel.objects.select_related("product").all().order_by("-created_at")

        image_rows = [{
            "Product ID": img.product_id,
            "Product Name": img.product.name if img.product else "",
            "Image": img.image.url if img.image else "",
            "Order": img.order,
        } for img in product_images]

        reel_rows = [{
            "Reel ID": reel.id,
            "Title": reel.title,
            "Linked Product ID": reel.product_id,
            "Video File": reel.video_file.url if reel.video_file else "",
            "Thumbnail": reel.thumbnail.url if reel.thumbnail else "",
            "Created At": reel.created_at,
        } for reel in reels]

        path = os.path.join(output_dir, f"product_media_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            self._excel_safe(pd.DataFrame(image_rows)).to_excel(writer, sheet_name="ProductImages", index=False)
            self._excel_safe(pd.DataFrame(reel_rows)).to_excel(writer, sheet_name="ProductVideos", index=False)
            self._auto_adjust_workbook(writer)
        return path

    def export_returns(self, output_dir, timestamp, date_from=None, date_to=None):
        returns = ReturnRequest.objects.select_related("order", "user", "order_item").all().order_by("-created_at")
        returns = self._date_filter(returns, "created_at", date_from, date_to)
        if not returns.exists():
            return None, 0

        rows = [{
            "Return Number": ret.return_number,
            "Order Number": ret.order.order_number,
            "User": ret.user.username,
            "Reason": ret.reason,
            "Status": ret.status,
            "Refund Amount": float(ret.refund_amount) if ret.refund_amount else 0,
            "Refund Net": float(ret.refund_amount_net) if ret.refund_amount_net else 0,
            "Requested At": ret.requested_at,
            "Resolved At": ret.resolved_at,
        } for ret in returns]
        df = self._excel_safe(pd.DataFrame(rows))

        path = os.path.join(output_dir, f"returns_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Returns", index=False)
            self._auto_adjust_workbook(writer)
        return path, len(df)

    def export_analytics(self, output_dir, timestamp, date_from=None, date_to=None):
        orders = Order.objects.all()
        orders = self._date_filter(orders, "created_at", date_from, date_to)
        if not orders.exists():
            return None

        total_revenue = float(orders.aggregate(total=Sum("total_amount"))["total"] or 0)
        total_orders = orders.count()
        total_returns = ReturnRequest.objects.filter(order__in=orders).count()
        avg_order = total_revenue / total_orders if total_orders else 0

        metrics_df = pd.DataFrame([
            {"Metric": "Total Revenue", "Value": total_revenue},
            {"Metric": "Total Orders", "Value": total_orders},
            {"Metric": "Average Order Value", "Value": avg_order},
            {"Metric": "Total Returns", "Value": total_returns},
            {"Metric": "Generated At", "Value": timezone.now().strftime("%Y-%m-%d %H:%M:%S")},
        ])

        status_df = pd.DataFrame(list(orders.values("order_status").annotate(count=Count("id"))))
        payment_df = pd.DataFrame(list(orders.values("payment_status").annotate(total_amount=Sum("total_amount"))))

        path = os.path.join(output_dir, f"analytics_backup_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            metrics_df.to_excel(writer, sheet_name="Metrics", index=False)
            status_df.to_excel(writer, sheet_name="OrderStatus", index=False)
            payment_df.to_excel(writer, sheet_name="PaymentStatus", index=False)
            self._auto_adjust_workbook(writer)
        return path

    def _calc_total_size_mb(self, files):
        total = 0
        for file_path in files.values():
            if os.path.isfile(file_path):
                total += os.path.getsize(file_path)
        return round(total / (1024 * 1024), 2)

    def _create_cleanup_request_if_needed(self, config, backup_log, regular_root, current_month_label):
        month_folders = [name for name in os.listdir(regular_root) if os.path.isdir(os.path.join(regular_root, name))]
        month_folders = sorted(month_folders)
        if len(month_folders) < 2:
            return

        candidates = [label for label in month_folders if label < current_month_label]
        if not candidates:
            return

        old_label = candidates[-1]
        old_folder = os.path.join(regular_root, old_label)

        existing = BackupCleanupRequest.objects.filter(folder_path=old_folder, status__in=["PENDING", "CONFIRMED"]).first()
        if existing:
            return

        cleanup = BackupCleanupRequest.objects.create(
            backup_log=backup_log,
            folder_path=old_folder,
            folder_label=old_label,
            status="PENDING",
        )
        backup_log.requires_cleanup_confirmation = True
        backup_log.save(update_fields=["requires_cleanup_confirmation", "updated_at"])

        recipients = config.get_notification_emails()
        if recipients:
            site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
            confirm_url = f"{site_url}/admin-panel/backup/cleanup/{cleanup.confirmation_token}/"
            email_sent = send_cleanup_confirmation_email(cleanup, recipients, confirm_url)
            cleanup.email_sent = email_sent
            cleanup.save(update_fields=["email_sent"])