#!/usr/bin/env python3
#
#  wikidata.py
"""
Functions for extracting data from Wikidata.
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
import posixpath
import sys
from operator import itemgetter
from typing import Any
from urllib.parse import urlparse

# 3rd party
import requests
from cachecontrol import CacheControl
from cachecontrol.caches import SeparateBodyFileCache
from requests import Session

# this package
from music_map import __version__

__all__ = ["WikidataAPI", "create_session", "get_english_label", "get_origin_id", "get_start_year"]


def get_start_year(wikidata_data: dict) -> int:
	"""
	Find the artist's start year or year of formation.

	:param wikidata_data: JSON data from Wikidata for an entity.
	"""

	# TODO: DOB
	for code in ["P2031", "P571"]:  # P2031: start of work period, P571: date of inception
		if code in wikidata_data["statements"]:
			value = wikidata_data["statements"][code][0]["value"]
			if value["type"] != "novalue":
				return int(value["content"]["time"].lstrip('+').split('-', 1)[0])

	return sys.maxsize


def get_origin_id(wikidata_data: dict) -> str | None:
	"""
	Returns the Wikidata entity ID for the artist's origin (location of formation or place of birth), if available.

	:param wikidata_data: JSON data from Wikidata for an entity.
	"""

	for code in ["P740", "P19", "P27", "P495"]:
		# P740: location of formation, P19: place of birth, P27: citizenship, P495: country of origin
		if code in wikidata_data["statements"]:
			value = wikidata_data["statements"][code][0]["value"]
			if value["type"] != "novalue":
				return value["content"]

	return None


def get_english_label(wikidata_data: dict) -> str:
	"""
	Returns the English-language label for the given entity.

	:param wikidata_data: JSON data from Wikidata for an entity.
	"""

	labels: dict[str, str] = wikidata_data["labels"]
	return labels.get("en", labels.get("mul", ''))


class WikidataAPI:
	"""
	Interface to Wikidata's APIs.

	:param session:
	"""

	def __init__(self, session: Session):
		self.session = session
		user_agent = f"music-map/{__version__} (https://github.com/domdfcoding/music-map; dominic@davis-foster.co.uk)"
		self.session.headers.update({"User-Agent": user_agent})

	def query_sparql(self, query: str) -> dict[str, Any]:
		"""
		Query the SPARQL endpoint.

		:param query:
		"""

		# TODO: rate limiter
		resp = self.session.get(
				"https://query.wikidata.org/sparql",
				params={"query": query},
				headers={"Accept": "application/sparql-results+json"},
				)
		resp.raise_for_status()
		return resp.json()

	def get_entity(self, entity_id: str) -> dict[str, Any]:
		"""
		Get an entity by ID.

		:param entity_id:
		"""

		resp = self.session.get(f"https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/{entity_id}")
		resp.raise_for_status()
		return resp.json()

	def get_artist_data(
			self,
			artist: str,
			property_code: str,
			category_code: str,
			language: str = "@en",
			) -> dict[str, Any] | None:
		"""
		Gather data about the given artist.

		:param artist:
		:param property_code:
		:param category_code:
		:param language: Language to filter labels to, if any.
		"""

		# TODO: docstring params

		if 's' not in property_code:
			instanceof = "ps:P31"
		else:
			instanceof = "p:P31/ps:P31"
		query = f"""
		SELECT DISTINCT ?item ?itemLabel WHERE {{
		SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }}
		{{
			SELECT DISTINCT ?item WHERE {{
			?item ?label "{artist}"{language}.
			?item p:{property_code} ?statement0.
			?statement0 ({instanceof}/(wdt:P279*)) wd:{category_code}.
			}}
			LIMIT 10
		}}
		}}
		"""
		# TODO: lookup pseudonym P742 for e.g. Childish Gambino
		# TODO: case insensitive for e.g. Foster The People (in Wikidata as "Foster the People")

		sparql_response = self.query_sparql(query)

		candidates = []

		for item in sparql_response["results"]["bindings"]:

			# entity_id = item.title()
			entity_id = posixpath.split(urlparse(item["item"]["value"]).path)[-1]
			json_response = self.get_entity(entity_id)

			artist_name = get_english_label(json_response)
			if not artist_name.lower().startswith(artist.lower()):  # TODO: check all aliases in labels
				if not any(
						alias.lower().startswith(artist.lower())
						for alias in json_response["aliases"].get("en", [])
						):
					# print("Wrong name, skipping")
					continue

			occupation_codes = [x["value"]["content"] for x in json_response["statements"].get("P106", [])]
			# if category_code == "Q135106813" and "Q130857" in occupation_codes:  # "disc jockey":
			# 	print("Disc jockey, skipping")
			# 	continue

			start_of_work_period = get_start_year(json_response)
			location_of_formation_id = get_origin_id(json_response)

			if not location_of_formation_id:
				# TODO: try origins of individual members (P527)
				# print("No origin data, skipping")
				continue

			location_json_response = self.get_entity(location_of_formation_id)
			coordinates = (
					location_json_response["statements"]["P625"][0]["value"]["content"]["latitude"],
					location_json_response["statements"]["P625"][0]["value"]["content"]["longitude"],
					)

			if "enwiki" not in json_response["sitelinks"]:
				# If not documented on English Wikipedia probably not the right person
				# print("No English Wikipedia article, skipping")
				continue

			candidates.append({
					"name": artist_name,
					"id": json_response["id"],
					"year": start_of_work_period,
					"location": get_english_label(location_json_response),
					"coordinates": coordinates,
					"link": json_response["sitelinks"]["enwiki"]["url"],
					"origin_link": location_json_response["sitelinks"].get("enwiki", {}).get("url"),
					"occupation_codes": occupation_codes,
					})

		# If there's more than one candidate filter those that are Q130857 'disc jockey'
		if len(candidates) > 1:
			candidates = [c for c in candidates if "Q130857" not in c["occupation_codes"]]

		# If there's more than one take the oldest
		candidates.sort(key=itemgetter("year"))

		if not candidates:
			return None

		artist_data = candidates[0]
		del artist_data["year"]
		del artist_data["occupation_codes"]
		return artist_data


def create_session(access_token: str) -> Session:
	"""
	Create a caching requests session with authorization headers for Wikidata.

	:param access_token:
	"""

	headers = {
			"Content-Type": "application/json",
			"Authorization": f'Bearer {access_token}',
			}

	# TODO: user cache dir from platformdirs
	sess = CacheControl(requests.Session(), cache=SeparateBodyFileCache("wikidata_cache"))
	sess.headers.update(headers)

	return sess
