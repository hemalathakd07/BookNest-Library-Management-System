from database import engine, Base
import models

# Create all registered tables in PostgreSQL
Base.metadata.create_all(bind=engine)

print("Tables created successfully!")