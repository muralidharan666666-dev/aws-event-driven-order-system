# AWS Event-Driven Order Processing System

I built this project to understand how AWS services can work together
without being directly connected to each other. Before this project,
I did not fully understand how large applications like Swiggy or Amazon
handle thousands of orders simultaneously without crashing. Building
this taught me exactly how that works.

---

## Why I Built This

I kept seeing "event-driven architecture" mentioned in AWS job descriptions
but I did not really understand what it meant in practice. I wanted to build
something real that would help me explain it confidently in interviews.

The idea is simple — when a customer places an order:
- They should get an instant response, not wait for the order to be processed
- If something goes wrong during processing, the order should not disappear
- The system should handle many orders at the same time without breaking

I used AWS serverless services to solve all three of these problems.

---

## What I Built

An order processing system where:

1. Customer sends an order via API
2. System instantly confirms the order
3. Order gets processed in the background
4. Customer receives an email when order is fulfilled
5. If processing fails, the order is safely stored and not lost

---

## Architecture

![AWS Event-Driven Order Processing System Architecture](architecture.png)

The diagram above shows the complete flow from the mobile app through
API Gateway, Lambda, SQS, SNS and the Dead-Letter Queue — with the
exact AWS service configurations I used in this project.

---

## AWS Services I Configured

### Amazon API Gateway
I created a REST API called `order-api` with a single POST /orders endpoint.
This is the URL the mobile app calls to place an order.
I deployed it to a stage called `dev`.

The main thing I learned here is that API Gateway does not run any code itself —
it just receives the request and passes it to Lambda.

### AWS Lambda — order-handler
Runtime: Python 3.12

This function receives the order from API Gateway, generates a unique Order ID
using UUID and sends the order as a message to the SQS queue.
It then immediately returns a confirmation to the customer.

I attached `AmazonSQSFullAccess` policy to this Lambda's execution role
so it has permission to write messages to the SQS queue.

One thing that confused me initially — I was wondering why SQS is not
configured as a trigger for this Lambda. Then I understood: this Lambda
SENDS messages to SQS, it does not RECEIVE from it. The trigger here
is API Gateway, not SQS.

### Amazon SQS — order-queue (Main Queue)
Type: Standard Queue
Visibility Timeout: 30 seconds
Maximum Receives before DLQ: 3

This queue sits between the two Lambda functions and holds order messages
safely until the fulfiller Lambda processes them.

I had to create the Dead-Letter Queue FIRST before creating this queue
because this queue needs to reference the DLQ during setup.
That order matters and I learned it the hard way.

### AWS Lambda — order-fulfiller
Runtime: Python 3.12
Trigger: Amazon SQS (order-queue)
Batch Size: 1

This function automatically runs whenever a new message arrives in the queue.
It processes the order and publishes a notification to SNS.

I attached both `AmazonSQSFullAccess` and `AmazonSNSFullAccess` to this
Lambda's execution role.

Unlike the first Lambda which is triggered by API Gateway, this one is
triggered directly by SQS. This is the core of what makes the system
event-driven — the function reacts automatically to events in the queue.

### Amazon SQS — order-dlq (Dead-Letter Queue)
Type: Standard Queue

This queue captures messages that failed processing after 3 retries.
I tested this by intentionally breaking the order-fulfiller Lambda and
confirming that after 3 retry attempts the message appeared in this queue
instead of disappearing.

This was actually one of the most interesting parts of the project because
it showed me concretely what happens to failed messages in a real system.

### Amazon SNS — order-notifications
Type: Standard Topic
Subscription: Email

Once an order is fulfilled, this Lambda publishes a notification here
and SNS automatically sends an email to the customer.

I subscribed my own email address and confirmed the subscription by
clicking the confirmation link AWS sent. I verified the subscription
status showed a proper Subscription ID on the SNS console.

---

## Real Test Results

I tested using the API Gateway built-in test tool with this request:

```json
{
    "item": "laptop",
    "quantity": 2
}
```

Response I received (under 1 second):
```json
{
    "message": "Order placed successfully",
    "orderId": "df204d3c-7f25-4085-9583-b6353b878774"
}
```

About 30 seconds later I received this email:

```
Subject: Order Fulfilled Successfully
Your order has been fulfilled!
Order ID: df204d3c-7f25-4085-9583-b6353b878774
Item: laptop
Quantity: 2
```

| Test | Result |
|---|---|
| API returns Status 200 | ✅ Passed — 937ms response time |
| Unique Order ID generated | ✅ Passed |
| SQS receives message | ✅ Passed |
| order-fulfiller triggered automatically | ✅ Passed |
| Email notification received | ✅ Passed |
| Failed message moves to DLQ after 3 retries | ✅ Passed |

---

## AWS Configuration Details

| Service | Setting | Value |
|---|---|---|
| SQS order-queue | Visibility Timeout | 30 seconds |
| SQS order-queue | Maximum Receives | 3 |
| SQS order-queue | Dead-Letter Queue | order-dlq |
| Lambda order-fulfiller | Batch Size | 1 |
| Lambda order-fulfiller | Trigger | SQS order-queue |
| API Gateway | Stage | dev |
| API Gateway | Method | POST /orders |
| SNS | Protocol | Email |

---

## Issues I Ran Into

### Issue 1 — Email notification was not arriving

Everything looked like it was working. API Gateway returned Status 200,
CloudWatch showed both Lambda functions ran successfully — but no email arrived.

I went back to the SNS Subscriptions page and noticed something strange.
The subscription showed:

```
Subscription ID : Deleted
Status          : Confirmed
```

The status said Confirmed but the ID said Deleted. This meant the subscription
existed at some point but was deleted. AWS was silently failing to deliver
emails because the endpoint no longer existed.

I created a fresh subscription, immediately confirmed it from my email
and verified the Subscription ID showed a proper ID — not Deleted.
After that the email arrived within 30 seconds.

What this taught me: A Confirmed status alone is not enough to trust.
Always check that the Subscription ID is a real ID. Silent failures in
notification systems are easy to miss because everything else appears
to be working fine.

### Issue 2 — AWS Console looked different from documentation

When creating the Lambda function I expected to see a radio button option
called "Create a new role with basic Lambda permissions" — which is what
most documentation shows.

Instead I saw a toggle called "Custom execution role" which opened a JSON
policy editor when turned on.

I figured out that keeping this toggle OFF does exactly the same thing as
the old radio button — AWS automatically creates a basic execution role.
I then manually attached the required policies to that role.

This taught me that AWS Console UI changes regularly. Understanding what
you are trying to achieve is more important than knowing where a specific
button is.

---

## What I Learned

**About event-driven architecture:**
Before this project I thought services had to directly call each other.
Now I understand why SQS sitting between two Lambda functions is better —
if the second Lambda is slow or temporarily unavailable, the first Lambda
does not fail or wait. The message just stays in the queue until the
second Lambda is ready.

**About Dead-Letter Queues:**
I used to think failed messages just disappear. Now I know DLQs exist
specifically to prevent that. The fact that you have to create the DLQ
before the main queue actually makes sense — the main queue needs to
know where to send failures before it can be configured.

**About SNS:**
I initially wanted to send emails directly from Lambda. Then I understood
why SNS is better — if I want to add SMS or push notifications later,
I just add a new subscriber to the topic. No code changes needed.

**About CloudWatch:**
When the email was not arriving, CloudWatch logs were the only way to
figure out what was actually happening inside the Lambda functions.
I can now see exactly which orders were processed and when.

**About IAM:**
Every Lambda needs specific permissions to talk to other AWS services.
I learned to always check what the function needs to DO and then attach
only the policies that allow those specific actions.

---

## Project Structure

```
aws-event-driven-project/
├── lambdas/
│   ├── order_handler.py       # Lambda 1 — receives order, sends to SQS
│   └── order_fulfiller.py     # Lambda 2 — processes order, notifies via SNS
├── architecture.png           # Architecture diagram with AWS icons
└── README.md                  # This file
```

---

## How to Deploy This

### Step 1 — Create Dead-Letter Queue first
```
Service   : Amazon SQS
Name      : order-dlq
Type      : Standard Queue
```

### Step 2 — Create Main Queue
```
Service           : Amazon SQS
Name              : order-queue
Type              : Standard Queue
Dead-Letter Queue : order-dlq
Maximum Receives  : 3
```

Note: Create the DLQ first. The main queue setup asks you to select
a DLQ during configuration — it must already exist.

### Step 3 — Create SNS Topic and confirm subscription
```
Service      : Amazon SNS
Name         : order-notifications
Type         : Standard
Subscription : Email
```

Important: After creating the subscription, immediately check your inbox
and click the confirmation link. Also verify the Subscription ID shows
a proper ID and not "Deleted" on the SNS console.

### Step 4 — Create order-handler Lambda
```
Service    : AWS Lambda
Name       : order-handler
Runtime    : Python 3.12
Code       : lambdas/order_handler.py
```
After creating: Go to Configuration → Permissions → click the role name
→ Attach AmazonSQSFullAccess policy

### Step 5 — Create order-fulfiller Lambda
```
Service    : AWS Lambda
Name       : order-fulfiller
Runtime    : Python 3.12
Code       : lambdas/order_fulfiller.py
```
After creating:
- Attach AmazonSQSFullAccess and AmazonSNSFullAccess to the role
- Add trigger: SQS → order-queue → Batch size 1

### Step 6 — Create API Gateway
```
Service   : Amazon API Gateway
Name      : order-api
Type      : REST API
Resource  : /orders
Method    : POST → Lambda → order-handler
Stage     : dev
```

---

## Monitoring

I checked Lambda execution using the Monitor tab on each function.
CloudWatch logs showed:

```
Processing order: df204d3c-7f25-4085-9583-b6353b878774
Item: laptop, Quantity: 2
Notification sent for order: df204d3c-7f25-4085-9583-b6353b878774
```

The Monitor tab also showed Invocations count and Error count which
helped me confirm when functions were being triggered and when they
were failing.

---

## References

- [AWS Event-Driven Architecture Workshop](https://catalog.workshops.aws/building-event-driven-architectures-on-aws/en-US)
- [Amazon SQS Documentation](https://docs.aws.amazon.com/sqs)
- [Amazon SNS Documentation](https://docs.aws.amazon.com/sns)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda)
- [Amazon API Gateway Documentation](https://docs.aws.amazon.com/apigateway)

---

## About Me

**Muralidharan M.N**
AWS re/Start Graduate | AWS Certified Cloud Practitioner |
Cloud Engineer in the Making

I completed the AWS re/Start program — AWS's official career
launch program for cloud — and earned the AWS Cloud Practitioner
certification. Since then I have spent 6 months building real
hands-on AWS projects including this event-driven order processing
system to go beyond what certifications teach.

I am actively looking for my first cloud role.
I am someone who questions everything — I want to understand
not just how to configure a service but why it was designed
that way. This project took me a full day of building and
debugging and I learned more from the errors than from
anything that worked first time.

AWS re/Start Graduate
AWS Certified Cloud Practitioner
Tirunelveli, Tamil Nadu — Open to Relocation & Remote
Actively looking for Cloud Engineer | DevOps Engineer | AWS Support Engineer roles

LinkedIn: https://www.linkedin.com/in/muralidharan-m-n-78a2522b8
GitHub: https://github.com/muralidharan666666-dev

---

If you found this project useful, feel free to star it!
