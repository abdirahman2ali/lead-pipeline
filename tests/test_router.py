from src.router import assign_tier, route


def test_hot_tier():
    assert assign_tier(80) == "hot"
    assert assign_tier(75) == "hot"


def test_warm_tier():
    assert assign_tier(60) == "warm"
    assert assign_tier(50) == "warm"


def test_cold_tier():
    assert assign_tier(49) == "cold"
    assert assign_tier(1) == "cold"


def test_route_returns_tuple():
    tier, rep = route(80)
    assert tier == "hot"
    assert isinstance(rep, str)
    assert "@" in rep or rep == "unassigned"


def test_route_uses_env_rep_pool(monkeypatch):
    monkeypatch.setenv("REP_POOL", "alice@co.com,bob@co.com")
    import src.router as r
    r._config_cache = None
    r._rep_index = 0
    tier, rep = route(80)
    assert rep in ("alice@co.com", "bob@co.com")
