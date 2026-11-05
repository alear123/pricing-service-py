import httpx
from fastapi import HTTPException, status
from app.config import settings

# Leemos la URL desde la configuración para que tome el valor de Docker (prod-cartgo-go:3003)
CART_GO_URL = getattr(settings, "CARTGO_URL", "http://prod-cartgo-go:3003")

async def validate_cart_exists(token: str) -> dict:
    """
    Consulta a CartGo (GET /cart) pasando el token del usuario.
    Si el carrito existe y está activo, retorna sus datos.
    """
    # Evitar duplicar el prefijo 'Bearer ' si ya viene en la variable token
    clean_token = token.replace("Bearer ", "").strip()
    headers = {"Authorization": f"Bearer {clean_token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{CART_GO_URL}/cart", headers=headers)
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No se pudo conectar con el servicio de Carrito (CartGo): {str(e)}"
            )

    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un carrito activo para este usuario."
        )
    elif response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no válido o expirado para CartGo."
        )
    elif response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al obtener la información del carrito en CartGo."
        )

    cart_data = response.json()
    
    # Validar si el carrito está deshabilitado
    if not cart_data.get("enabled", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El carrito se encuentra deshabilitado."
        )

    return cart_data