from fastapi import APIRouter, Depends, status, Header, HTTPException
from app.models.coupon import CouponCreate, CouponUpdate
from app.models.coupon_usage import CouponUsageCreate
from app.services.coupon_service import coupon_service
from app.security import get_current_user, require_permission 

router = APIRouter(prefix="/coupons", tags=["Coupons"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_coupon(
    coupon_data: CouponCreate,
    current_user: dict = Depends(require_permission("admin")) 
):
    """Crea un nuevo cupón de descuento y emite 'coupon.created'."""
    # Validar que la payload recibida no venga vacía en sus campos clave
    if not coupon_data or not coupon_data.couponCode or not coupon_data.couponCode.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código del cupón es obligatorio."
        )

    try:
        return await coupon_service.create_coupon(coupon_data)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando la creación del cupón: {str(e)}"
        )

@router.put("/{coupon_code}", status_code=status.HTTP_200_OK)
async def update_coupon(
    coupon_code: str, 
    update_data: CouponUpdate,
    current_user: dict = Depends(require_permission("admin"))
):
    """Actualiza la fecha de expiración o descuento de un cupón existente."""
    # Validación HTTP de parámetro de ruta
    if not coupon_code or not coupon_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'coupon_code' en la URL es obligatorio."
        )

    try:
        return await coupon_service.update_coupon(coupon_code.strip(), update_data)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/apply", status_code=status.HTTP_200_OK)
async def apply_coupon(
    request: CouponUsageCreate,
    authorization: str = Header(...), 
    current_user: dict = Depends(get_current_user)
):
    """Valida y aplica un cupón a un carrito de compra emitiendo 'coupon.applied'."""
    # Validar formato del header Authorization
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'Authorization' inválido o ausente. Debe usar el esquema Bearer."
        )

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token Bearer proporcionado está vacío."
        )
    
    user_login = current_user.get("login") if current_user else None
    if not user_login or not user_login.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario autenticado no posee una identificación 'login' válida."
        )

    if not request or not request.couponCode or not request.couponCode.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir un 'couponCode' válido en el cuerpo de la solicitud."
        )

    try:
        return await coupon_service.apply_coupon(
            usage_data=request, 
            user_login=user_login.strip(),
            token=token 
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al aplicar el cupón: {str(e)}"
        )