"""Tests for T4 Phase 2 (server-side visual diffing)."""

import io
import uuid

import fitz
import pytest
from PIL import Image, ImageDraw

from src.models.project import Project
from src.services import diffing


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Diffing Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


def _make_pdf_bytes(page2_change: tuple | None = None) -> bytes:
    """Deterministic 2-page PDF: page 1 identical, page 2 gains a red box."""
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=400, height=300)
        page.draw_rect(fitz.Rect(50, 50, 200, 120), color=(0.1, 0.1, 0.1), width=2)
        page.draw_circle(fitz.Point(120, 200), 30, color=(0.2, 0.2, 0.6), width=2)
        if page2_change and i == 1:
            x0, y0, x1, y1 = page2_change
            page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0.8, 0, 0), width=2, fill=(0.9, 0.2, 0.2))
    return doc.tobytes()


def _big_pdf_bytes(page_count: int) -> bytes:
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=100, height=100)
    return doc.tobytes()


def _png_bytes(red_box: bool = False) -> bytes:
    img = Image.new("RGB", (200, 150), "white")
    if red_box:
        ImageDraw.Draw(img).rectangle([20, 20, 80, 80], fill="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def test_pdf_diff_ready_with_per_page_metrics(fake_s3):
    """Two real PDFs produce ready status, per-page ratios, and regions."""
    fake_s3.objects["uploads/from.pdf"] = _make_pdf_bytes()
    fake_s3.objects["uploads/to.pdf"] = _make_pdf_bytes(page2_change=(250, 180, 330, 260))

    computed = await diffing.generate_comparison_diff(
        file_id=str(uuid.uuid4()),
        from_key="uploads/from.pdf",
        to_key="uploads/to.pdf",
        file_type="pdf",
        from_version=1,
        to_version=2,
        enforce_budget=True,
    )

    assert computed is not None
    assert computed["status"] == "ready"
    assert computed["page_count"] == 2
    p1, p2 = computed["pages"]
    assert p1["changed"] is False
    assert p1["diff_ratio"] <= 0.005
    assert p2["changed"] is True
    assert p2["diff_ratio"] > 0.005
    assert p2["regions"], "expected at least one change region"
    for r in p2["regions"]:
        assert 0 <= r["x"] < r["x"] + r["w"] <= 400
        assert 0 <= r["y"] < r["y"] + r["h"] <= 300
        assert r["kind"] in ("added", "removed", "modified")
    # Fake S3 presigns derived renders for changed pages.
    assert p2["from_url"] is not None
    assert p2["to_url"] is not None
    assert p2["overlay_url"] is not None


async def test_pdf_sync_budget_enforces_async_path(fake_s3):
    fake_s3.objects["uploads/from.pdf"] = _make_pdf_bytes()
    fake_s3.objects["uploads/big.pdf"] = _big_pdf_bytes(21)

    # enforce_budget=True returns None (caller then enqueues the ARQ job).
    over_budget = await diffing.generate_comparison_diff(
        file_id=str(uuid.uuid4()),
        from_key="uploads/from.pdf",
        to_key="uploads/big.pdf",
        file_type="pdf",
        from_version=1,
        to_version=2,
        enforce_budget=True,
    )
    assert over_budget is None

    # Worker path (no budget) completes.
    worker_result = await diffing.generate_comparison_diff(
        file_id=str(uuid.uuid4()),
        from_key="uploads/from.pdf",
        to_key="uploads/big.pdf",
        file_type="pdf",
        from_version=1,
        to_version=2,
        enforce_budget=False,
    )
    assert worker_result is not None
    assert worker_result["page_count"] == 21


async def test_image_diff_ready_synchronously(fake_s3):
    fake_s3.objects["uploads/src.png"] = _png_bytes()
    fake_s3.objects["uploads/dst.png"] = _png_bytes(red_box=True)

    result = await diffing.generate_comparison_diff(
        file_id=str(uuid.uuid4()),
        from_key="uploads/src.png",
        to_key="uploads/dst.png",
        file_type="png",
        from_version=1,
        to_version=2,
        enforce_budget=True,
    )
    assert result is not None
    assert result["status"] == "ready"
    assert result["page_count"] == 1
    assert result["pages"][0]["changed"] is True
    assert 0 < result["pages"][0]["diff_ratio"] <= 1


async def test_compare_route_returns_diff_key(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    """Compare endpoint returns an additive `diff` payload (T4 Phase 2)."""
    file, _ = await seed_file(project.id, test_architect.id, content=_make_pdf_bytes())

    key2 = f"uploads/{project.id}/{uuid.uuid4()}/to.pdf"
    fake_s3.objects[key2] = _make_pdf_bytes(page2_change=(250, 180, 330, 260))
    resp = await client.post(
        f"/api/files/{file.id}/upload-complete", params={"key": key2}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        f"/api/files/{file.id}/compare",
        json={"from_version": 1, "to_version": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["supported"] is True
    assert body["from"]["version_number"] == 1
    assert body["to"]["version_number"] == 2

    diff = body["diff"]
    assert diff["status"] == "ready"
    assert diff["page_count"] == 2
    p1, p2 = diff["pages"]
    assert p1["changed"] is False
    assert p2["changed"] is True
    assert p2["regions"]


async def test_poll_route_rejects_malformed_job_id(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    """Malformed or foreign job ids 404 without touching Redis."""
    file, _ = await seed_file(project.id, test_architect.id)

    resp = await client.get(
        f"/api/files/{file.id}/compare/diff:notafile:1:2", headers=auth_headers
    )
    assert resp.status_code == 404
    resp_foreign = await client.get(
        f"/api/files/{file.id}/compare/diff:{uuid.uuid4()}:1:2", headers=auth_headers
    )
    assert resp_foreign.status_code == 404


async def test_unit_region_merge_and_kind_heuristic():
    """Pure-function coverage: box merge stays in-bounds, kinds are valid."""
    a = Image.new("RGB", (120, 90), "white")
    b = Image.new("RGB", (120, 90), "white")
    ImageDraw.Draw(b).rectangle([10, 10, 50, 50], fill="black")

    ratio, regions = diffing._diff_image_pair(a, b)
    assert ratio > 0
    assert regions
    for r in regions:
        assert r["kind"] in ("added", "removed", "modified")
        assert 0 <= r["x"] < r["x"] + r["w"] <= 120
        assert 0 <= r["y"] < r["y"] + r["h"] <= 90

    assert diffing.unavailable_payload("x")["status"] == "unavailable"
    assert diffing.unavailable_payload("x")["pages"] == []