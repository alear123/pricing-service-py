from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Optional
from app.models.pricing import PricingCreate
from app.models.mov_pricing import MovType
from app.services.pricing_service import pricing_service
from app.security import get_current_user, require_permission

router = APIRouter(prefix="/pricing", tags=["Pricing"])

@router.get("/{article_id}", status_code=status.HTTP_200_OK)
async def get_price(
    article_id: str,
    current_user: dict = Depends(get_current_user) 
):
    """Obtiene el precio actual de un artículo y emite el evento 'pricing.queried'."""
    # Validar parámetro de entrada HTTP
    if not article_id or not article_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'article_id' es obligatorio y no puede estar vacío."
        )

    try:
        return await pricing_service.get_price(article_id.strip())
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("", status_code=status.HTTP_200_OK)
async def create_or_update_price(
    pricing_data: PricingCreate,
    mov_type: MovType = Query(MovType.SET, alias="movType", description="Tipo de movimiento: SET, INCR o DECR"),
    current_user: dict = Depends(require_permission("admin"))
):
    """Establece, incrementa o decrementa el precio de un artículo."""
    user_login = current_user.get("login") if current_user else None
    
    # Validar presencia de credencial de usuario
    if not user_login or not user_login.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario autenticado no contiene una identificación ('login') válida."
        )

    try:
        return await pricing_service.create_or_update_price(
            pricing_data=pricing_data, 
            mov_type=mov_type,
            user_login=user_login.strip()
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando la solicitud de precio: {str(e)}"
        )