from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from ..security import verify_token_header

router = APIRouter()


class SendRequest(BaseModel):
    jid: str = Field(..., description="JID destino, ej: '56912345678@s.whatsapp.net'")
    text: str = Field(..., min_length=1, max_length=4000)


@router.post("/send", dependencies=[Depends(verify_token_header)])
async def send(request: Request, body: SendRequest):
    wa = request.app.state.wa_client
    if not wa.status()["connected"]:
        raise HTTPException(status_code=503, detail="WA client not connected")
    try:
        await wa.send_text(body.jid, body.text)
        return {"status": "sent", "jid": body.jid}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"send_failed: {str(e)[:200]}")
