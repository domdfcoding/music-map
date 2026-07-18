#!/usr/bin/env python3
#
#  mp3.py
"""
Read artists from MP3 files etc.
"""
#
#  Copyright © 2026 Dominic Davis-Foster <dominic@davis-foster.co.uk>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#  DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
#  OR OTHER DEALINGS IN THE SOFTWARE.
#

# stdlib
import re
from collections.abc import Iterator

# 3rd party
from domdf_python_tools.paths import PathPlus, unwanted_dirs
from mutagen.id3 import ID3, TPE2

__all__ = ["iter_artists"]


def iter_artists(path: PathPlus) -> Iterator[str]:
	"""
	Returns the names of artists in the music collection.

	:param path: Directory containing MP3 files.
	"""

	artists = set()

	for file in path.iterchildren(
			match="**/*.mp*",
			exclude_dirs={*unwanted_dirs, ".stversions", "Various artists"},
			):
		tags = ID3(file)
		if "TPE1" not in tags:
			continue

		artist: str = tags["TPE1"].text[0].strip()
		artist = re.split("( duet | with | feat| ft)", artist, flags=re.IGNORECASE)[0].strip()

		if artist in artists:
			continue

		multiple_act_hints = ['/', ", ", " and ", " & ", " vs ", " vs. "]
		artist_lowercase = artist.lower()
		if any(h in artist_lowercase for h in multiple_act_hints):
			continue

		if "TPE2" in tags:
			album_artist: TPE2 = tags["TPE2"]
			if album_artist.text[0].lower() in {"various", "various artists"}:  # type: ignore[attr-defined]
				continue

		artists.add(artist)
		yield artist
