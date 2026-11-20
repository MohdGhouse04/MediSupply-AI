
from fastapi import FastAPI

from backend.app.api.inventory import router as inventory_router
from backend.app.api.inventory_transactions import router as transaction_router
from backend.app.api.medicines import router as medicine_router
from backend.app.api.facilities import router as facility_router
from backend.app.api.suppliers import router as supplier_router
from backend.app.api.medicine_batches import router as batch_router
from backend.app.api.stockout_alerts import router as stockout_alerts_router
from backend.app.api.fefo import router as fefo_router
from backend.app.api.expiry_management import router as expiry_management_router

app = FastAPI(
    title="MediSupply AI",
    description="Intelligent Medicine Availability and Supply Chain Platform",
    version="1.0.0"
)

# Register API routers
app.include_router(inventory_router)
app.include_router(transaction_router)
app.include_router(medicine_router)
app.include_router(facility_router)
app.include_router(supplier_router)
app.include_router(batch_router)
app.include_router(stockout_alerts_router)
app.include_router(fefo_router)
app.include_router(expiry_management_router)


@app.get("/")
def home():
    return {
        "project": "MediSupply AI",
        "message": "Medicine Supply Chain Intelligence Platform",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MediSupply AI Backend"
    }
