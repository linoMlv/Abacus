"""Supporting documents (justificatifs) attached to entries — T3c.

Security is the point of this module (plan §10/§15.7):

* the accepted content type is **sniffed from the bytes**, never trusted from
  the client; only PDF and raster images pass (no SVG/HTML);
* size is hard-capped and reads are bounded (no memory blow-up);
* storage keys are **server-generated** (``{association_id}/{id}``) — a client
  filename never reaches the filesystem path;
* every object is fetched tenant-scoped via ``owned_or_404`` (cross-tenant →
  404, no existence leak);
* downloads are forced as **attachments** with ``nosniff`` so a browser never
  executes a payload.

Upload/delete are gated by ``ATTACHMENT_MANAGE``; listing/downloading is open to
any active member (a read-only président/CA can consult the proofs).
"""

import re
import unicodedata
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlmodel import Session, asc, select

from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    get_active_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from file_storage import MAX_UPLOAD_BYTES, FileStorage, detect_content_type, get_storage
from models import Ecriture, Justificatif, JustificatifRead

router = APIRouter(prefix="/api/asso/{association_id}", tags=["justificatifs"])


def _sanitize_filename(name: str | None) -> str:
    """Reduce a client filename to a safe display name (never a path)."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFC", base)
    base = re.sub(r"[\x00-\x1f]", "", base).strip()
    base = base[:200]
    return base or "fichier"


def _content_disposition(filename: str, disposition: str) -> str:
    """RFC 6266 disposition header with an ASCII fallback and a UTF-8 form."""
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "fichier"
    ascii_name = ascii_name.replace('"', "")
    return (
        f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    )


def _serve(
    session: Session,
    storage: FileStorage,
    association_id: str,
    justificatif_id: str,
    *,
    inline: bool,
) -> Response:
    """Stream a tenant-owned justificatif, as an attachment or for inline preview.

    Inline responses are sandboxed (``Content-Security-Policy: sandbox``) and
    ``nosniff``, so a (strictly type-validated) PDF/image renders in an iframe/img
    without being able to run script or navigate. Both forms are marked
    non-storable — these are private tenant documents.
    """
    justificatif = owned_or_404(
        session,
        Justificatif,
        justificatif_id,
        association_id,
        "Justificatif introuvable",
    )
    try:
        data = storage.load(justificatif.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable"
        ) from exc

    headers = {
        "Content-Disposition": _content_disposition(
            justificatif.filename, "inline" if inline else "attachment"
        ),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    if inline:
        headers["Content-Security-Policy"] = "sandbox"
        # Override the middleware's default X-Frame-Options: DENY so the preview
        # can be framed by our own SPA (same-origin), while cross-origin framing
        # stays blocked. The sandbox + nosniff posture is unchanged.
        headers["X-Frame-Options"] = "SAMEORIGIN"
    return Response(content=data, media_type=justificatif.content_type, headers=headers)


@router.post(
    "/ecritures/{ecriture_id}/justificatifs",
    response_model=JustificatifRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_justificatif(
    ecriture_id: str,
    file: UploadFile = File(...),
    ctx: AccessContext = Depends(require_permission(Permission.ATTACHMENT_MANAGE)),
    session: Session = Depends(get_session),
    storage: FileStorage = Depends(get_storage),
):
    ecriture = owned_or_404(
        session, Ecriture, ecriture_id, ctx.association_id, "Écriture introuvable"
    )

    # Bounded read: one extra byte tells us the cap was exceeded.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux (5 Mo maximum).",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide."
        )

    # Trust the bytes, not the declared type. Reject anything but PDF / images.
    content_type = detect_content_type(content[:32])
    if content_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format non pris en charge (PDF ou image uniquement).",
        )

    justificatif = Justificatif(
        association_id=ctx.association_id,
        ecriture_id=ecriture.id,
        filename=_sanitize_filename(file.filename),
        content_type=content_type,
        size=len(content),
        storage_key="",  # set below from the generated id
        uploaded_by=ctx.user.id,
    )
    justificatif.storage_key = f"{ctx.association_id}/{justificatif.id}"

    storage.save(justificatif.storage_key, content)
    try:
        session.add(justificatif)
        record_audit(
            session,
            association_id=ctx.association_id,
            actor_user_id=ctx.user.id,
            action=AuditAction.JUSTIFICATIF_UPLOAD,
            target_type="justificatif",
            target_id=justificatif.id,
            detail=justificatif.filename,
        )
        session.commit()
    except Exception:
        # Never leave a stored blob without its metadata row.
        storage.delete(justificatif.storage_key)
        raise
    session.refresh(justificatif)
    return justificatif


@router.get(
    "/ecritures/{ecriture_id}/justificatifs",
    response_model=list[JustificatifRead],
)
def list_justificatifs(
    ecriture_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    owned_or_404(
        session, Ecriture, ecriture_id, ctx.association_id, "Écriture introuvable"
    )
    statement = (
        select(Justificatif)
        .where(
            Justificatif.association_id == ctx.association_id,
            Justificatif.ecriture_id == ecriture_id,
        )
        .order_by(asc(Justificatif.created_at))
    )
    return session.exec(statement).all()


@router.get("/justificatifs/{justificatif_id}/contenu")
def download_justificatif(
    justificatif_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
    storage: FileStorage = Depends(get_storage),
):
    """Download the file as an attachment (forced save, never rendered inline)."""
    return _serve(session, storage, ctx.association_id, justificatif_id, inline=False)


@router.get("/justificatifs/{justificatif_id}/apercu")
def preview_justificatif(
    justificatif_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
    storage: FileStorage = Depends(get_storage),
):
    """Serve the file inline for an in-app preview (sandboxed, nosniff)."""
    return _serve(session, storage, ctx.association_id, justificatif_id, inline=True)


@router.delete(
    "/justificatifs/{justificatif_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_justificatif(
    justificatif_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ATTACHMENT_MANAGE)),
    session: Session = Depends(get_session),
    storage: FileStorage = Depends(get_storage),
):
    justificatif = owned_or_404(
        session,
        Justificatif,
        justificatif_id,
        ctx.association_id,
        "Justificatif introuvable",
    )
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.JUSTIFICATIF_DELETE,
        target_type="justificatif",
        target_id=justificatif.id,
        detail=justificatif.filename,
    )
    storage_key = justificatif.storage_key
    session.delete(justificatif)
    session.commit()
    storage.delete(storage_key)
