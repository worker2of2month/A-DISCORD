"""City combat terrains and the national city clusters that use them.

A city cluster is a connected group of city provinces; every province of one
cluster shares a terrain. The coastal geography builder writes the terrain of
the southern provinces it owns. The remaining provinces are authored in
map/definition.csv and the tests compare them with this table.
"""

from __future__ import annotations

# Combat terrains of city provinces: city VPs and settlement checks accept each.
CITY_TERRAINS = frozenset({
    "urban",
    "vorkernsberg",
    "desert_city",
    "hill_city",
    "fada_city",
    "dopotoydron_city",
    "south_harbour_city",
    "svetlogorye_town",
    "kefreyt_city",
    "stelander_city",
    "rich_city",
})

NATIONAL_CITY_CLUSTERS = {
    # Stelander capital: the Bronze Congress and the Fada centre.
    "fada_city": (145, 16351, 16366, 16368, 16374, 16377, 16386),
    # Kefreyt capital with the Kefreyt arms combine.
    "dopotoydron_city": (16514, 16515, 16519, 16521, 16530, 16535),
    # Seat of the Svetlogorye governorate.
    "south_harbour_city": (16716, 16881, 16884, 16892),
    "svetlogorye_town": (16721, 16885, 16887, 16890),
    "kefreyt_city": (16510, 16511, 16534, 16645, 16653),
    "stelander_city": (16345, 16349, 16448, 16450, 16529, 16547),
    # Wealthy cities of Nodrul and Stelander: Cussington, Ostrium, New Monaii, Abilia.
    "rich_city": (12434, 16346, 16356, 16363, 16369, 16440, 16441, 16442, 16444, 16445),
}

NATIONAL_CITY_TERRAIN = {
    province: terrain
    for terrain, provinces in NATIONAL_CITY_CLUSTERS.items()
    for province in provinces
}
