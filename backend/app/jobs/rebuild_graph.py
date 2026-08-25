from app.engine.money_graph import money_graph

def rebuild_graph():
    print("Rebuilding Money Graph from SQLite database...")
    money_graph.build_from_db()
    n_nodes = money_graph.graph.number_of_nodes()
    n_edges = money_graph.graph.number_of_edges()
    print("Money Graph Rebuild Complete:")
    print(f"  - Total Nodes: {n_nodes}")
    print(f"  - Total Edges: {n_edges}")

if __name__ == "__main__":
    rebuild_graph()
