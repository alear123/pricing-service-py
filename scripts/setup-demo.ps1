# Prepara usuarios de demo y muestra sus tokens.
# Requiere el ecosistema levantado:  docker compose -f docker-compose.ecosystem.yml up -d --build
# Uso (desde la raiz del repo):       powershell -ExecutionPolicy Bypass -File scripts\setup-demo.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)   # raiz del repo, donde esta el docker-compose
$AuthUrl = "http://localhost:3000"
$Password = "demo1234"
$Compose = @("compose", "-f", "docker-compose.ecosystem.yml")

# Nota: AuthGo exige un login de al menos 5 caracteres
function New-DemoUser([string]$login, [string]$name) {
    $body = @{ login = $login; name = $name; password = $Password } | ConvertTo-Json
    try {
        Invoke-RestMethod -Method Post -Uri "$AuthUrl/users/signup" -ContentType "application/json" -Body $body | Out-Null
        Write-Host "  Usuario '$login' creado."
    } catch {
        # AuthGo responde un error si el usuario ya existe; se muestra el motivo por si es otro (p. ej. validacion)
        Write-Host "  No se creo '$login' (probablemente ya existe): $($_.ErrorDetails.Message)"
    }
}

function Get-Token([string]$login) {
    $body = @{ login = $login; password = $Password } | ConvertTo-Json
    return (Invoke-RestMethod -Method Post -Uri "$AuthUrl/users/signin" -ContentType "application/json" -Body $body).token
}

Write-Host "Esperando a AuthGo en $AuthUrl ..."
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -Uri "$AuthUrl/users/current" -UseBasicParsing -TimeoutSec 2 | Out-Null; break }
    catch { if ($_.Exception.Response) { break } }   # cualquier respuesta HTTP (401) significa que esta arriba
    Start-Sleep -Seconds 2
}

Write-Host "Creando usuarios..."
New-DemoUser "admin" "Admin Demo"
New-DemoUser "usuario" "Usuario Demo"

Write-Host "Otorgando permiso 'admin' al usuario 'admin'..."
# Comillas simples dentro del JS: PowerShell 5.1 rompe las comillas dobles al pasarlas a programas externos
& docker @Compose exec -T mongo mongosh auth --quiet --eval 'db.users.updateOne({login: ''admin''}, {$addToSet: {permissions: ''admin''}})' | Out-Null

# Se inicia sesion despues de otorgar el permiso, para que el token refleje los permisos actualizados
$adminToken = Get-Token "admin"
$userToken = Get-Token "usuario"

Write-Host ""
Write-Host "Listo. Pega estos tokens en 'Authorize' de http://localhost:8000/docs"
Write-Host ""
Write-Host "ADMIN (login: admin / $Password):"
Write-Host $adminToken
Write-Host ""
Write-Host "USUARIO (login: usuario / $Password):"
Write-Host $userToken
