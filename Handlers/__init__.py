from aiogram import Router

from Handlers.errors import router as errors_router
from Handlers.file2link import router as file2link_router
from Handlers.links import router as links_router
from Handlers.search import router as search_router
from Handlers.start import router as start_router


def setup_routers() -> Router:
    router = Router(name="main")
    router.include_router(start_router)
    router.include_router(search_router)
    router.include_router(file2link_router)
    router.include_router(links_router)
    router.include_router(errors_router)
    return router
