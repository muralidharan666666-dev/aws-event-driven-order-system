# order-fulfiller
# Triggered by the SQS order-queue (batch size 1).
# Reads each order message, logs it to CloudWatch, and publishes
# a notification to the SNS order-notifications topic.
# If this function fails, SQS tries again; after 3 failed attempts
# the message moves to the order-dlq. The topic ARN comes from the
# SNS_TOPIC_ARN environment variable.

import json
import os
import boto3

sns = boto3.client('sns')

SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

def lambda_handler(event, context):

    for record in event['Records']:

        body = json.loads(record['body'])

        order_id = body['orderId']
        item = body['item']
        quantity = body['quantity']

        print(f"Processing order: {order_id}")
        print(f"Item: {item}, Quantity: {quantity}")

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=f"Your order has been fulfilled! Order ID: {order_id}, Item: {item}, Quantity: {quantity}",
            Subject="Order Fulfilled Successfully"
        )

        print(f"Notification sent for order: {order_id}")

    return {
        'statusCode': 200,
        'body': json.dumps('Order fulfilled successfully')
    }