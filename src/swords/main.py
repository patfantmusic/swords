import sys
import requests
import click
import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Initialize Rich console for terminal formatting
console = Console()

# LRCLIB requires a User-Agent to identify the client interacting with their API
HEADERS = {"User-Agent": "swords CLI v2.0 (https://github.com/yourusername/swords)"}


def search_lrclib(query: str, artist: str = None) -> list:
    """Searches LRCLIB for a song and returns a list of results."""
    url = "https://lrclib.net/api/search"

    # Construct parameters based on what the user provided
    params = {}
    if artist:
        params["track_name"] = query
        params["artist_name"] = artist
    else:
        params["q"] = query

    # Display a loading spinner while fetching the API
    with console.status(
        "[bold green]Searching for lyrics...[/bold green]", spinner="dots"
    ):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error communicating with LRCLIB:[/bold red] {e}")
            sys.exit(1)


def display_lyrics(song_data: dict):
    """Formats and prints the lyrics using Rich."""
    title = song_data.get("trackName", "Unknown Title")
    artist = song_data.get("artistName", "Unknown Artist")
    album = song_data.get("albumName", "Unknown Album")

    # Prefer plainLyrics, fallback to syncedLyrics, then handle missing lyrics
    lyrics = song_data.get("plainLyrics")
    if not lyrics:
        lyrics = song_data.get("syncedLyrics")
        if lyrics:
            console.print(
                "[yellow]Note: Displaying synced lyrics (contains timestamps).[/yellow]"
            )

    if not lyrics:
        if song_data.get("instrumental"):
            lyrics = "*This track is marked as instrumental (no lyrics).*"
        else:
            lyrics = "*No lyrics found for this track.*"

    # Create a nicely formatted header text for the song metadata
    header = Text()
    header.append(f"{title}\n", style="bold cyan")
    header.append(f"by {artist}\n", style="bold magenta")
    if album:
        header.append(f"Album: {album}", style="italic dim")

    # Render the output inside a styled Panel
    panel = Panel(
        lyrics, title=header, title_align="center", border_style="green", expand=False
    )

    # Use Rich's pager so long lyrics don't scroll off the screen
    with console.pager():
        console.print(panel)


@click.command()
@click.argument("query", required=False)
@click.option("-a", "--artist", help="Filter search by artist name.")
def main(query, artist):
    """
    SWORDS: Song WORD Search.

    Search for song lyrics right in your terminal.
    If no QUERY is provided, you will be prompted.
    """

    # 1. Handle missing arguments with an interactive text prompt
    if not query:
        questions = [inquirer.Text("query", message="Enter a song name to search for")]
        answers = inquirer.prompt(questions)

        # If user cancels the prompt (Ctrl+C)
        if not answers or not answers.get("query"):
            console.print("[yellow]Search cancelled.[/yellow]")
            sys.exit(0)

        query = answers["query"]

    # 2. Fetch results from LRCLIB
    results = search_lrclib(query, artist)

    if not results:
        console.print(f"[bold red]No lyrics found for '{query}'.[/bold red]")
        sys.exit(0)

    # Limit results to the top 15 to prevent the terminal from scrolling down
    # and losing the top of the menu in small panes (like tmux).
    results = results[:15]

    # 3. If there's only one result, bypass the menu and show it
    if len(results) == 1:
        display_lyrics(results[0])
        sys.exit(0)

    # 4. If multiple results, use python-inquirer for an interactive selection menu
    # Find max widths for columns to create a neat table, capping lengths
    max_t = min(40, max(len(str(item.get("trackName", "Unknown"))) for item in results))
    max_a = min(
        30, max(len(str(item.get("artistName", "Unknown"))) for item in results)
    )
    max_al = min(30, max(len(str(item.get("albumName", "") or "")) for item in results))

    def format_col(text, max_len):
        """Truncate text if too long, or pad it with spaces if short."""
        text = str(text or "")
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text.ljust(max_len)

    choices = []

    # Enumerate to get rankings (1 is best), then reverse to put the best at the bottom
    ranked_results = list(enumerate(results, start=1))
    ranked_results.reverse()

    for rank, item in ranked_results:
        t = format_col(item.get("trackName", "Unknown"), max_t)
        a = format_col(item.get("artistName", "Unknown"), max_a)
        al = format_col(item.get("albumName", ""), max_al)

        # Combine into a table-like row separated by pipes, with the rank on the left
        # We use >2 to pad single-digit numbers so 1 and 15 line up perfectly
        display_text = f"{rank:>2}. {t} │ {a} │ {al}"
        choices.append((display_text, item))

    choices.append(("Cancel", None))

    # Show the interactive arrow-key menu
    questions = [
        inquirer.List(
            "selected_song",
            message="Select a song (1 is best match)",
            choices=choices,
            default=results[0],  # Automatically place the cursor on the best match
            carousel=True,  # Allow wrapping from bottom to top
        )
    ]

    answers = inquirer.prompt(questions)

    # If the user hits Ctrl+C or selects "Cancel", prompt returns None
    if not answers or answers.get("selected_song") is None:
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    selected_song = answers["selected_song"]

    # 5. Display the selected lyrics
    display_lyrics(selected_song)


if __name__ == "__main__":
    # Ensure dependencies are noted for the user before running
    try:
        import inquirer
    except ImportError:
        print("Please install requirements: pip install click rich inquirer requests")
        sys.exit(1)

    main()
