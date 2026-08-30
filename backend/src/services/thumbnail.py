"""ARQ thumbnail worker: async thumbnail and 3D preview generation."""

import io
import os
import tempfile
from pathlib import Path
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from src.core.config import settings
from src.models.file import ThumbnailStatus


# ── ARQ Worker Settings ───────────────────────────────────

class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions: list = [
        "src.services.thumbnail.generate_thumbnails",
        "src.services.thumbnail.generate_3d_preview",
        "src.services.diffing.generate_revision_diff",
    ]
    job_timeout = 120  # Default 120s
    max_jobs = 10
    allow_abort_jobs = True

    # Job-specific timeouts
    job_timeouts = {
        "generate_3d_preview": 180,
        "generate_revision_diff": 300,
    }


# ── Redis Queue Helper ───────────────────────────────────

_queue_pool = None


async def get_queue():
    """Get or create an ARQ queue connection pool."""
    global _queue_pool
    if _queue_pool is None:
        _queue_pool = await create_pool(
            RedisSettings.from_dsn(settings.REDIS_URL)
        )
    return _queue_pool


async def enqueue_thumbnail_job(file_id: str, s3_key: str, file_type: str) -> None:
    """Enqueue a thumbnail generation job."""
    queue = await get_queue()
    await queue.enqueue_job(
        "src.services.thumbnail.generate_thumbnails",
        file_id=file_id,
        s3_key=s3_key,
        file_type=file_type,
        _job_id=f"thumbnail:{file_id}",
    )


async def enqueue_preview_job(file_id: str, s3_key: str, file_type: str) -> None:
    """Enqueue a 3D preview generation job (IFC/OBJ/STL only)."""
    queue = await get_queue()
    await queue.enqueue_job(
        "src.services.thumbnail.generate_3d_preview",
        file_id=file_id,
        s3_key=s3_key,
        file_type=file_type,
        _job_id=f"preview:{file_id}",
    )


# ── Thumbnail Generation ──────────────────────────────────

async def generate_thumbnails(ctx: dict, file_id: str, s3_key: str, file_type: str) -> dict:
    """Generate small (200x200) and medium (600x600) WebP thumbnails.

    Called by ARQ worker.
    """
    from src.services.file import _get_lazy_s3_client
    from src.core.config import settings as cfg

    s3_client = _get_lazy_s3_client()
    result = {"status": "started", "file_id": file_id}

    try:
        # Download file from S3 to temp location
        suffix = f".{file_type}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        s3_client.download_file(cfg.S3_BUCKET, s3_key, tmp_path)

        # Update status to processing
        await _update_thumbnail_status(file_id, ThumbnailStatus.processing)

        # Generate thumbnails based on file type
        if file_type in ("png", "jpg", "jpeg", "webp"):
            _generate_raster_thumbnail(tmp_path, file_type)
        elif file_type == "pdf":
            _generate_pdf_thumbnail(tmp_path)
        elif file_type in ("dxf", "dwg"):
            _generate_cad_thumbnail(tmp_path, file_type)
        elif file_type in ("obj", "stl", "ifc"):
            _generate_3d_thumbnail(tmp_path, file_type)
        else:
            # SKP, RVT — unsupported
            await _update_thumbnail_status(file_id, ThumbnailStatus.unsupported)
            return {"status": "unsupported", "file_id": file_id}

        # Upload thumbnails to S3
        small_key = f"thumbnails/{file_id}/small.webp"
        medium_key = f"thumbnails/{file_id}/medium.webp"

        for size_name, size_key, dims in [
            ("small", small_key, (200, 200)),
            ("medium", medium_key, (600, 600)),
        ]:
            thumbnail_data = _create_webp_thumbnail(tmp_path, file_type, dims)
            if thumbnail_data:
                s3_client.put_object(
                    Bucket=cfg.S3_BUCKET,
                    Key=size_key,
                    Body=thumbnail_data,
                    ContentType="image/webp",
                )

        # Update file record with thumbnail keys
        await _save_thumbnail_keys(file_id, small_key, medium_key)
        await _update_thumbnail_status(file_id, ThumbnailStatus.complete)

        result["status"] = "complete"
    except Exception as e:
        await _update_thumbnail_status(file_id, ThumbnailStatus.failed)
        result["status"] = "failed"
        result["error"] = str(e)
    finally:
        # Cleanup temp file
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return result


# ── 3D Preview Generation ─────────────────────────────────

async def generate_3d_preview(ctx: dict, file_id: str, s3_key: str, file_type: str) -> dict:
    """Generate a glTF/GLB 3D preview from IFC/OBJ/STL files.

    Called by ARQ worker.
    """
    from src.services.file import _get_lazy_s3_client
    from src.core.config import settings as cfg

    s3_client = _get_lazy_s3_client()
    result = {"status": "started", "file_id": file_id}

    try:
        suffix = f".{file_type}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        s3_client.download_file(cfg.S3_BUCKET, s3_key, tmp_path)

        preview_data = None

        if file_type == "ifc":
            preview_data = _convert_ifc_to_gltf(tmp_path)
        elif file_type in ("obj", "stl"):
            preview_data = _convert_mesh_to_gltf(tmp_path, file_type)

        if preview_data:
            preview_key = f"previews/{file_id}/model.glb"
            s3_client.put_object(
                Bucket=cfg.S3_BUCKET,
                Key=preview_key,
                Body=preview_data,
                ContentType="model/gltf-binary",
            )
            await _save_preview_key(file_id, preview_key, "complete")

        result["status"] = "complete"
    except Exception as e:
        await _save_preview_key(file_id, None, "failed")
        result["status"] = "failed"
        result["error"] = str(e)
    finally:
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return result


# ── Internal Helpers ──────────────────────────────────────

def _generate_raster_thumbnail(path: str, file_type: str) -> None:
    """Validate that a raster image can be opened."""
    from PIL import Image
    Image.open(path).verify()


def _generate_pdf_thumbnail(path: str) -> None:
    """Validate that a PDF can be opened (page 1)."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    if len(doc) > 0:
        doc[0].get_pixmap()
    doc.close()


def _generate_cad_thumbnail(path: str, file_type: str) -> None:
    """Validate that a CAD file can be processed."""
    if file_type == "dxf":
        import ezdxf
        ezdxf.readfile(path)


def _generate_3d_thumbnail(path: str, file_type: str) -> None:
    """Validate that a 3D model can be loaded."""
    import trimesh
    trimesh.load(path)


def _create_webp_thumbnail(path: str, file_type: str, size: tuple[int, int]) -> bytes | None:
    """Create a WebP thumbnail at the given dimensions.

    Returns the thumbnail bytes, or None if unsupported.
    """
    from PIL import Image

    try:
        if file_type == "pdf":
            import fitz
            doc = fitz.open(path)
            page = doc[0]
            pix = page.get_pixmap(dpi=72)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
        elif file_type in ("dxf",):
            # For DXF, render with matplotlib
            img = _render_dxf_to_image(path, size)
            if img is None:
                return None
        elif file_type in ("obj", "stl", "ifc"):
            # For 3D, render with trimesh scene
            img = _render_3d_to_image(path, file_type, size)
            if img is None:
                return None
        else:
            img = Image.open(path)

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Resize maintaining aspect ratio, then center-crop
        img.thumbnail(size, Image.LANCZOS)

        # Create canvas and center
        canvas = Image.new("RGB", size, (255, 255, 255))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        canvas.paste(img, offset)

        # Encode as WebP
        output = io.BytesIO()
        canvas.save(output, format="WEBP", quality=85)
        return output.getvalue()
    except Exception:
        return None


def _render_dxf_to_image(path: str, size: tuple[int, int]) -> Any:
    """Render a DXF file to a PIL Image using matplotlib."""
    try:
        import ezdxf
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import matplotlib.pyplot as plt

        doc = ezdxf.readfile(path)
        msp = doc.modelspace()

        fig = plt.figure(figsize=(size[0] / 100, size[1] / 100), dpi=100)
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        from PIL import Image
        return Image.open(buf)
    except Exception:
        return None


def _render_3d_to_image(path: str, file_type: str, size: tuple[int, int]) -> Any:
    """Render a 3D model to a PIL Image using trimesh."""
    try:
        import trimesh
        scene = trimesh.load(path)

        if isinstance(scene, trimesh.Scene):
            # Take a snapshot of the scene
            png = scene.save_image(resolution=size)
            from PIL import Image
            return Image.open(io.BytesIO(png))
        elif isinstance(scene, trimesh.Trimesh):
            # Single mesh render
            png = scene.scene().save_image(resolution=size)
            from PIL import Image
            return Image.open(io.BytesIO(png))
    except Exception:
        return None

    return None


def _convert_ifc_to_gltf(path: str) -> bytes | None:
    """Convert an IFC file to glTF binary (GLB) using IfcOpenShell + trimesh."""
    try:
        import ifcopenshell
        import trimesh

        ifc_file = ifcopenshell.open(path)
        meshes = []

        # Extract geometry from IFC elements
        from ifcopenshell.geom import create_shape, settings as geom_settings
        geom_settings.set(geom_settings.USE_PYTHON_OPENCASCADE, True)

        products = ifc_file.by_type("IfcProduct")
        for product in products[:200]:  # Limit for performance
            try:
                shape = create_shape(geom_settings, product)
                if shape and shape.geometry:
                    verts = shape.geometry.verts
                    faces = shape.geometry.faces
                    if verts and faces:
                        mesh = trimesh.Trimesh(
                            vertices=verts.reshape(-1, 3),
                            faces=faces.reshape(-1, 3),
                        )
                        meshes.append(mesh)
            except Exception:
                continue

        if meshes:
            combined = trimesh.util.concatenate(meshes)
            return combined.export(file_type="glb")
    except Exception:
        pass

    return None


def _convert_mesh_to_gltf(path: str, file_type: str) -> bytes | None:
    """Convert OBJ/STL to glTF binary (GLB) using trimesh."""
    try:
        import trimesh
        mesh = trimesh.load(path)

        if isinstance(mesh, trimesh.Scene):
            combined = mesh.dump(concatenate=True)
            if combined:
                return combined.export(file_type="glb")
        elif isinstance(mesh, trimesh.Trimesh):
            return mesh.export(file_type="glb")
    except Exception:
        pass

    return None


# ── Database Update Helpers ───────────────────────────────

async def _update_thumbnail_status(file_id: str, status: ThumbnailStatus) -> None:
    """Update the thumbnail_status for a design file."""
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.models.file import DesignFile
    from src.core.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            update(DesignFile)
            .where(DesignFile.id == file_id)
            .values(thumbnail_status=status)
        )
        await session.commit()


async def _save_thumbnail_keys(
    file_id: str,
    small_key: str,
    medium_key: str,
) -> None:
    """Save thumbnail S3 keys to the file record."""
    from sqlalchemy import update
    from src.models.file import DesignFile
    from src.core.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            update(DesignFile)
            .where(DesignFile.id == file_id)
            .values(
                thumbnail_small_key=small_key,
                thumbnail_medium_key=medium_key,
                thumbnail_status=ThumbnailStatus.complete,
            )
        )
        await session.commit()


async def _save_preview_key(
    file_id: str,
    preview_key: str | None,
    status: str,
) -> None:
    """Save 3D preview S3 key and status to the file record."""
    from sqlalchemy import update
    from src.models.file import DesignFile
    from src.core.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            update(DesignFile)
            .where(DesignFile.id == file_id)
            .values(
                preview_glb_key=preview_key,
                preview_status=status,
            )
        )
        await session.commit()
