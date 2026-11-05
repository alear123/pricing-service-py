# app/security.py
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# Activa la integración gráfica para probar tokens desde Swagger UI (/docs)
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.AUTHGO_URL}/users/current",
                headers=headers
            )

        # Token expirado, mal formado o inexistente
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticación inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Error en la validación de credenciales con AuthGo"
            )

        user_data = response.json()

        # Validación extra: Verificar que el usuario no esté deshabilitado en AuthGo
        if not user_data.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario se encuentra deshabilitado en el sistema"
            )

        return user_data

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio AuthGo no disponible para autenticación"
        )

def require_permission(required_permission: str):
    async def permission_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_permissions = current_user.get("permissions", [])
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No posees el permiso necesario: '{required_permission}'"
            )
        return current_user
    return permission_checker