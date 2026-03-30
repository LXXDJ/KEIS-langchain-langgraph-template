from agents import build_graph


def main() -> None:
    graph = build_graph()
    print("graph ready:", type(graph).__name__)


if __name__ == "__main__":
    main()
