from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Reprocess product image files directly from media folders into "
        "a 4:5 frame (960x1200), without requiring DB records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without writing files.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional max files to process (0 = all).",
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            help="Create backup copies before overwriting files.",
        )
        parser.add_argument(
            "--include-descriptions",
            action="store_true",
            help="Also process media/products/descriptions/",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = max(0, int(options["limit"] or 0))
        backup = bool(options["backup"])
        include_descriptions = bool(options["include_descriptions"])

        try:
            from PIL import Image
        except Exception:
            self.stdout.write(self.style.ERROR("Pillow is not installed."))
            return

        media_root = Path(str(settings.MEDIA_ROOT))
        # Use only top-level products dir to avoid duplicate traversal of subfolders.
        target_dirs = [media_root / "products"]

        image_paths_set: set[Path] = set()
        for d in target_dirs:
            if not d.exists():
                continue
            for p in d.rglob("*"):
                if not include_descriptions and "descriptions" in p.parts:
                    continue
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    image_paths_set.add(p)

        image_paths = sorted(image_paths_set)

        if limit:
            image_paths = image_paths[:limit]

        self.stdout.write(self.style.SUCCESS(f"Found files: {len(image_paths)}"))
        if dry_run:
            for p in image_paths[:20]:
                self.stdout.write(f"  would process: {p}")
            if len(image_paths) > 20:
                self.stdout.write(f"  ... and {len(image_paths) - 20} more")
            self.stdout.write(self.style.WARNING("Dry run complete. No files changed."))
            return

        processed = 0
        skipped = 0
        failed = 0

        for path in image_paths:
            try:
                with path.open("rb") as f:
                    img = Image.open(f)
                    img.load()

                if img.format not in {"JPEG", "PNG", "WEBP"}:
                    skipped += 1
                    continue

                has_alpha = img.mode in ("RGBA", "LA") or (
                    img.mode == "P" and "transparency" in img.info
                )
                working = img.convert("RGBA") if has_alpha else img.convert("RGB")

                # Fit entire image into a 4:5 frame without cropping.
                # Upscale small images too, so they don't appear tiny.
                target_width, target_height = 960, 1200
                scale = min(target_width / working.width, target_height / working.height)
                new_width = max(1, int(round(working.width * scale)))
                new_height = max(1, int(round(working.height * scale)))
                fitted = working.resize((new_width, new_height), Image.LANCZOS)

                if has_alpha:
                    canvas = Image.new("RGBA", (target_width, target_height), (246, 244, 239, 255))
                else:
                    canvas = Image.new("RGB", (target_width, target_height), (246, 244, 239))

                x = (target_width - fitted.width) // 2
                y = (target_height - fitted.height) // 2
                canvas.paste(fitted, (x, y), fitted if has_alpha else None)

                output_format = "PNG" if has_alpha else "JPEG"
                buffer = BytesIO()
                save_kwargs = {"format": output_format, "optimize": True}
                if output_format == "JPEG":
                    save_kwargs["quality"] = 82
                canvas.save(buffer, **save_kwargs)
                buffer.seek(0)

                if backup:
                    backup_path = path.with_suffix(path.suffix + ".bak")
                    if not backup_path.exists():
                        shutil.copy2(path, backup_path)

                # Keep same file path to avoid URL changes.
                with path.open("wb") as out:
                    out.write(buffer.read())

                processed += 1
                if processed % 50 == 0:
                    self.stdout.write(f"  processed: {processed}")
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  failed {path}: {exc}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Folder reprocess completed."))
        self.stdout.write(f"Processed: {processed}")
        self.stdout.write(f"Skipped: {skipped}")
        self.stdout.write(f"Failed: {failed}")
