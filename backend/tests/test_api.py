from app.config import Settings
from app.services import refresh


def seed_demo():
    refresh.run_refresh("manual", settings=Settings(demo_mode=True, scrape_delay_seconds=0))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_metrics_exposed(client):
    resp = client.get("/metrics/")
    assert resp.status_code == 200
    assert "pricehunt_scrape_runs_total" in resp.text


def test_stores_seeded_with_shortcuts(client):
    stores = client.get("/api/stores").json()
    slugs = {s["slug"] for s in stores}
    assert {"amazon", "ldlc", "mediamarkt", "pccomponentes"} <= slugs
    assert all(s["shortcut_url"].startswith("https://") for s in stores)


def test_create_and_delete_shortcut(client):
    resp = client.post(
        "/api/stores",
        json={
            "name": "Neobyte",
            "shortcut_url": "https://www.neobyte.es",
            "accent_color": "#123abc",
        },
    )
    assert resp.status_code == 201
    store = resp.json()
    assert store["slug"] == "neobyte" and store["tracked"] is False
    assert (
        client.post(
            "/api/stores", json={"name": "Neobyte", "shortcut_url": "https://www.neobyte.es"}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/stores/{store['id']}").status_code == 204


def test_create_store_rejects_http(client):
    resp = client.post("/api/stores", json={"name": "Insegura", "shortcut_url": "http://x.com"})
    assert resp.status_code == 422


def test_cannot_delete_tracked_store(client):
    amazon = next(s for s in client.get("/api/stores").json() if s["slug"] == "amazon")
    assert client.delete(f"/api/stores/{amazon['id']}").status_code == 409


def test_watchlist_crud(client):
    resp = client.post("/api/watchlist", json={"query": "Glorious"})
    assert resp.status_code == 201 and resp.json()["query"] == "glorious"
    assert client.post("/api/watchlist", json={"query": "glorious"}).status_code == 409
    assert client.post("/api/watchlist", json={"query": "<script>"}).status_code == 422
    assert client.delete(f"/api/watchlist/{resp.json()['id']}").status_code == 204


def test_deals_filters_and_sorting(client):
    seed_demo()
    page = client.get("/api/deals").json()
    assert page["total"] > 0
    discounts = [d["discount_pct"] for d in page["items"]]
    assert discounts == sorted(discounts, reverse=True)
    assert all(d["is_new"] for d in page["items"])

    cheap = client.get("/api/deals", params={"sort": "price_asc"}).json()["items"]
    assert [d["price"] for d in cheap] == sorted(d["price"] for d in cheap)

    only_ldlc = client.get("/api/deals", params={"store": "ldlc"}).json()["items"]
    assert only_ldlc and all(d["store_slug"] == "ldlc" for d in only_ldlc)

    big = client.get("/api/deals", params={"min_discount": 30}).json()["items"]
    assert all(d["discount_pct"] >= 30 for d in big)

    deal_id = page["items"][0]["id"]
    history = client.get(f"/api/deals/{deal_id}/history").json()
    assert len(history) == 1
    assert client.get("/api/deals/999999/history").status_code == 404


def test_stats_and_runs(client):
    seed_demo()
    stats = client.get("/api/stats").json()
    assert stats["active_deals"] > 0
    assert stats["last_run"]["status"] == "success"
    assert stats["refreshing"] is False
    assert client.get("/api/runs").json()[0]["trigger"] == "manual"
    cats = client.get("/api/categories").json()
    assert sum(c["count"] for c in cats) == stats["active_deals"]


def test_manual_refresh_endpoint(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        refresh, "start_in_background", lambda trigger: calls.append(trigger) or True
    )
    assert client.post("/api/refresh").status_code == 202
    assert calls == ["manual"]
    monkeypatch.setattr(refresh, "start_in_background", lambda trigger: False)
    assert client.post("/api/refresh").status_code == 409


def test_verticals_are_separated(client):
    seed_demo()
    tech = client.get("/api/deals?limit=200").json()
    cars = client.get("/api/deals?vertical=cars&limit=200").json()
    assert tech["total"] > 0 and cars["total"] > 0
    assert {d["store_slug"] for d in cars["items"]} <= {"dasweltauto", "ocasionplus"}
    assert "dasweltauto" not in {d["store_slug"] for d in tech["items"]}
    assert {c["name"] for c in client.get("/api/categories?vertical=cars").json()} <= {
        "SUV",
        "Compacto",
        "Utilitario",
        "Familiar",
    }
    assert {s["slug"] for s in client.get("/api/stores?vertical=cars").json()} == {
        "dasweltauto",
        "ocasionplus",
        "subastas-boe",
    }
    terms = {t["query"] for t in client.get("/api/watchlist?vertical=cars").json()}
    assert {"seat", "cupra"} <= terms and "corsair" not in terms
    assert client.get("/api/stats?vertical=cars").json()["active_deals"] == cars["total"]
    assert client.get("/api/deals?vertical=boats").status_code == 422


def test_watch_term_keeps_its_vertical(client):
    resp = client.post("/api/watchlist", json={"query": "mazda", "vertical": "cars"})
    assert resp.status_code == 201 and resp.json()["vertical"] == "cars"
    assert "mazda" not in {t["query"] for t in client.get("/api/watchlist").json()}
