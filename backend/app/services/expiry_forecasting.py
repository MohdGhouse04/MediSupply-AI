def simulate_fefo_wastage(batches, forecast):
    """
    Simulate demand allocation across medicine batches using FEFO.

    Returns a mapping of batch_id to projected wastage and forecast status.
    Does not modify the input batches.
    """
    if not forecast:
        raise ValueError("Forecast cannot be empty")

    forecast_dates = sorted(forecast)
    first_date = forecast_dates[0]
    last_date = forecast_dates[-1]

    working_batches = []

    for batch in batches:
        working_batches.append({
            **batch,
            "remaining_stock": batch["usable_stock"],
            "projected_wastage": None
        })

    working_batches.sort(
        key=lambda item: (item["expires_on"], item["batch_id"])
    )

    for forecast_date in forecast_dates:
        daily_demand = max(0, float(forecast[forecast_date]))

        # Mark stock expired before this forecast date as wastage.
        for batch in working_batches:
            if (
                batch["remaining_stock"] > 0
                and batch["expires_on"] < forecast_date
            ):
                batch["projected_wastage"] = batch["remaining_stock"]
                batch["remaining_stock"] = 0

        # Allocate demand using First Expiry, First Out.
        for batch in working_batches:
            if daily_demand <= 0:
                break

            if batch["remaining_stock"] <= 0:
                continue

            if batch["expires_on"] < forecast_date:
                continue

            issued = min(batch["remaining_stock"], daily_demand)
            batch["remaining_stock"] -= issued
            daily_demand -= issued

        # Remaining stock expires at the end of its expiry date.
        for batch in working_batches:
            if batch["expires_on"] == forecast_date:
                batch["projected_wastage"] = batch["remaining_stock"]
                batch["remaining_stock"] = 0

    results = {}

    for batch in working_batches:
        expiry_date = batch["expires_on"]

        if expiry_date < first_date:
            wastage = batch["usable_stock"]
            status = "EXPIRES_BEFORE_FORECAST_WINDOW"

        elif expiry_date <= last_date:
            wastage = batch["projected_wastage"]

            if wastage is None:
                wastage = batch["remaining_stock"]

            status = "ESTIMATED_WITHIN_60_DAY_FORECAST"

        else:
            wastage = None
            status = "INSUFFICIENT_FORECAST_HORIZON"

        results[batch["batch_id"]] = {
            "projected_wastage_units": wastage,
            "forecast_status": status
        }

    return results
