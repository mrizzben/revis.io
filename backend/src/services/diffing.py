"""T4 Phase 2: server-side revision diffing for comparison.

Rasterizes PDFs (or loads raster images), aligns the two revisions to a
common letterboxed canvas per page, and reports per-page change metrics,
change-region boxes, and highlight overlays. PDFs beyond the synchronous
page budget are handed to the ARQ worker and polled via
``get_diff_job_result``.

CPU-heavy work runs under ``asyncio.to_thread`` so the API event loop is
never blocked.
"""

import asyncio
import io
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

logger = logging.getLogger(__name__)

# Rasterize PDFs at a moderate DPI; pixel-level noise is absorbed by the
# per-channel delta threshold below.
DIFF_DPI = 72
# Per-channel pixel delta below which a pixel counts as unchanged.
PIXEL_DELTA_THRESHOLD = 10
# A page whose changed-pixel fraction is at or below this counts as unchanged.
CHANGED_RATIO_THRESHOLD = 0.005
# PDFs with more pages than this are diffed by the ARQ worker, not inline.
MAX_SYNC_PAGES = 20
# Grid-merge granularity for change-region boxes (cell count per axis).
REGION_GRID = 16
# Cap the longest canvas side to bound memory for large drawings.
MAX_RENDER_SIDE = 2048

_EMPTY_PAGES: list[dict[str, Any]] = []


def unavailable_payload(message: str) -> dict[str, Any]:
    """Diff object for failed/unsupported computation (never raises)."""
    return {
        "status": "unavailable",
        "poll_url": None,
        "page_count": 0,
        "pages": _EMPTY_PAGES,
        "message": message,
    }


@dataclass
class _DiffPage:
    page_number: int
    width: int
    height: int
    diff_ratio: float
    changed: bool
    regions: list[dict[str, Any]]
    from_img: Image.Image | None
    to_img: Image.Image | None
    overlay: bytes | None


@dataclass
class _ComputedDiff:
    pages: list[_DiffPage]


# ── pixel-level diff (CPU-bound) ───────────────────────────


def _downscale(image: Image.Image, max_side: int = MAX_RENDER_SIDE) -> Image.Image:
    if max(image.width, image.height) <= max_side:
        return image
    image = image.copy()
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def _align(from_img: Image.Image, to_img: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Letterbox both revisions onto one shared canvas so regions align."""
    w = max(from_img.width, to_img.width)
    h = max(from_img.height, to_img.height)

    def _letterbox(img: Image.Image) -> Image.Image:
        canvas = Image.new("RGB", (w, h), (255, 255, 255))
        canvas.paste(img.convert("RGB"), ((w - img.width) // 2, (h - img.height) // 2))
        return canvas

    return _letterbox(from_img), _letterbox(to_img)


def _merged_region_boxes(mask: Image.Image) -> list[tuple[int, int, int, int]]:
    """Turn a thresholded changed-pixel mask into page-coordinate boxes.

    Grid-merge: downsample the mask to a REGION_GRID x REGION_GRID cell grid,
    merge horizontal runs per row, then merge boxes that overlap horizontally
    and touch vertically. Approximate but fast and deterministic.
    """
    w, h = mask.size
    gw = min(REGION_GRID, max(w, 1))
    gh = min(REGION_GRID, max(h, 1))
    if gw == 0 or gh == 0:
        return []
    small = mask.resize((gw, gh), Image.Resampling.NEAREST)

    boxes: list[list[int]] = []  # [x0, y0, x1, y1] in cell coordinates
    for row in range(gh):
        col = 0
        while col < gw:
            if small.getpixel((col, row)):
                col2 = col
                while col2 < gw and small.getpixel((col2, row)):
                    col2 += 1
                boxes.append([col, row, col2, row + 1])
                col = col2
            else:
                col += 1

    # Two passes are enough for a 16x16 grid.
    for _ in range(2):
        merged: list[list[int]] = []
        for box in boxes:
            for m in merged:
                if box[0] < m[2] and m[0] < box[2] and box[1] <= m[3] and m[1] <= box[3]:
                    m[0] = min(m[0], box[0])
                    m[1] = min(m[1], box[1])
                    m[2] = max(m[2], box[2])
                    m[3] = max(m[3], box[3])
                    break
            else:
                merged.append(box)
        boxes = merged

    sx = w / gw
    sy = h / gh
    out: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in boxes:
        px0 = int(round(x0 * sx))
        py0 = int(round(y0 * sy))
        px1 = min(int(round(x1 * sx)), w)
        py1 = min(int(round(y1 * sy)), h)
        if px1 > px0 and py1 > py0:
            out.append((px0, py0, px1, py1))
    return out


def _ink_fraction(img: Image.Image) -> float:
    """Fraction of pixels darker than a luminance cutoff (white-sheet model)."""
    gray = img.convert("L")
    total = max(gray.width * gray.height, 1)
    return sum(gray.histogram()[:160]) / total


def _region_kind(from_img: Image.Image, to_img: Image.Image, box: tuple[int, int, int, int]) -> str:
    """added / removed / modified heuristic.

    ponytail: white-background drawing heuristic; photographic content will
    mostly read as 'modified', which is a safe fallback for the frontend.
    """
    from_ink = _ink_fraction(from_img.crop(box))
    to_ink = _ink_fraction(to_img.crop(box))
    if to_ink > 0.05 and from_ink <= 0.05:
        return "added"
    if from_ink > 0.05 and to_ink <= 0.05:
        return "removed"
    return "modified"


_KIND_COLORS = {
    "added": (34, 197, 94),    # green
    "removed": (239, 68, 68),  # red
    "modified": (245, 158, 11),  # amber
}


def _render_overlay(width: int, height: int, regions: list[dict[str, Any]]) -> bytes:
    """Semi-transparent colored boxes over a transparent canvas (WebP)."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for region in regions:
        color = _KIND_COLORS.get(region["kind"], _KIND_COLORS["modified"])
        box = (region["x"], region["y"], region["x"] + region["w"], region["y"] + region["h"])
        draw.rectangle(box, fill=(*color, 64), outline=(*color, 255), width=2)
    buf = io.BytesIO()
    overlay.save(buf, format="WEBP", quality=90)
    return buf.getvalue()


def _diff_image_pair(from_img: Image.Image, to_img: Image.Image) -> tuple[float, list[dict[str, Any]]]:
    """diff_ratio + region boxes for two aligned revisions."""
    a, b = _align(_downscale(from_img), _downscale(to_img))
    diff = ImageChops.difference(a, b).convert("L")
    threshold_table = [255 if i > PIXEL_DELTA_THRESHOLD else 0 for i in range(256)]
    mask = diff.point(threshold_table)
    w, h = mask.size
    diff_ratio = mask.histogram()[255] / max(w * h, 1)
    regions = [
        {
            "x": x0,
            "y": y0,
            "w": x1 - x0,
            "h": y1 - y0,
            "kind": _region_kind(a, b, (x0, y0, x1, y1)),
        }
        for (x0, y0, x1, y1) in _merged_region_boxes(mask)
    ]
    return diff_ratio, regions


# ── document loading (CPU-bound) ───────────────────────────


def _page_count_pdf(path: str) -> int:
    import fitz  # PyMuPDF

    with fitz.open(path) as doc:
        return len(doc)


def _rasterize_pdf(path: str, dpi: int = DIFF_DPI) -> list[Image.Image]:
    import fitz  # PyMuPDF

    pages: list[Image.Image] = []
    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)  # type: ignore[reportAttributeAccessIssue]  # PyMuPDF 1.25 typings lag the rebased API
            pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return pages


def _compute_diff(
    from_path: str,
    to_path: str,
    file_type: str,
    enforce_budget: bool,
) -> _ComputedDiff | None:
    """Pure-CPU diff. Returns None when the sync page budget is exceeded."""
    if file_type == "pdf":
        if enforce_budget and max(
            _page_count_pdf(from_path), _page_count_pdf(to_path)
        ) > MAX_SYNC_PAGES:
            return None
        from_pages = _rasterize_pdf(from_path)
        to_pages = _rasterize_pdf(to_path)
    else:
        from_pages = [_downscale(Image.open(from_path).convert("RGB"))]
        to_pages = [_downscale(Image.open(to_path).convert("RGB"))]

    pages: list[_DiffPage] = []
    page_count = max(len(from_pages), len(to_pages))
    for i in range(page_count):
        from_img = from_pages[i] if i < len(from_pages) else None
        to_img = to_pages[i] if i < len(to_pages) else None
        if from_img is None or to_img is None:
            # Full page added/removed: whole canvas is one changed region.
            present = to_img if to_img is not None else from_img
            assert present is not None
            width, height = present.width, present.height
            kind = "added" if to_img is not None else "removed"
            regions = [{"x": 0, "y": 0, "w": width, "h": height, "kind": kind}]
            pages.append(
                _DiffPage(
                    page_number=i + 1,
                    width=width,
                    height=height,
                    diff_ratio=1.0,
                    changed=True,
                    regions=regions,
                    from_img=from_img,
                    to_img=to_img,
                    overlay=_render_overlay(width, height, regions),
                )
            )
            continue

        diff_ratio, regions = _diff_image_pair(from_img, to_img)
        changed = diff_ratio > CHANGED_RATIO_THRESHOLD
        width, height = max(from_img.width, to_img.width), max(from_img.height, to_img.height)
        overlay = _render_overlay(width, height, regions) if changed else None
        pages.append(
            _DiffPage(
                page_number=i + 1,
                width=width,
                height=height,
                diff_ratio=round(diff_ratio, 6),
                changed=changed,
                regions=regions,
                from_img=from_img if changed else None,
                to_img=to_img if changed else None,
                overlay=overlay,
            )
        )

    return _ComputedDiff(pages=pages)


# ── S3 artifacts + presigned URLs (async orchestration) ───


def _image_webp(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


async def _upload_page_artifacts(s3: Any, bucket: str, prefix: str, page: _DiffPage) -> dict[str, Any]:
    """Upload page renders + overlay for one changed page; return URLs.

    Only changed pages produce renders/overlays (contract: URLs nullable).
    """
    from src.services.file import create_presigned_download_url

    from_key = f"{prefix}/p{page.page_number}-from.webp"
    to_key = f"{prefix}/p{page.page_number}-to.webp"
    overlay_key = f"{prefix}/p{page.page_number}-overlay.webp"

    if page.changed:
        from_img = page.from_img
        to_img = page.to_img
        overlay = page.overlay
        if from_img is None or to_img is None or overlay is None:
            # Defensive: page objects always carry renders when changed.
            return {
                "page_number": page.page_number,
                "width": page.width,
                "height": page.height,
                "diff_ratio": page.diff_ratio,
                "changed": True,
                "regions": page.regions,
                "from_url": None,
                "to_url": None,
                "overlay_url": None,
            }
        s3.put_object(
            Bucket=bucket, Key=from_key, Body=_image_webp(from_img),
            ContentType="image/webp",
        )
        s3.put_object(
            Bucket=bucket, Key=to_key, Body=_image_webp(to_img),
            ContentType="image/webp",
        )
        s3.put_object(
            Bucket=bucket, Key=overlay_key, Body=page.overlay,
            ContentType="image/webp",
        )
        from_url = create_presigned_download_url(from_key, content_type="image/webp")
        to_url = create_presigned_download_url(to_key, content_type="image/webp")
        overlay_url = create_presigned_download_url(overlay_key, content_type="image/webp")
    else:
        from_url = to_url = overlay_url = None

    return {
        "page_number": page.page_number,
        "width": page.width,
        "height": page.height,
        "diff_ratio": page.diff_ratio,
        "changed": page.changed,
        "regions": page.regions,
        "from_url": from_url,
        "to_url": to_url,
        "overlay_url": overlay_url,
    }


async def generate_comparison_diff(
    file_id: str,
    from_key: str,
    to_key: str,
    file_type: str,
    from_version: int,
    to_version: int,
    *,
    enforce_budget: bool,
) -> dict[str, Any] | None:
    """Compute the full ``diff`` payload for two revision objects.

    Returns None only when ``enforce_budget`` is set and the PDF exceeds the
    sync page budget (caller should enqueue the ARQ job instead). Never
    raises: failures degrade to ``status: unavailable``.
    """
    from src.core.config import settings
    from src.services.file import _get_lazy_s3_client

    s3 = _get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    try:
        with tempfile.TemporaryDirectory() as tmp:
            from_path = str(Path(tmp) / "from.bin")
            to_path = str(Path(tmp) / "to.bin")
            Path(from_path).write_bytes(s3.get_object(Bucket=bucket, Key=from_key)["Body"].read())
            Path(to_path).write_bytes(s3.get_object(Bucket=bucket, Key=to_key)["Body"].read())

            computed = await asyncio.to_thread(
                _compute_diff, from_path, to_path, file_type, enforce_budget
            )
            if computed is None:
                return None

            prefix = f"derive/{file_id}/diff/{from_version}-{to_version}"
            pages = [
                await _upload_page_artifacts(s3, bucket, prefix, page)
                for page in computed.pages
            ]
            return {
                "status": "ready",
                "poll_url": None,
                "page_count": len(pages),
                "pages": pages,
            }
    except Exception as exc:
        logger.exception("Diff computation failed for file %s", file_id)
        return unavailable_payload(str(exc))


# ── ARQ worker integration ─────────────────────────────────


async def enqueue_diff_job(
    file_id: str,
    from_key: str,
    to_key: str,
    file_type: str,
    from_version: int,
    to_version: int,
) -> str:
    """Enqueue the background diff job; returns its deterministic job id."""
    from src.services.thumbnail import get_queue

    job_id = f"diff:{file_id}:{from_version}:{to_version}"
    queue = await get_queue()
    await queue.enqueue_job(
        "src.services.diffing.generate_revision_diff",
        file_id=file_id,
        file_type=file_type,
        from_key=from_key,
        to_key=to_key,
        from_version=from_version,
        to_version=to_version,
        _job_id=job_id,
    )
    return job_id


async def generate_revision_diff(
    ctx: dict,
    file_id: str,
    file_type: str,
    from_key: str,
    to_key: str,
    from_version: int,
    to_version: int,
) -> dict[str, Any]:
    """ARQ job: diff without the inline sync budget."""
    result = await generate_comparison_diff(
        file_id,
        from_key,
        to_key,
        file_type,
        from_version,
        to_version,
        enforce_budget=False,
    )
    if result is None:  # only reachable when enforce_budget, but keep honest
        return unavailable_payload("Diff computation budget exceeded")
    return result


async def compute_diff_or_enqueue(
    file: Any,
    from_version: Any,
    to_version: Any,
) -> dict[str, Any]:
    """Compute a diff for two revision objects, or enqueue the ARQ job when
    the sync budget is exceeded (PDFs beyond MAX_SYNC_PAGES).

    ``file`` is a DesignFile, ``from_version``/``to_version`` are FileVersion
    rows. Sync work runs under asyncio.to_thread; enqueueing is best-effort
    (a queue outage degrades to ``pending`` with a poll URL instead of
    failing the compare request).
    """
    if file.file_type not in ("pdf", "png", "jpg", "jpeg", "webp"):
        return unavailable_payload(f"Diff unsupported for {file.file_type}")

    result = await generate_comparison_diff(
        file_id=str(file.id),
        from_key=from_version.s3_key,
        to_key=to_version.s3_key,
        file_type=file.file_type,
        from_version=from_version.version_number,
        to_version=to_version.version_number,
        enforce_budget=True,
    )
    if result is not None:
        return result

    # Budget exceeded: hand to the ARQ worker and return a poll URL.
    try:
        job_id = await enqueue_diff_job(
            file_id=str(file.id),
            from_key=from_version.s3_key,
            to_key=to_version.s3_key,
            file_type=file.file_type,
            from_version=from_version.version_number,
            to_version=to_version.version_number,
        )
        return {
            "status": "pending",
            "poll_url": f"/api/files/{file.id}/compare/{job_id}",
            "page_count": 0,
            "pages": [],
        }
    except Exception as exc:  # queue outage must not 500 compare
        logger.exception("Diff enqueue failed for file %s", file.id)
        return unavailable_payload(str(exc))


async def get_diff_job_result(job_id: str) -> dict[str, Any] | None:
    """Completed diff payload for a job, or None while it is still running.

    Best-effort: failures (job expired, redis down) read as not-ready so the
    poll endpoint keeps returning ``pending`` instead of 500ing.
    """
    from arq.jobs import Job

    from src.services.thumbnail import get_queue

    queue = await get_queue()
    job = Job(job_id, queue, _deserializer=queue.job_deserializer)
    try:
        return await job.result(timeout=0)
    except Exception:
        return None