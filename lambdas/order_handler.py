# order-handler
# Triggered by API Gateway (POST /orders).
# Reads the order from the request, creates a unique order ID,
# sends the order to the SQS order-queue, and returns a confirmation
# to the caller right away. The queue URL comes from the
# QUEUE_URL environment variable.

import json
import os
import boto3
import uuid

sqs = boto3.client('sqs')

QUEUE_URL = os.environ['QUEUE_URL']

def lambda_handler(event, context):

    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    elif isinstance(event.get('body'), dict):
        body = event['body']
    else:
        body = event

    order_id = str(uuid.uuid4())

    message = {
        'orderId': order_id,
        'item': body.get('item'),
        'quantity': body.get('quantity')
    }

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Order placed successfully',
            'orderId': order_id
        })
    }