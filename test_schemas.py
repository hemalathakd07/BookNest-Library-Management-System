from schemas import UserCreate, BookCreate


# Test valid user
user = UserCreate(
    name="Ananya",
    email="ananya@example.com",
    password="student123"
)

print("User schema:")
print(user)

# Test valid book
book = BookCreate(
    title="Python Programming",
    author="John Smith",
    isbn="9781234567890",
    category="Programming",
    total_copies=5
)

print("\nBook schema:")
print(book)