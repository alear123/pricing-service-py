# app/rabbitmq.py
import json
import aio_pika
from datetime import datetime
from app.config import settings

class RabbitMQManager:
    connection: aio_pika.RobustConnection = None
    channel: aio_pika.RobustChannel = None
    exchange: aio_pika.RobustExchange = None

rabbitmq = RabbitMQManager()

async def connect_to_rabbitmq():
    try:
        rabbitmq.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        rabbitmq.channel = await rabbitmq.connection.channel()
        
        # 'amq.direct' en RabbitMQ es por defecto durable=True
        rabbitmq.exchange = await rabbitmq.channel.declare_exchange(
            name=settings.RABBITMQ_EXCHANGE,
            type=aio_pika.ExchangeType.DIRECT,
            durable=True  
        )
        print("Conectado exitosamente a RabbitMQ")
    except Exception as e:
        print(f"Error al conectar con RabbitMQ: {e}")

async def close_rabbitmq_connection():
    if rabbitmq.connection:
        await rabbitmq.connection.close()
        print("Conexión a RabbitMQ cerrada")

async def publish_event(routing_key: str, message_data: dict):
    """
    Publica un evento asíncrono en RabbitMQ en formato JSON.
    """
    if not rabbitmq.exchange:
        print(f"Advertencia: No se pudo emitir el evento {routing_key}. RabbitMQ no está conectado.")
        return

    # Helper para serializar datetimes a string ISO
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    payload = json.dumps(message_data, default=json_serializer).encode("utf-8")

    message = aio_pika.Message(
        body=payload,
        content_type="application/json"
    )

    await rabbitmq.exchange.publish(
        message,
        routing_key=routing_key
    )
    print(f"Evento emitido -> Routing Key: '{routing_key}'")

async def start_order_consumer():
    """
    Crea la cola en RabbitMQ, la vincula al exchange 'order_placed' (FANOUT, durable=False)
    y empieza a escuchar eventos de órdenes.
    """
    from app.events.consumers import handle_order_created_event

    if not rabbitmq.channel:
        print("No se puede iniciar el consumidor: RabbitMQ no está inicializado.")
        return

    try:
        # 1. Declarar el Exchange 'order_placed' como en rabbitmq
        orders_exchange = await rabbitmq.channel.declare_exchange(
            name="order_placed",
            type=aio_pika.ExchangeType.FANOUT,
            durable=False
        )

        queue_name = "pricing_place_order_queue"
        
        # 2. Declarar la cola de Pricing
        queue = await rabbitmq.channel.declare_queue(queue_name, durable=True)

        # 3. Vincular la cola al Exchange FANOUT
        await queue.bind(orders_exchange, routing_key="")

        # 4. Callback para procesar el mensaje
        async def on_message_received(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    body_str = message.body.decode("utf-8")
                    payload = json.loads(body_str)
                    await handle_order_created_event(payload)
                except Exception as e:
                    print(f" Error al procesar mensaje entrante de RabbitMQ: {e}")

        # 5. Iniciar el consumo
        await queue.consume(on_message_received)
        print(f"Escuchando en Exchange FANOUT 'order_placed' -> Cola '{queue_name}'")

    except Exception as e:
        print(f"Error al configurar el consumidor de RabbitMQ: {e}")