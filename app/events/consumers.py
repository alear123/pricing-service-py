from app.services.coupon_service import coupon_service
import json

async def handle_order_created_event(message_payload: dict):
    print("Llegó un mensaje a handle_order_created_event")
    print(f" Payload recibido: {json.dumps(message_payload, indent=2, default=str)}")
    
    try:
        # Extraer 'message' si viene anidado en el formato de OrdersGo
        data = message_payload.get("message", message_payload)
        
        print(f"Payload extraído para procesar: {data}")
        await coupon_service.process_order_created_usage(data)
        
    except Exception as e:
        print(f"Falló el procesamiento del mensaje: {e}")