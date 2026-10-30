"""End-to-end tests: every endpoint is run against both MySQL and MongoDB."""
import pytest

SALE = {
    "invoice_no": "581587", "stock_code": "22613", "description": "PACK OF 20 SPACEBOY NAPKINS",
    "quantity": 12, "invoice_date": "2011-12-09T12:50:00", "unit_price": 0.85,
    "customer_id": "12680", "country": "France",
}
DATABASES = ["sql", "mongo"]


def add(client, db, **changes):
    response = client.post(f"/{db}/transactions", json={**SALE, **changes})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("db", DATABASES)
def test_create_and_get(client, db):
    created = add(client, db)
    assert created["revenue"] == pytest.approx(10.2)
    assert created["is_cancelled"] is False

    fetched = client.get(f"/{db}/transactions/{created['id']}").json()
    assert fetched == created
    assert len(client.get(f"/{db}/transactions").json()) == 1


@pytest.mark.parametrize("db", DATABASES)
def test_missing_customer_becomes_unknown(client, db):
    body = {k: v for k, v in SALE.items() if k != "customer_id"}
    assert client.post(f"/{db}/transactions", json=body).json()["customer_id"] == "UNKNOWN"


@pytest.mark.parametrize("db", DATABASES)
def test_validation(client, db):
    assert client.post(f"/{db}/transactions", json={**SALE, "unit_price": 0}).status_code == 422
    assert client.post(f"/{db}/transactions", json={**SALE, "quantity": -3}).status_code == 422
    # A cancellation must have a negative quantity
    assert client.post(f"/{db}/transactions",
                       json={**SALE, "invoice_no": "C581587", "quantity": 5}).status_code == 422
    cancelled = add(client, db, invoice_no="C581587", quantity=-5)
    assert cancelled["is_cancelled"] is True and cancelled["revenue"] < 0


@pytest.mark.parametrize("db", DATABASES)
def test_update(client, db):
    created = add(client, db)
    response = client.put(f"/{db}/transactions/{created['id']}", json={"quantity": 24})
    assert response.status_code == 200
    updated = response.json()
    assert updated["quantity"] == 24
    assert updated["revenue"] == pytest.approx(20.4)
    assert updated["stock_code"] == SALE["stock_code"]  # fields not sent are kept

    # The update is checked with the same rules as a new record
    assert client.put(f"/{db}/transactions/{created['id']}",
                      json={"invoice_no": "C999999"}).status_code == 422


@pytest.mark.parametrize("db", DATABASES)
def test_delete(client, db):
    created = add(client, db)
    assert client.delete(f"/{db}/transactions/{created['id']}").status_code == 204
    assert client.get(f"/{db}/transactions/{created['id']}").status_code == 404
    assert client.delete(f"/{db}/transactions/{created['id']}").status_code == 404


@pytest.mark.parametrize("db", DATABASES)
def test_latest(client, db):
    assert client.get(f"/{db}/transactions/latest").status_code == 404
    add(client, db, invoice_date="2011-12-01T10:00:00")
    newest = add(client, db, invoice_no="581588", invoice_date="2011-12-09T09:00:00")
    add(client, db, invoice_no="581589", invoice_date="2011-12-05T10:00:00")
    assert client.get(f"/{db}/transactions/latest").json()["id"] == newest["id"]


@pytest.mark.parametrize("db", DATABASES)
def test_date_range_and_daily(client, db):
    add(client, db, invoice_no="1", invoice_date="2011-12-01T10:00:00")
    add(client, db, invoice_no="2", invoice_date="2011-12-02T23:59:00")
    add(client, db, invoice_no="C2", quantity=-2, invoice_date="2011-12-02T12:00:00")
    add(client, db, invoice_no="3", invoice_date="2011-12-03T00:00:00")

    rows = client.get(f"/{db}/transactions/range", params={"start": "2011-12-01", "end": "2011-12-02"}).json()
    assert [r["invoice_no"] for r in rows] == ["1", "C2", "2"]  # end date is inclusive, sorted by time

    daily = client.get(f"/{db}/daily", params={"start": "2011-12-02", "end": "2011-12-02"}).json()
    assert daily == [{"date": "2011-12-02", "gross_revenue": pytest.approx(10.2),
                      "net_revenue": pytest.approx(8.5), "n_invoices": 1,
                      "total_quantity": 12, "n_lines": 2}]

    bad = client.get(f"/{db}/transactions/range", params={"start": "2011-12-05", "end": "2011-12-01"})
    assert bad.status_code == 400


def test_invalid_mongo_id(client):
    assert client.get("/mongo/transactions/not-an-id").status_code == 400


def test_sql_moving_line_removes_empty_invoice(client):
    from api.sql_db import Invoice, SessionLocal

    created = add(client, "sql")
    client.put(f"/sql/transactions/{created['id']}", json={"invoice_no": "581600"})
    with SessionLocal() as session:
        assert session.get(Invoice, "581587") is None
        assert session.get(Invoice, "581600") is not None
