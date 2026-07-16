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

# resp = requests.get("https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q42/statements", headers=headers)
# resp.raise_for_status()

# pprint.pprint(resp.json())

origins_datafile = PathPlus("origins_v2.json")
if origins_datafile.exists():
	origins = origins_datafile.load_json()
else:
	origins = {}


def save_origins():
	origins_datafile.dump_json(origins, indent=2)


atexit.register(save_origins)

wd_api = WikidataAPI(session=sess)


def lookup_origin(artist: str) -> dict:
	for language in ('', "@en"):
		for code in [
				("P31", "Q2088357"),  # Musical ensemble
				("P106/ps:P106", "Q135106813"),  # musical occupation
				]:
			data = wd_api.get_artist_data(artist, *code, language)
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
