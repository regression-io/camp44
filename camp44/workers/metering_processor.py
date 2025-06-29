import json
import time

import pika
import stripe

from camp44.core.config import settings

# Initialize stripe if the key is provided, but don't require it
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def process_event(event_data: dict):
    """Process a single metering event."""
    print(f"Processing event: {event_data}")
    # In a real scenario, you would do more here:
    # 1. Check if stripe.api_key is set.
    # 2. Look up the tenant's Stripe Customer ID and the App's Stripe Price ID from your database.
    # 3. Report usage to Stripe against the correct subscription item.
    #    stripe.SubscriptionItem.create_usage_record(...)
    time.sleep(0.1)  # Simulate work


def main():
    """Main worker loop to process events from RabbitMQ."""
    connection_params = pika.URLParameters(settings.RABBITMQ_URL)
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()

    exchange_name = 'metering_exchange'
    queue_name = 'metering_queue'
    routing_key = 'metering.event'

    # Ensure the exchange and queue exist and are durable
    channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=routing_key)

    def callback(ch, method, properties, body):
        print(f"Received message {method.delivery_tag}")
        try:
            event = json.loads(body.decode())
            process_event(event)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"Acknowledged message {method.delivery_tag}")
        except Exception as e:
            print(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)  # Process one message at a time
    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    print('Waiting for messages. To exit press CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Interrupted")
        connection.close()


if __name__ == "__main__":
    print("Starting metering processor...")
    while True:
        try:
            main()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Shutting down.")
            break
