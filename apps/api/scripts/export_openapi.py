"""Write the actual FastAPI OpenAPI schema for frontend type generation."""

import json
from pathlib import Path

from app.main import app

destination = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "openapi.json"
destination.write_text(json.dumps(app.openapi(), indent=2))
print(destination)
