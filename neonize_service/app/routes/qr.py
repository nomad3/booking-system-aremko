import io
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from ..security import verify_token_flexible

router = APIRouter()


@router.get("/qr", dependencies=[Depends(verify_token_flexible)])
async def get_qr(request: Request):
    wa = request.app.state.wa_client
    status = wa.status()
    if status["connected"]:
        return {
            "status": "already_connected",
            "message": "La sesión ya está autenticada; no se requiere QR.",
        }
    qr_data = wa.get_qr_data()
    if not qr_data:
        raise HTTPException(
            status_code=404,
            detail="QR todavía no está listo. Espera 5-10 segundos y reintenta.",
        )
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
