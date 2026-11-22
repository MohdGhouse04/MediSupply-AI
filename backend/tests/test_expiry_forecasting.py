from datetime import date

from backend.app.services.expiry_forecasting import (
    simulate_fefo_wastage
)


def make_batch(batch_id, expires_on, usable_stock):
    return {
        "batch_id": batch_id,
        "expires_on": date.fromisoformat(expires_on),
        "usable_stock": usable_stock
    }


def test_stock_consumed_before_expiry_has_zero_wastage():
    batches = [
        make_batch(1, "2026-11-23", 100)
    ]

    forecast = {
        date(2026, 11, 22): 60,
        date(2026, 11, 23): 40
    }

    result = simulate_fefo_wastage(batches, forecast)

    assert result[1]["projected_wastage_units"] == 0
    assert result[1]["forecast_status"] == (
        "ESTIMATED_WITHIN_60_DAY_FORECAST"
    )


def test_remaining_stock_on_expiry_is_wastage():
    batches = [
        make_batch(1, "2026-11-23", 100)
    ]

    forecast = {
        date(2026, 11, 22): 30,
        date(2026, 11, 23): 20
    }

    result = simulate_fefo_wastage(batches, forecast)

    assert result[1]["projected_wastage_units"] == 50


def test_expiry_beyond_forecast_has_no_estimate():
    batches = [
        make_batch(1, "2026-12-31", 100)
    ]

    forecast = {
        date(2026, 11, 22): 20,
        date(2026, 11, 23): 20
    }

    result = simulate_fefo_wastage(batches, forecast)

    assert result[1]["projected_wastage_units"] is None
    assert result[1]["forecast_status"] == (
        "INSUFFICIENT_FORECAST_HORIZON"
    )


def test_fefo_consumes_earliest_expiring_batch_first():
    batches = [
        make_batch(2, "2026-11-24", 100),
        make_batch(1, "2026-11-23", 50)
    ]

    forecast = {
        date(2026, 11, 22): 60,
        date(2026, 11, 23): 0,
        date(2026, 11, 24): 0
    }

    result = simulate_fefo_wastage(batches, forecast)

    assert result[1]["projected_wastage_units"] == 0
    assert result[2]["projected_wastage_units"] == 90
