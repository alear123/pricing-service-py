# Pricing Service

Microservicio de **precios y cupones de descuento** para una plataforma de e-commerce basada en microservicios. Desarrollado con **Python + FastAPI**, persiste en **MongoDB** y se comunica con el resto del ecosistema de forma **asíncrona mediante RabbitMQ** y de forma **síncrona vía HTTP**.

[![Tests](https://github.com/alear123/pricing-service-py/actions/workflows/tests.yml/badge.svg)](https://github.com/alear123/pricing-service-py/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?logo=rabbitmq&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

> 📚 **Contexto:** proyecto académico de la materia **Arquitectura de Microservicios**. El servicio se integra al ecosistema e-commerce provisto por la cátedra ([nmarsollier/ecommerce](https://github.com/nmarsollier/ecommerce)), que incluye los servicios de autenticación, carrito y órdenes. **Este microservicio (precios y cupones) es de desarrollo propio.**

---

## Funcionalidades

**Precios**
- Consulta del precio vigente de un artículo.
- Alta y modificación de precios con tres tipos de movimiento: `SET` (fijar), `INCR` (incrementar) y `DECR` (decrementar).
- **Auditoría**: cada cambio de precio queda registrado con el tipo de movimiento, el valor y el usuario que lo realizó.
- Reglas de negocio: el precio nunca puede quedar negativo y no se puede decrementar un artículo sin precio previo.

**Cupones**
- Alta y modificación de cupones de tipo **porcentaje** (`PERCENTAGE`) o **monto fijo** (`FIXED`).
- Validación de vigencia (fecha de inicio y expiración) y **límite global de usos**.
- Aplicación de un cupón al carrito del usuario: calcula subtotal, descuento y total, y **reserva el cupón temporalmente**.
- Confirmación del uso del cupón cuando se concreta la orden (vía evento).

---

## Arquitectura

```mermaid
flowchart LR
    Client([Cliente / Frontend])

    subgraph Pricing Service
        API[FastAPI<br/>controllers]
        SVC[services]
        REPO[repositories]
    end

    Mongo[(MongoDB)]
    Rabbit{{RabbitMQ}}
    Auth[AuthGo]
    Cart[CartGo]
    Orders[OrdersGo]

    Client -->|HTTP + JWT| API
    API --> SVC --> REPO --> Mongo
    API -->|valida token| Auth
    SVC -->|obtiene carrito| Cart
    SVC -->|publica eventos<br/>amq.direct| Rabbit
    Orders -->|order_placed<br/>fanout| Rabbit
    Rabbit -->|consume| SVC
```

El código sigue una **arquitectura en capas**:

```
app/
├── controllers/    # Endpoints HTTP (FastAPI routers) y validación de entrada
├── services/       # Lógica de negocio
├── repositories/   # Acceso a datos (MongoDB con Motor, async)
├── models/         # Modelos Pydantic (requests, entidades y eventos)
├── clients/        # Clientes HTTP hacia otros microservicios (CartGo)
├── events/         # Consumidores de eventos de RabbitMQ
├── security.py     # Autenticación y autorización delegada en AuthGo
├── rabbitmq.py     # Conexión, publicación y consumo de mensajes
├── database.py     # Conexión a MongoDB
└── config.py       # Configuración por variables de entorno
```

---

## Flujo de aplicación de un cupón

El cupón no se descuenta en el momento de aplicarlo, sino cuando la orden se confirma. Así un cupón no se consume si el usuario abandona la compra.

```mermaid
sequenceDiagram
    actor U as Usuario
    participant P as Pricing Service
    participant C as CartGo
    participant DB as MongoDB
    participant R as RabbitMQ
    participant O as OrdersGo

    U->>P: POST /coupons/apply {couponCode}
    P->>C: GET /cart (token del usuario)
    C-->>P: carrito activo + artículos
    P->>DB: valida vigencia, límite de usos y que el carrito no tenga cupón
    P->>DB: calcula subtotal con los precios de cada artículo
    P->>DB: guarda reserva en pending_coupons (TTL 30 min)
    P-->>U: subtotal, descuento y total

    O->>R: order_placed (fanout)
    R->>P: evento de orden creada
    P->>DB: toma y elimina la reserva, registra el uso
    P->>R: coupon.applied / coupon.failed / coupon.processed
```

Las reservas que no se concretan en una orden **expiran solas a los 30 minutos** gracias a un índice TTL de MongoDB, sin necesidad de un job de limpieza.

---

## API

La documentación interactiva (Swagger) está disponible en **`http://localhost:8000/docs`**.

Todos los endpoints (excepto `/health`) requieren el header `Authorization: Bearer <token>`. El token se valida contra el servicio **AuthGo**.

| Método | Endpoint | Permiso | Descripción |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `GET` | `/pricing/{article_id}` | usuario | Precio vigente de un artículo |
| `POST` | `/pricing?movType=SET\|INCR\|DECR` | `admin` | Fija, incrementa o decrementa un precio |
| `POST` | `/coupons` | `admin` | Crea un cupón |
| `PUT` | `/coupons/{coupon_code}` | `admin` | Modifica límite de usos, expiración o descuento |
| `POST` | `/coupons/apply` | usuario | Aplica un cupón al carrito del usuario |

### Ejemplos

**Fijar el precio de un artículo**
```http
POST /pricing?movType=SET
Authorization: Bearer <token-admin>
Content-Type: application/json

{ "articleId": "art-123", "price": 1500.0 }
```

**Crear un cupón**
```http
POST /coupons
Authorization: Bearer <token-admin>
Content-Type: application/json

{
  "couponCode": "VERANO20",
  "usageLimit": 100,
  "discountType": "PERCENTAGE",
  "discountValue": 20,
  "startDate": "2025-12-01T00:00:00",
  "expirationDate": "2026-03-01T00:00:00"
}
```

**Aplicar un cupón**
```http
POST /coupons/apply
Authorization: Bearer <token-usuario>
Content-Type: application/json

{ "couponCode": "VERANO20" }
```
```json
{
  "status": "valid",
  "couponCode": "VERANO20",
  "cartId": "...",
  "discountType": "PERCENTAGE",
  "discountValue": 20.0,
  "subtotal": 3000.0,
  "discountAmount": 600.0,
  "totalWithDiscount": 2400.0,
  "appliedBy": "usuario"
}
```

---

## Eventos (RabbitMQ)

### Publicados — exchange `amq.direct`

| Routing key | Cuándo se emite |
|---|---|
| `pricing.queried` | Se consulta el precio de un artículo |
| `pricing.updated` | Se crea o modifica un precio |
| `coupon.created` | Se crea un cupón |
| `coupon.applied` | Se confirmó el uso de un cupón en una orden (`SUCCESS`) |
| `coupon.failed` | No se pudo registrar el uso (`LIMIT_EXCEEDED` o `ERROR`) |
| `coupon.processed` | La orden no tenía cupón reservado (`NOT_APPLIED`) o el cupón ya no existe (`FAILED`) |

### Consumidos

| Exchange | Tipo | Cola | Acción |
|---|---|---|---|
| `order_placed` | fanout | `pricing_place_order_queue` | Confirma el uso del cupón reservado para el carrito de la orden |

---

## Modelo de datos (MongoDB)

| Colección | Contenido |
|---|---|
| `pricings` | Precio vigente por artículo |
| `mov_pricings` | Historial de auditoría de cambios de precio |
| `coupons` | Definición de cupones |
| `coupon_usages` | Usos confirmados de cupones (por carrito y orden) |
| `pending_coupons` | Reservas temporales de cupones (índice TTL de 30 min) |

---

## Cómo ejecutarlo

### Ecosistema completo con un solo comando (recomendado)

`docker-compose.ecosystem.yml` levanta todo lo necesario para probar el servicio de punta a punta: MongoDB, RabbitMQ, los servicios de la cátedra (auth, catálogo, carrito y órdenes), construidos desde sus repositorios públicos, y este microservicio.

```bash
docker compose -f docker-compose.ecosystem.yml up -d --build
```

La primera vez tarda varios minutos porque compila los servicios de la cátedra. Después, el proyecto `ecommerce-demo` se inicia y detiene desde Docker Desktop con un clic.

Luego, para crear un usuario admin y uno común y obtener sus tokens (en Windows):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-demo.ps1
```

| Servicio | URL |
|---|---|
| Pricing Service (Swagger) | http://localhost:8000/docs |
| Front de la cátedra (login, catálogo, carrito, checkout) | http://localhost:4200 |
| RabbitMQ Management | http://localhost:15672 (`guest` / `guest`) |
| AuthGo / Catalog / Cart / Orders | http://localhost:3000 / 3002 / 3003 / 3004 |

### Integrado a un ecosistema ya levantado

Si el ecosistema ya está corriendo según las instrucciones del repositorio [nmarsollier/ecommerce](https://github.com/nmarsollier/ecommerce), el servicio se conecta a la red Docker `ecommerce-net`, que se crea y vincula a mano:

```bash
docker network create ecommerce-net
docker network connect ecommerce-net ec-mongo
docker network connect ecommerce-net ec-rabbitmq
docker network connect ecommerce-net prod-auth-go
docker network connect ecommerce-net prod-cartgo-go
```

Y después:

```bash
docker compose up --build
```

El servicio queda disponible en `http://localhost:8000` y Swagger en `http://localhost:8000/docs`.

### En local

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajustar las URLs si hace falta
python main.py
```

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `PORT` | Puerto HTTP | `8000` |
| `MONGODB_URI` | URI de conexión a MongoDB | `mongodb://ec-mongo:27017` |
| `MONGODB_DB_NAME` | Nombre de la base de datos | `coupons_db` |
| `RABBITMQ_URL` | URL de conexión a RabbitMQ | `amqp://guest:guest@ec-rabbitmq:5672/` |
| `RABBITMQ_EXCHANGE` | Exchange donde se publican los eventos | `amq.direct` |
| `AUTHGO_URL` | URL del servicio de autenticación | `http://prod-auth-go:3000` |
| `CARTGO_URL` | URL del servicio de carrito | `http://prod-cartgo-go:3003` |

---

## Tests

Tests unitarios de la lógica de negocio (`services`) y de la capa HTTP (`controllers`). MongoDB, RabbitMQ, AuthGo y CartGo se reemplazan por mocks, por lo que **no se necesita levantar ninguna dependencia**. Se ejecutan automáticamente en cada push con **GitHub Actions** (Python 3.11 y 3.13).

```bash
pip install -r requirements-dev.txt
pytest
```

Qué cubren:
- Movimientos de precio `SET` / `INCR` / `DECR` y sus reglas (no negativos, no decrementar sin precio previo, auditoría).
- Cálculo de descuentos porcentuales y fijos (el descuento fijo nunca supera el subtotal).
- Validaciones de cupones: vigencia, límite de usos, duplicados y un solo cupón por carrito.
- Procesamiento del evento de orden creada y los eventos resultantes.
- Autorización por permisos (`admin`) y traducción de errores de negocio a HTTP 400.

---

## Decisiones de diseño

- **Arquitectura en capas** (controller → service → repository): separa la capa HTTP, la lógica de negocio y la persistencia.
- **Comunicación asíncrona por eventos**: los cambios de precio y de cupones se publican en RabbitMQ para que otros servicios reaccionen sin acoplarse a este.
- **Reserva de cupones con TTL**: el uso del cupón se confirma recién cuando llega el evento de orden creada. Las reservas abandonadas expiran solas.
- **Autenticación delegada**: el servicio no maneja usuarios. Valida el token contra AuthGo y controla permisos (`admin`) con una dependencia de FastAPI reutilizable.
- **Auditoría de precios**: cada movimiento queda registrado con su autor en una colección separada.
- **Stack 100% asíncrono**: FastAPI, Motor (MongoDB) y aio-pika (RabbitMQ).
