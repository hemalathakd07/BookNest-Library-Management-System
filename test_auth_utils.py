from auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
)

password = "student123"

hashed = hash_password(password)

print("Password hashed:", hashed != password)
print("Correct password verified:", verify_password(password, hashed))
print("Wrong password verified:", verify_password("wrong123", hashed))

token = create_access_token(user_id=1, role="student")
print("JWT token created:", bool(token))