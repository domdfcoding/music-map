#!/usr/bin/env python3
#
#  map.py
"""
Map generation functions.
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
from typing import Any

# 3rd party
import folium
from domdf_folium_tools import EmbeddedCSSJS
from domdf_folium_tools.elements import add_to, set_id
from folium.plugins import MarkerCluster
from folium_map_search import MapSearchControl, MapSearchProvider
from folium_reset_control import ResetViewControl
from folium_zoom_state import ZoomStateJS, ZoomStateMap

__all__ = ["make_map", "popup"]


def popup(text: str) -> folium.Popup:
	"""
	Create a popup.

	:param text:
	"""

	popup_text = text.replace('\n', "<br>")
	style = "min-width: fit-content; text-wrap: nowrap;"
	return folium.Popup(f"<div class='text-center', style='{style}'>{popup_text}</div>")


def make_map(origins: dict[str, Any]) -> folium.Map:
	"""
	Create the folium map.

	:param origins: Data on artists and their origins.
	"""

	zoom_start = 3
	map_centre = (25, 0)

	osm_tiles = set_id(
			folium.TileLayer(
					tiles="OpenStreetMap",
					name="OpenStreetMap",
					referrerPolicy="strict-origin-when-cross-origin",
					attr='Map &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Data from <a href="wikidata.org">Wikidata</a>',
					),
			"osm_carto",
			)

	m = ZoomStateMap(
			map_centre,
			maxZoom=13,
			zoom_start=zoom_start,
			font_size="1.3rem",
			tiles=osm_tiles,
			)

	mc = add_to(MarkerCluster(), m, "artists")
	ZoomStateJS().add_to(m)
	ResetViewControl(centre=map_centre, zoom=zoom_start).add_to(m)
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

	for band, band_data in origins.items():

		popup_html = "<h3><a href='{link}'>{name}</a></h3>".format_map(band_data)
		if band_data["origin_link"]:
			popup_html += "<h4><a href='{origin_link}'>{location}</a></h4>".format_map(band_data)
		else:
			popup_html += "<h4>{location}</h4>".format_map(band_data)

		folium.Marker(
				band_data["coordinates"],
				popup=popup(popup_html),
				search_name=band,
				).add_to(mc)

	custom_css = """
.leaflet-popup-close-button {
	margin-right: 4px;
	margin-top: 4px;

	span {
		font-size: 24px;
	}
}

.leaflet-control.geosearch form {
	input {
		font-size: 14px !important;
	}

	.results.active {
		font-size: 14px;
	}
}
"""

	EmbeddedCSSJS(custom_css=custom_css).add_to(m)

	return m
