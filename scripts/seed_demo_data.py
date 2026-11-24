import csv
from pathlib import Path
from urllib.parse import urlparse
from datetime import date

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.connection import SessionLocal
from backend.app.models.facility import Facility
from backend.app.models.medicine import Medicine
from backend.app.models.supplier import Supplier
from backend.app.models.medicine_batch import MedicineBatch
from backend.app.models.inventory import Inventory


# Safety: refuse to write to a local or unexpected database.
host = urlparse(settings.DATABASE_URL).hostname or ""
if not host.endswith(".pooler.supabase.com"):
    raise RuntimeError("Refusing to seed: database is not the expected Supabase host.")

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "ml" / "data" / "stockout_alerts.csv"

facilities = [
    (1, "Hyderabad General Hospital", "Hospital", "Hyderabad", "Telangana"),
    (2, "Sangareddy Community Pharmacy", "Community Pharmacy", "Sangareddy", "Telangana"),
]

medicines = [
    (1, "Paracetamol", "500 mg", "Tablet", "tablets", "Analgesic"),
    (2, "Amoxicillin", "500 mg", "Capsule", "capsules", "Antibiotic"),
    (3, "Cetirizine", "10 mg", "Tablet", "tablets", "Antihistamine"),
    (4, "Ibuprofen", "400 mg", "Tablet", "tablets", "NSAID"),
]

if not CSV_PATH.exists():
    raise FileNotFoundError(f"Stockout CSV not found: {CSV_PATH}")

with CSV_PATH.open("r", newline="", encoding="utf-8") as file:
    rows = list(csv.DictReader(file))

if not rows:
    raise ValueError("Stockout CSV contains no records.")

stock = {}
for row in rows:
    key = (int(row["facility_id"]), int(row["medicine_id"]))
    stock[key] = int(float(row["previous_stock"]))

expected_keys = {
    (facility_id, medicine_id)
    for facility_id, *_ in facilities
    for medicine_id, *_ in medicines
}
if set(stock) != expected_keys:
    raise ValueError("CSV facility/medicine IDs do not match the expected demo dataset.")

with SessionLocal() as db:
    try:
        # Facilities: preserve the IDs used by the existing CSV files.
        facility_records = {}
        for expected_id, name, kind, city, state in facilities:
            record = db.scalar(
                select(Facility).where(Facility.facility_name == name)
            )
            if record is None:
                record = Facility(
                    facility_name=name,
                    facility_type=kind,
                    city=city,
                    state=state,
                )
                db.add(record)
                db.flush()

            if record.facility_id != expected_id:
                raise RuntimeError(
                    f"{name} has ID {record.facility_id}; expected {expected_id}."
                )
            facility_records[expected_id] = record

        # Medicines: preserve the IDs used by the existing CSV files.
        medicine_records = {}
        for expected_id, name, strength, form, unit, category in medicines:
            record = db.scalar(
                select(Medicine).where(Medicine.generic_name == name)
            )
            if record is None:
                record = Medicine(
                    generic_name=name,
                    strength=strength,
                    dosage_form=form,
                    unit=unit,
                    category=category,
                    nlem_listed=False,
                )
                db.add(record)
                db.flush()

            if record.medicine_id != expected_id:
                raise RuntimeError(
                    f"{name} has ID {record.medicine_id}; expected {expected_id}."
                )
            medicine_records[expected_id] = record

        # One clearly labelled demo supplier.
        supplier = db.scalar(
            select(Supplier).where(
                Supplier.supplier_name == "MediSupply Demo Supplier"
            )
        )
        if supplier is None:
            supplier = Supplier(
                supplier_name="MediSupply Demo Supplier",
                city="Hyderabad",
                state="Telangana",
            )
            db.add(supplier)
            db.flush()

        # One batch per medicine, distributed across both facilities.
        for medicine_id, medicine in medicine_records.items():
            batch_number = f"DEMO-{medicine_id}-2026"
            total_received = sum(
                stock[(facility_id, medicine_id)]
                for facility_id, *_ in facilities
            )

            batch = db.scalar(
                select(MedicineBatch).where(
                    MedicineBatch.medicine_id == medicine_id,
                    MedicineBatch.supplier_id == supplier.supplier_id,
                    MedicineBatch.batch_number == batch_number,
                )
            )

            if batch is None:
                batch = MedicineBatch(
                    medicine_id=medicine_id,
                    supplier_id=supplier.supplier_id,
                    batch_number=batch_number,
                    manufactured_on=date(2026, 1, 1),
                    expires_on=date(2027, 12, 31),
                    received_quantity=total_received,
                    batch_status="AVAILABLE",
                )
                db.add(batch)
                db.flush()
            else:
                batch.received_quantity = total_received

            # Inventory quantities match previous_stock in the CSV.
            for facility_id, *_ in facilities:
                quantity = stock[(facility_id, medicine_id)]
                inventory = db.scalar(
                    select(Inventory).where(
                        Inventory.facility_id == facility_id,
                        Inventory.batch_id == batch.batch_id,
                    )
                )

                if inventory is None:
                    inventory = Inventory(
                        facility_id=facility_id,
                        batch_id=batch.batch_id,
                        quantity_on_hand=quantity,
                        reserved_quantity=0,
                        damaged_quantity=0,
                    )
                    db.add(inventory)
                else:
                    inventory.quantity_on_hand = quantity

        db.commit()

        print("Demo data seeded successfully.")
        print("Facilities: 2")
        print("Medicines: 4")
        print("Suppliers: 1")
        print("Medicine batches: 4")
        print("Inventory records: 8")
        print("Stockout alerts: not imported yet (next step).")

    except Exception:
        db.rollback()
        raise
