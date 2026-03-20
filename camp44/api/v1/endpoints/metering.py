import pika
from fastapi import APIRouter, Depends, Response, status

from camp44.api.deps import get_current_active_user
from camp44.core.config import settings
from camp44.models.metering import MeterEvent
from camp44.models.user import User

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_meter_event(
    event: MeterEvent,
    response: Response,
    current_user: User = Depends(get_current_active_user),
):
    """
    Emit a new metering event to the queue.
    """
    # Override tenant_id with authenticated user's value — never trust client
    event.tenant_id = current_user.tenant_id or "default"

    connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
    channel = connection.channel()

    exchange_name = "metering_exchange"
    queue_name = "metering_queue"
    routing_key = "metering.event"

    # Declare a durable exchange
    channel.exchange_declare(
        exchange=exchange_name, exchange_type="direct", durable=True
    )

    # Declare a durable queue
    channel.queue_declare(queue=queue_name, durable=True)

    # Bind the queue to the exchange
    channel.queue_bind(
        queue=queue_name, exchange=exchange_name, routing_key=routing_key
    )

    event_json = event.model_dump_json()

    channel.basic_publish(
        exchange=exchange_name,
        routing_key=routing_key,
        body=event_json,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ),
    )

    connection.close()

    return {"status": "accepted"}
