from services.ibge_service import geometry_centroid


def test_polygon_centroid():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
    }
    latitude, longitude = geometry_centroid(geometry)
    assert latitude == 1
    assert longitude == 1


def test_multipolygon_uses_largest_polygon():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [[[10, 10], [14, 10], [14, 14], [10, 14], [10, 10]]],
        ],
    }
    latitude, longitude = geometry_centroid(geometry)
    assert latitude == 12
    assert longitude == 12
