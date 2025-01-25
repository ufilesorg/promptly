from apps.ai.routes import router as ai_router
from fastapi_mongo_base.core import app_factory

from . import config

app = app_factory.create_app(settings=config.Settings(), serve_coverage=False)
app.include_router(ai_router, prefix=config.Settings.base_path)
