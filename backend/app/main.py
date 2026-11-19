from fastapi import FastAPI

app = FastAPI(
    title="MediSupply AI",
    description="Intelligent Medicine Availability and Supply Chain Platform",
    version="1.0.0"
)


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