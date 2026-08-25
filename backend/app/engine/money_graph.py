import networkx as nx
from typing import Dict, Any, List, Optional
from app.engine.database import get_db_connection

class MoneyGraph:
    """
    In-memory financial relationship graph using NetworkX.
    Models interconnected entities:
      Customer -> Order -> Payment -> [Refund, Settlement, Dispute, WebhookEvent]
    Enables multi-hop traversal, blast-radius calculation, and cross-entity correlation.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def build_from_db(self):
        """Constructs the NetworkX graph from database records."""
        self.graph.clear()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Add Merchants
        cursor.execute("SELECT merchant_id, name, category FROM merchants")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["merchant_id"],
                type="Merchant",
                label=row["name"],
                category=row["category"],
                status="active"
            )

        # Add Customers
        cursor.execute("SELECT customer_id, name, email FROM customers")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["customer_id"],
                type="Customer",
                label=row["name"],
                email=row["email"],
                status="active"
            )

        # Add Orders
        cursor.execute("SELECT order_id, merchant_id, customer_id, amount, status FROM orders")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["order_id"],
                type="Order",
                label=f"Order {row['order_id'][-6:]}",
                amount=row["amount"],
                status=row["status"]
            )
            # Edges: Customer -> Order, Merchant -> Order
            self.graph.add_edge(row["customer_id"], row["order_id"], relation="PLACED")
            self.graph.add_edge(row["merchant_id"], row["order_id"], relation="FULFILLS")

        # Add Payments
        cursor.execute("SELECT payment_id, order_id, merchant_id, customer_id, amount, status, gateway, failure_code, retry_count FROM payments")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["payment_id"],
                type="Payment",
                label=f"Pay {row['payment_id'][-6:]}",
                amount=row["amount"],
                status=row["status"],
                gateway=row["gateway"],
                failure_code=row["failure_code"],
                retry_count=row["retry_count"]
            )
            # Edge: Order -> Payment
            self.graph.add_edge(row["order_id"], row["payment_id"], relation="PAID_WITH")
            # Edge: Payment -> Gateway
            if not self.graph.has_node(row["gateway"]):
                self.graph.add_node(row["gateway"], type="Gateway", label=row["gateway"], status="active")
            self.graph.add_edge(row["payment_id"], row["gateway"], relation="ROUTED_TO")

        # Add Refunds
        cursor.execute("SELECT refund_id, payment_id, merchant_id, amount, status, failure_reason FROM refunds")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["refund_id"],
                type="Refund",
                label=f"Ref {row['refund_id'][-6:]}",
                amount=row["amount"],
                status=row["status"],
                failure_reason=row["failure_reason"]
            )
            # Edge: Payment -> Refund
            self.graph.add_edge(row["payment_id"], row["refund_id"], relation="REFUNDED_BY")

        # Add Settlements
        cursor.execute("SELECT settlement_id, merchant_id, payment_id, amount, status, utr, delay_hours FROM settlements")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["settlement_id"],
                type="Settlement",
                label=f"Set {row['settlement_id'][-6:]}",
                amount=row["amount"],
                status=row["status"],
                utr=row["utr"],
                delay_hours=row["delay_hours"]
            )
            # Edge: Payment -> Settlement
            self.graph.add_edge(row["payment_id"], row["settlement_id"], relation="SETTLED_IN")

        # Add Disputes
        cursor.execute("SELECT dispute_id, payment_id, amount, reason, status FROM disputes")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["dispute_id"],
                type="Dispute",
                label=f"Disp {row['dispute_id'][-6:]}",
                amount=row["amount"],
                reason=row["reason"],
                status=row["status"]
            )
            # Edge: Payment -> Dispute
            self.graph.add_edge(row["payment_id"], row["dispute_id"], relation="DISPUTED_IN")

        # Add Webhooks
        cursor.execute("SELECT event_id, event_type, entity_id, delivery_status, http_status, response_time_ms FROM webhook_events")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["event_id"],
                type="WebhookEvent",
                label=row["event_type"],
                status=row["delivery_status"],
                http_status=row["http_status"],
                response_time_ms=row["response_time_ms"]
            )
            # Edge: Entity -> Webhook
            if self.graph.has_node(row["entity_id"]):
                self.graph.add_edge(row["entity_id"], row["event_id"], relation="TRIGGERED_WEBHOOK")

        conn.close()

    def add_payment_event(self, payment_id: str, order_id: str, merchant_id: str, customer_id: str, amount: float, status: str, gateway: str, failure_code: Optional[str] = None, retry_count: int = 0):
        """Incrementally adds a payment entity and relations to the graph."""
        if not self.graph.has_node(merchant_id):
            self.graph.add_node(merchant_id, type="Merchant", label=merchant_id, status="active")
        if not self.graph.has_node(customer_id):
            self.graph.add_node(customer_id, type="Customer", label=customer_id, status="active")
        if not self.graph.has_node(order_id):
            self.graph.add_node(order_id, type="Order", label=f"Order {order_id[-6:]}", amount=amount, status="paid")
            self.graph.add_edge(customer_id, order_id, relation="PLACED")
            self.graph.add_edge(merchant_id, order_id, relation="FULFILLS")

        self.graph.add_node(
            payment_id,
            type="Payment",
            label=f"Pay {payment_id[-6:]}",
            amount=amount,
            status=status,
            gateway=gateway,
            failure_code=failure_code,
            retry_count=retry_count
        )
        self.graph.add_edge(order_id, payment_id, relation="PAID_WITH")
        if not self.graph.has_node(gateway):
            self.graph.add_node(gateway, type="Gateway", label=gateway, status="active")
        self.graph.add_edge(payment_id, gateway, relation="ROUTED_TO")

    def add_refund_event(self, refund_id: str, payment_id: str, merchant_id: str, amount: float, status: str, failure_reason: Optional[str] = None):
        """Incrementally adds a refund entity and relations to the graph."""
        self.graph.add_node(
            refund_id,
            type="Refund",
            label=f"Ref {refund_id[-6:]}",
            amount=amount,
            status=status,
            failure_reason=failure_reason
        )
        if self.graph.has_node(payment_id):
            self.graph.add_edge(payment_id, refund_id, relation="REFUNDED_BY")

    def add_webhook_event(self, event_id: str, entity_id: str, event_type: str, status: str = "delivered"):
        """Incrementally adds a webhook event and relations to the graph."""
        self.graph.add_node(
            event_id,
            type="WebhookEvent",
            label=event_type,
            status=status
        )
        if self.graph.has_node(entity_id):
            self.graph.add_edge(entity_id, event_id, relation="TRIGGERED_WEBHOOK")

    def get_payment_cluster(self, payment_id: str) -> Dict[str, Any]:
        """Traverse connected entities around a single payment."""
        if not self.graph.has_node(payment_id):
            return {"error": f"Payment {payment_id} not found in Money Graph"}

        predecessors = list(self.graph.predecessors(payment_id))
        successors = list(self.graph.successors(payment_id))

        refunds = []
        settlements = []
        disputes = []
        webhooks = []
        gateway = None

        for succ in successors:
            node_data = self.graph.nodes[succ]
            n_type = node_data.get("type")
            if n_type == "Refund":
                refunds.append({"id": succ, **node_data})
                # Check webhooks attached to refund
                for r_succ in self.graph.successors(succ):
                    if self.graph.nodes[r_succ].get("type") == "WebhookEvent":
                        webhooks.append({"id": r_succ, "target": succ, **self.graph.nodes[r_succ]})
            elif n_type == "Settlement":
                settlements.append({"id": succ, **node_data})
            elif n_type == "Dispute":
                disputes.append({"id": succ, **node_data})
            elif n_type == "Gateway":
                gateway = {"id": succ, **node_data}
            elif n_type == "WebhookEvent":
                webhooks.append({"id": succ, "target": payment_id, **node_data})

        order_id = None
        customer_id = None
        merchant_id = None
        for pred in predecessors:
            node_data = self.graph.nodes[pred]
            if node_data.get("type") == "Order":
                order_id = pred
                # From Order, trace Customer & Merchant
                for order_pred in self.graph.predecessors(order_id):
                    op_data = self.graph.nodes[order_pred]
                    if op_data.get("type") == "Customer":
                        customer_id = order_pred
                    elif op_data.get("type") == "Merchant":
                        merchant_id = order_pred

        payment_data = self.graph.nodes[payment_id]

        return {
            "payment": {"id": payment_id, **payment_data},
            "order_id": order_id,
            "customer_id": customer_id,
            "merchant_id": merchant_id,
            "gateway": gateway,
            "refunds": refunds,
            "settlements": settlements,
            "disputes": disputes,
            "webhooks": webhooks,
            "is_duplicate_refund": len(refunds) > 1,
            "has_failed_webhooks": any(w.get("status") in ["failed", "timed_out"] for w in webhooks)
        }

    def get_gateway_blast_radius(self, gateway_name: str, error_code: Optional[str] = None) -> Dict[str, Any]:
        """Calculates cross-merchant blast radius for a gateway incident."""
        affected_payments = []
        affected_merchants = set()
        affected_refunds = []
        total_delayed_amount = 0.0

        for u, v, data in self.graph.edges(data=True):
            if v == gateway_name and data.get("relation") == "ROUTED_TO":
                p_data = self.graph.nodes[u]
                if error_code is None or p_data.get("failure_code") == error_code or p_data.get("status") == "failed":
                    affected_payments.append(u)
                    # Find refunds attached to payment
                    for succ in self.graph.successors(u):
                        if self.graph.nodes[succ].get("type") == "Refund":
                            r_data = self.graph.nodes[succ]
                            affected_refunds.append(succ)
                            total_delayed_amount += r_data.get("amount", 0.0)

        # Trace merchants
        for p in affected_payments:
            for pred in self.graph.predecessors(p):
                if self.graph.nodes[pred].get("type") == "Order":
                    for m_pred in self.graph.predecessors(pred):
                        if self.graph.nodes[m_pred].get("type") == "Merchant":
                            affected_merchants.add(m_pred)

        return {
            "gateway": gateway_name,
            "error_code": error_code,
            "affected_payments_count": len(affected_payments),
            "affected_refunds_count": len(affected_refunds),
            "affected_merchants_count": len(affected_merchants),
            "affected_merchants_list": list(affected_merchants)[:10],
            "total_delayed_exposure": round(total_delayed_amount, 2)
        }

    def export_subgraph_for_vis(self, target_id: str, depth: int = 2) -> Dict[str, Any]:
        """Exports a formatted node/edge JSON subgraph for interactive UI visualization."""
        if not self.graph.has_node(target_id):
            return {"nodes": [], "edges": []}

        # Subgraph extraction via undirected neighborhood
        undirected = self.graph.to_undirected()
        sub_nodes = {target_id}
        current_layer = {target_id}

        for _ in range(depth):
            next_layer = set()
            for n in current_layer:
                neighbors = set(undirected.neighbors(n))
                next_layer.update(neighbors)
            sub_nodes.update(next_layer)
            current_layer = next_layer
            if len(sub_nodes) > 40:  # limit for clean UI visualization
                break

        nodes_list = []
        for n in sub_nodes:
            nd = self.graph.nodes[n]
            nodes_list.append({
                "id": n,
                "type": nd.get("type", "Entity"),
                "label": nd.get("label", n),
                "status": nd.get("status", "normal"),
                "amount": nd.get("amount", None),
                "is_target": (n == target_id)
            })

        edges_list = []
        for u, v, ed in self.graph.edges(sub_nodes, data=True):
            if u in sub_nodes and v in sub_nodes:
                edges_list.append({
                    "source": u,
                    "target": v,
                    "relation": ed.get("relation", "CONNECTED_TO")
                })

        return {"nodes": nodes_list, "edges": edges_list}

money_graph = MoneyGraph()
