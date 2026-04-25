"""
Render the compiled LangGraph as ASCII (and optionally as a Mermaid diagram)
so reviewers can confirm the architecture matches the README diagram.

Usage:
    python -m scripts.print_graph
"""
from dotenv import load_dotenv
load_dotenv()

from graph.builder import build_graph


def main():
    graph = build_graph()
    print("=== Nodes ===")
    for n in graph.get_graph().nodes.keys():
        print(f"  {n}")
    print("\n=== ASCII diagram ===")
    try:
        print(graph.get_graph().draw_ascii())
    except Exception as e:
        print(f"(draw_ascii failed: {e})")
    print("\n=== Mermaid ===")
    try:
        print(graph.get_graph().draw_mermaid())
    except Exception as e:
        print(f"(draw_mermaid failed: {e})")


if __name__ == "__main__":
    main()
