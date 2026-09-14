from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/status")
async def get_status(request: Request):
    app_state = request.app.state.app_state
    return app_state.get_status()
