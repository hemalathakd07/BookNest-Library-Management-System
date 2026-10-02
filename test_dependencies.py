from dependencies import bearer_scheme, get_current_user

print("Authentication dependency imported successfully!")
print("Bearer scheme:", bearer_scheme.scheme_name)
print("Current user dependency:", get_current_user.__name__)