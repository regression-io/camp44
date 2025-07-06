from camp44.main import app

# Print all registered routes
print("Registered FastAPI routes:")
for route in app.routes:
    print(f"Route: {route.path}, methods: {route.methods}")
