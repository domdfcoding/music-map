# 3rd party
from domdf_folium_tools import set_branca_random_seed
from domdf_python_tools.paths import PathPlus

# this package
from music_map.map import make_map

set_branca_random_seed("music")
origins: dict = PathPlus("origins_v2.json").load_json()
m = make_map(origins)
html = m.get_root().render()
PathPlus("index.html").write_clean(html)
