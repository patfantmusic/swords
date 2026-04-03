"""A lightweight script to search Genius for song lyrics."""

from dataclasses import dataclass, fields
import re
from typing import Any
from urllib.parse import quote_plus

import click
from selectolax.lexbor import LexborHTMLParser
import requests


@dataclass
class Song:
    """Represents song data from Genius."""

    primary_artist_names: str
    title: str
    url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Song":
        class_fields = {field.name for field in fields(cls)}
        filtered_data = {
            key: value for key, value in data.items() if key in class_fields
        }
        return cls(**filtered_data)


def get_song_choices(query: str) -> list[Song]:
    """Query Genius for songs that match the given search."""
    response = requests.get(
        "https://genius.com/api/search/multi",
        params={"per_page": 5, "q": quote_plus(query)},
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for section in data["response"]["sections"]:
        if section["type"] == "song":
            for hit in section["hits"]:
                song = Song.from_dict(hit["result"])
                results.append(song)
    return results


def get_lyrics(song: Song) -> str:
    """Given a song, get Genius's corresponding lyrics using selectolax (Lexbor)."""
    response = requests.get(song.url)
    response.raise_for_status()

    parser = LexborHTMLParser(response.text)
    lyrics_list = []

    # Find all lyric container divs
    for section in parser.css('div[class^="Lyrics__Container"]'):
        # Manually find and decompose the header containers
        for header in section.css('div[class^="LyricsHeader__Container"]'):
            header.decompose()

        # Get text with a newline separator
        # strip=True removes leading/trailing whitespace from the resulting string
        text = section.text(separator="\n", strip=True)
        if text:
            lyrics_list.append(text)

    return "\n".join(lyrics_list)


@click.command
@click.argument("query")
def search(query: str) -> None:
    """
    Takes a search query, finds up to 5 matches, and displays lyrics for a
    chosen match.
    """
    click.echo("Searching...")
    click.echo("")

    song_choices = get_song_choices(query)
    click.echo("Choices:")
    for i, song in enumerate(song_choices):
        click.echo(f"{i}. {song.title} - {song.primary_artist_names}")
    click.echo("")

    choice_id = click.prompt(
        "Select an option",
        type=click.IntRange(0, len(song_choices) - 1),
    )
    choice = song_choices[choice_id]
    lyrics = get_lyrics(choice)

    # Assume anything in brackets is a section header and format accordingly.
    formatted_lyrics = re.sub(
        r"(\[.*?\])",
        lambda m: "\n" + click.style(m.group(0), bold=True),
        lyrics,
    )

    click.echo("=" * 80)
    click.echo("")
    click.echo(f"{formatted_lyrics.strip()}")
    click.echo("")


if __name__ == "__main__":
    search()
