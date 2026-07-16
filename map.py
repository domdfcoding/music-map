# 3rd party
import folium
from domdf_folium_tools import set_branca_random_seed
from domdf_python_tools.paths import PathPlus
from folium.plugins import MarkerCluster
from folium_map_search import MapSearchControl, MapSearchProvider
from folium_reset_control import ResetViewControl
from folium_zoom_state import ZoomStateJS, ZoomStateMap

set_branca_random_seed("music")


def popup(text: str) -> folium.Popup:
	popup_text = text.replace('\n', "<br>")
	style = "min-width: fit-content; text-wrap: nowrap;"
	return folium.Popup(f"<div class='text-center', style='{style}'>{popup_text}</div>")


m = ZoomStateMap(maxZoom=13)

mc = MarkerCluster().add_to(m)
ZoomStateJS().add_to(m)
ResetViewControl(centre=m.location, zoom=m.options["zoom"]).add_to(m)
search_provider = MapSearchProvider(layer=mc, map=m, feature_type="settlement")
MapSearchControl(
		provider=search_provider,
		auto_complete_delay=1000,  # Effectively turns off autocomplete to comply with Nominatum TOS
		show_marker=False,
		max_suggestions=15,
		search_label="Enter town or artist name",
		disable_enter_search=True,  # Otherwise markers don't appear 🤷
		close_on_submit=True,
		).add_to(m)

origins: dict = PathPlus("origins_v2.json").load_json()

print(list(origins.items())[0])
for band, band_data in origins.items():

	marker = folium.Marker(
			band_data["coordinates"],
			popup=popup(
					"<h3><a href='{link}'>{name}</a></h3><h4><a href='{origin_link}'>{location}</a></h4>"
					.format_map(band_data),
					),
			search_name=band,
			).add_to(mc)

html = m.get_root().render()
PathPlus("index.html").write_clean(html)
