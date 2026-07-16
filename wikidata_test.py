# stdlib
import atexit
import datetime
import posixpath
import sys
import time
from collections.abc import Iterator
from operator import itemgetter
from typing import Any
from urllib.parse import urlparse

# 3rd party
import requests
from cachecontrol import CacheControl
from cachecontrol.caches import SeparateBodyFileCache
from domdf_python_tools.paths import PathPlus, unwanted_dirs
from mutagen.id3 import ID3, TPE2


def from_iso_zulu(the_datetime: str) -> datetime.datetime:
	"""
	Constructs a :class:`datetime.datetime` object from an
	`ISO 8601 <https://en.wikipedia.org/wiki/ISO_8601>`_ format string.

	This function understands the character ``Z`` as meaning Zulu time (GMT/UTC).

	:param the_datetime:
	"""  # noqa: D400

	return datetime.datetime.fromisoformat(the_datetime.replace('Z', "+00:00").lstrip('+'))


headers = {
		"Content-Type": "application/json",
		"Authorization": f'Bearer {access_token}',
		"User-Agent": "music-map/0.0.0 (https://github.com/domdfcoding/music-map; dominic@davis-foster.co.uk)",
		}

sess = CacheControl(requests.Session(), cache=SeparateBodyFileCache("wikidata_cache"))
sess.headers.update(headers)

# resp = requests.get("https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q42/statements", headers=headers)
# resp.raise_for_status()

# pprint.pprint(resp.json())


def get_start_date(wikidata_data: dict) -> int:
	for code in ["P2031", "P571"]:  # P571: date of inception
		if code in wikidata_data["statements"]:
			value = wikidata_data["statements"][code][0]["value"]
			if value["type"] != "novalue":
				return int(value["content"]["time"].lstrip('+').split('-', 1)[0])

	return sys.maxsize


def get_origin_id(wikidata_data: dict) -> str | None:
	for code in ["P740", "P19", "P27", "P495"]:
		# P740: location of formation, P19: place of birth, P27: citizenship, P495: country of origin
		if code in wikidata_data["statements"]:
			value = wikidata_data["statements"][code][0]["value"]
			if value["type"] != "novalue":
				return value["content"]

	return None


def get_english_label(wikidata_data: dict) -> str:
	labels: dict[str, str] = wikidata_data["labels"]
	return labels.get("en", labels.get("mul", ''))


def get_artist_data(
		artist: str,
		property_code: str,
		category_code: str,
		language: str = "@en",
		) -> dict[str, Any] | None:

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

	sparql_response = sess.get(
			"https://query.wikidata.org/sparql",
			params={"query": query},
			headers={"Accept": "application/sparql-results+json"},
			)
	sparql_response.raise_for_status()

	candidates = []

	for item in sparql_response.json()["results"]["bindings"]:

		# entity_id = item.title()
		entity_id = posixpath.split(urlparse(item["item"]["value"]).path)[-1]
		resp = sess.get(f"https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/{entity_id}")
		resp.raise_for_status()

		json_response = resp.json()

		artist_name = get_english_label(json_response)
		if not artist_name.lower().startswith(artist.lower()):  # TODO: check all aliases in labels
			if not any(
					alias.lower().startswith(artist.lower()) for alias in json_response["aliases"].get("en", [])
					):
				# print("Wrong name, skipping")
				continue

		occupation_codes = [x["value"]["content"] for x in json_response["statements"].get("P106", [])]
		# if category_code == "Q135106813" and "Q130857" in occupation_codes:  # "disc jockey":
		# 	print("Disc jockey, skipping")
		# 	continue

		start_of_work_period = get_start_date(json_response)
		location_of_formation_id = get_origin_id(json_response)

		if not location_of_formation_id:
			# TODO: try origins of individual members (P527)
			# print("No origin data, skipping")
			continue

		location_resp = sess.get(
				f"https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/{location_of_formation_id}",
				)
		location_resp.raise_for_status()
		location_json_response = location_resp.json()
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


origins_datafile = PathPlus("origins_v2.json")
if origins_datafile.exists():
	origins = origins_datafile.load_json()
else:
	origins = {}


def save_origins():
	origins_datafile.dump_json(origins, indent=2)


atexit.register(save_origins)


def iter_artists(path: PathPlus) -> Iterator[str]:

	artists = set()

	for file in path.iterchildren(
			match="**/*.mp*",
			exclude_dirs={*unwanted_dirs, ".stversions", "Various artists"},
			):
		tags = ID3(file)
		if "TPE1" not in tags:
			continue

		artist: str = tags["TPE1"].text[0]
		if artist in artists:
			continue

		multiple_act_hints = ['/', ", ", " with ", " and ", " feat", " ft", " & ", " vs ", " vs. "]
		artist_lowercase = artist.lower()
		if any(h in artist_lowercase for h in multiple_act_hints):
			continue

		if "TPE2" in tags:
			album_artist: TPE2 = tags["TPE2"]
			if album_artist.text[0].lower() in {"various", "various artists"}:
				continue

		artists.add(artist)
		yield artist


def lookup_origin(artist: str) -> dict:
	for language in ('', "@en"):
		for code in [
				("P31", "Q2088357"),  # Musical ensemble
				("P106/ps:P106", "Q135106813"),  # musical occupation
				]:
			data = get_artist_data(artist, *code, language)
			time.sleep(1)
			if data is not None:
				return data


# for artist in ["Genesis"]:
# # for artist in ["Genesis", "Pink Floyd", "Electric Light Orchestra", "Jade Bird"]:
# for artist in ["Genesis", "Jade Bird"]:
# for artist in ["Bob Dylan"]:
# 	print(artist)
# 	print(lookup_origin(artist))

# exit()

with open("problems.txt", 'w', encoding="UTF-8") as fp:

	for artist in iter_artists(PathPlus("~/Nextcloud/Music - original").expanduser()):
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
