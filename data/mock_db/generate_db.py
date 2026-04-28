import json
import random

# ---------- INPUT ----------
order_ids = [
    1277,
    9098,
    4220,
    3129,
    4104,
    9221,
    9624,
    6900,
    2189,
    6509,
    3643,
    6076,
    3600,
    9926,
    6019,
    2360,
    9950,
    1650,
    4364,
    3226,
    9240,
    5845,
    1477,
    6372,
    6018,
    9744,
    5961,
    4403,
    9493,
    7286,
]

statuses = ["placed", "shipped", "delivered", "cancelled"]
users = [f"USR{i}" for i in range(1, 8)]

orders = []
payments = []
refunds = []
tickets = []
users_data = []

# ---------- USERS ----------
for i in range(1, 8):
    users_data.append(
        {
            "user_id": f"USR{i}",
            "name": f"User {i}",
            "wallet_balance": random.choice([0, 100, 500, 1000]),
        }
    )

# ---------- ORDERS + PAYMENTS ----------
for i, oid in enumerate(order_ids):
    status = statuses[i % 4]
    payment_type = "prepaid" if i % 2 == 0 else "cod"

    order = {
        "order_id": f"ORD{oid}",
        "user_id": users[i % len(users)],
        "status": status,
        "items": ["item"],
        "payment_type": payment_type,
        "amount": (i + 1) * 500,
    }
    orders.append(order)

    payments.append(
        {
            "payment_id": f"PAY{oid}",
            "order_id": order["order_id"],
            "method": payment_type,
            "status": ("completed" if payment_type == "prepaid" else "pending"),
        }
    )

    # ---------- REFUNDS (controlled subset) ----------
    if status in ["cancelled", "delivered"] and i % 3 == 0:
        refunds.append(
            {
                "refund_id": f"REF{oid}",
                "order_id": order["order_id"],
                "status": random.choice(["completed", "processing"]),
                "amount": order["amount"],
                "mode": "original_method" if payment_type == "prepaid" else "wallet",
            }
        )

    # ---------- TICKETS ----------
    if i % 4 == 0:
        tickets.append(
            {
                "ticket_id": f"TICK{oid}",
                "order_id": order["order_id"],
                "issue_type": random.choice(
                    ["delivery_delay", "damaged_product", "not_received"]
                ),
                "status": random.choice(["open", "in_progress", "resolved"]),
            }
        )

# ---------- WRITE FILES ----------
with open("orders.json", "w") as f:
    json.dump(orders, f, indent=2)

with open("payments.json", "w") as f:
    json.dump(payments, f, indent=2)

with open("refunds.json", "w") as f:
    json.dump(refunds, f, indent=2)

with open("tickets.json", "w") as f:
    json.dump(tickets, f, indent=2)

with open("users.json", "w") as f:
    json.dump(users_data, f, indent=2)

print("Mock DB generated.")
