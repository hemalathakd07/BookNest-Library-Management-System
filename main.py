from fastapi import FastAPI
from routers import auth
from routers import books
from routers import borrow

app = FastAPI(title="BookNest - Digital Library")

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(borrow.router)


@app.get("/")
def root():
    return {"message": "Welcome to BookNest"}