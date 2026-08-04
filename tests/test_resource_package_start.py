import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "edu-api"))

from routers.resource_packages import (
    _BACKGROUND_RESOURCE_PACKAGE_TASKS,
    start_resource_package_generation,
)


class ResourcePackageStartTests(unittest.TestCase):
    def test_start_returns_package_before_background_generation_finishes(self):
        async def exercise():
            release_generation = asyncio.Event()
            generation_finished = asyncio.Event()
            package = SimpleNamespace(id="package-1", status="generating")

            class FakeRequest:
                @staticmethod
                def model_dump():
                    return {"target_topic": "Streaming", "resource_types": ["lecture_note"]}

            class FakeService:
                async def generate_resource_package(self, *, event_sink, **_kwargs):
                    await event_sink(
                        SimpleNamespace(
                            event="package_started",
                            package_id=package.id,
                        )
                    )
                    await release_generation.wait()
                    generation_finished.set()
                    return package

                @staticmethod
                def get_resource_package(user_id, project_id, package_id):
                    assert (user_id, project_id, package_id) == (
                        "user-1",
                        "project-1",
                        "package-1",
                    )
                    return package

            try:
                result = await start_resource_package_generation(
                    "project-1",
                    FakeRequest(),
                    user=SimpleNamespace(id="user-1"),
                    service=FakeService(),
                )
                self.assertIs(result, package)
                self.assertFalse(generation_finished.is_set())
                self.assertTrue(_BACKGROUND_RESOURCE_PACKAGE_TASKS)
            finally:
                release_generation.set()
                tasks = list(_BACKGROUND_RESOURCE_PACKAGE_TASKS)
                if tasks:
                    await asyncio.gather(*tasks)

            self.assertTrue(generation_finished.is_set())

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
