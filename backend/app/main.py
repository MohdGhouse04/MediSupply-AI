
from fastapi import FastAPI

from backend.app.api.inventory import router as inventory_router
from backend.app.api.inventory_transactions import router as transaction_router
from backend.app.api.medicines import router as medicine_router
from backend.app.api.facilities import router as facility_router
from backend.app.api.suppliers import router as supplier_router
from backend.app.api.medicine_batches import router as batch_router

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
