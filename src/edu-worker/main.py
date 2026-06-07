from rich.console import Console

console = Console(force_terminal=True)


def main():
    console.print(
        "[bold green]Edu worker is configured for arq.[/bold green]\n"
        "Start it with: [bold]uv run arq worker.WorkerSettings[/bold]\n"
        "Run this command from the src/edu-worker directory."
    )


if __name__ == "__main__":
    main()
