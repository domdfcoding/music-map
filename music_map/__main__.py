#!/usr/bin/env python3
#
#  __main__.py
"""
Generate a map showing where artists in your music collection come from.
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

# 3rd party
import click
from consolekit import CONTEXT_SETTINGS, SuggestionGroup, click_group
from consolekit.options import auto_default_option
from domdf_python_tools.typing import PathLike

__all__ = ["main", "make_map", "prepare_data"]


@click_group(
		cls=SuggestionGroup,
		invoke_without_command=False,
		context_settings={**CONTEXT_SETTINGS, "show_default": True},
		)
def main() -> None:
	"""
	Map showing listed buildings in England and Wales.
	"""


@click.option("--token", "-t", "access_token", help="Wikidata API OAuth access token", envvar="WIKIDATA_TOKEN")
@click.argument("music_directory")
@main.command()
def prepare_data(music_directory: PathLike, access_token: str) -> None:
	"""
	Prepare data for the map.
	"""

	# stdlib
	import atexit
	import time

	# 3rd party
	import requests
	from cachecontrol import CacheControl
	from cachecontrol.caches import SeparateBodyFileCache
	from domdf_python_tools.paths import PathPlus

	# this package
	from music_map.mp3 import iter_artists
	from music_map.wikidata import WikidataAPI

	headers = {
			"Content-Type": "application/json",
			"Authorization": f'Bearer {access_token}',
			}

	sess = CacheControl(requests.Session(), cache=SeparateBodyFileCache("wikidata_cache"))
	sess.headers.update(headers)

	origins_datafile = PathPlus("origins_v2.json")
	if origins_datafile.exists():
		origins = origins_datafile.load_json()
	else:
		origins = {}

	def save_origins() -> None:
		origins_datafile.dump_json(origins, indent=2)

	atexit.register(save_origins)

	wd_api = WikidataAPI(session=sess)

	def lookup_origin(artist: str) -> dict | None:
		for language in ('', "@en"):
			for code in [
					("P31", "Q2088357"),  # Musical ensemble
					("P106/ps:P106", "Q135106813"),  # musical occupation
					]:
				data = wd_api.get_artist_data(artist, *code, language)
				time.sleep(1)
				if data is not None:
					return data

		return None

	with open("problems.txt", 'w', encoding="UTF-8") as fp:

		for artist in iter_artists(PathPlus(music_directory)):
			if artist in {"James Morrison", "Alan Walker", "Oscar"}:
				# TODO: need special handling
				continue

			if artist not in origins:
				print(artist)
				origin = lookup_origin(artist)
				print(origin)
				if origin:
					origins[artist] = origin
				else:
					fp.write(artist + '\n')
					fp.flush()


@auto_default_option("-O", "--output-dir", "output_directory")
@main.command()
def make_map(output_directory: str = "output") -> None:
	"""
	Create the map and write associated files.
	"""

	# TODO: data dir?

	# 3rd party
	from domdf_folium_tools import set_branca_random_seed
	from domdf_python_tools.paths import PathPlus

	# this package
	from music_map.map import make_map

	set_branca_random_seed("music")

	output_dir = PathPlus(output_directory)
	output_dir.maybe_make()

	origins: dict = PathPlus("origins_v2.json").load_json()

	m = make_map(origins)
	html = m.get_root().render()

	output_dir.joinpath("index.html").write_clean(html)


if __name__ == "__main__":
	main()
