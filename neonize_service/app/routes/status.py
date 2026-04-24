from fastapi import APIRouter, Depends, Request
from ..security import verify_token_header

router = APIRouter()


@router.get("/status", dependencies=[Depends(verify_token_header)])
async def status(request: Request):
    wa = request.app.state.wa_client
    return wa.status()
