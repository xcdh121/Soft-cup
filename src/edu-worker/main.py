from config import get_settings
from edu_db.session import init_db
from rich.console import Console

console = Console(force_terminal=True)


def main():
    settings = get_settings()

    # Initialize database connection
    init_db(settings.database_url)
    console.print(
        "[bold yellow]Local-first mode is enabled.[/bold yellow] "
        "Background queue workers are no longer required because tasks run synchronously in the API process."
    )


if __name__ == "__main__":
    main()
