from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# DOPASUJ do pochodzenia frontendu: CRA=3000, Vite=5173
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # jeśli używasz cookies/sesji
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/company")
def get_companies():
    return [
        {"id": 1, "name": "OpenAI", "industry": "AI"},
        {"id": 2, "name": "SpaceX", "industry": "Aerospace"},
    ]