import json
import random

OUTPUT_PATH = "app/eval/dataset.json"

single_intent_templates = [
    ("Where is my order {id}?", "track_order", ["status", "order"]),
    ("Cancel my order {id}", "cancel_order", ["cancel", "order"]),
    ("I want a refund for order {id}", "refund_order", ["refund", "order"]),
]

multi_intent_templates = [
    ("Cancel order {id} and refund it", "refund_order", ["cancel", "refund"]),
    ("Track order {id} and tell if I can cancel", "track_order", ["track", "cancel"]),
]

rag_templates = [
    ("What is your return policy?", "product_info", ["return", "policy"]),
    ("How long does shipping take?", "product_info", ["shipping", "time"]),
]

edge_templates = [
    ("asdfghjkl", "fallback", []),
    ("Cancel it", "fallback", ["cancel"]),
    ("Refund", "fallback", ["refund"]),
]


def generate_entries(templates, count, type_name, start_idx):
    data = []
    for i in range(count):
        tpl = random.choice(templates)
        q = tpl[0].format(id=random.randint(1000, 9999))
        data.append(
            {
                "id": f"q{start_idx + i}",
                "query": q,
                "type": type_name,
                "expected_tool": tpl[1],
                "expected_keywords": tpl[2],
            }
        )
    return data


dataset = []
idx = 1

dataset += generate_entries(single_intent_templates, 15, "single_intent", idx)
idx += 15

dataset += generate_entries(multi_intent_templates, 15, "multi_intent", idx)
idx += 15

dataset += generate_entries(rag_templates, 10, "rag", idx)
idx += 10

dataset += generate_entries(edge_templates, 10, "edge", idx)

with open(OUTPUT_PATH, "w") as f:
    json.dump(dataset, f, indent=2)

print(f"Dataset generated with {len(dataset)} entries at {OUTPUT_PATH}")
