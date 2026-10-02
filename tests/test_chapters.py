import asyncio
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DocumentTooLarge, DuplicateKeyError, ServerSelectionTimeoutError

from backend.database import ensure_chapter_index, get_database
from backend.main import app


class ChapterApiTests(unittest.TestCase):
    def setUp(self):
        self.comic_id = ObjectId()
        self.chapter_id = ObjectId()
        self.catalogs = MagicMock(find_one=AsyncMock(return_value={"_id": self.comic_id}))
        self.chapters = MagicMock(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=self.chapter_id)))
        self.database = MagicMock()
        self.database.get_collection.side_effect = {"catalogs": self.catalogs, "chapters": self.chapters}.__getitem__
        app.dependency_overrides[get_database] = lambda: self.database
        self.addCleanup(app.dependency_overrides.clear)
        index_patch = patch("backend.main.ensure_chapter_index", new_callable=AsyncMock)
        self.prepare_index = index_patch.start()
        self.addCleanup(index_patch.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.url = f"/api/comics/{self.comic_id}/chapters"
        self.payload = {"chapter_number": 1, "title": " Início "}

    def test_create_links_to_parent_and_sets_server_fields(self):
        # Motor adiciona _id ao dicionário inserido; isso não deve vazar na resposta.
        async def insert(document):
            document["_id"] = self.chapter_id
            return SimpleNamespace(inserted_id=self.chapter_id)
        self.chapters.insert_one.side_effect = insert
        response = self.client.post(f"/api/comics/{str(self.comic_id).upper()}/chapters", json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["id"], str(self.chapter_id))
        self.assertEqual(body["comic_id"], str(self.comic_id))
        self.assertEqual(body["title"], "Início")
        self.assertEqual(body["chapter_number"], 1)
        self.assertEqual(body["initial_pages"], [])
        self.assertIsNotNone(datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")).tzinfo)
        self.assertNotIn("_id", body)
        self.catalogs.find_one.assert_awaited_once_with({"_id": self.comic_id}, {"_id": 1})
        self.prepare_index.assert_awaited_once()
        self.chapters.insert_one.assert_awaited_once()

    def test_missing_parent_prevents_index_and_insert(self):
        self.catalogs.find_one.return_value = None
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 404)
        self.prepare_index.assert_not_awaited()
        self.chapters.insert_one.assert_not_awaited()

    def test_invalid_id_does_not_reach_database(self):
        self.assertEqual(self.client.post("/api/comics/invalid/chapters", json=self.payload).status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_invalid_body_does_not_reach_database(self):
        invalid = [
            {"chapter_number": n, "title": "Título"} for n in (0, -1, True, 1.5, "1", 2**63)
        ] + [{"chapter_number": 1, "title": " "}, {"title": "Título"}]
        for body in invalid:
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.url, json=body).status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_client_cannot_override_server_fields_or_submit_pages(self):
        for field, value in (("comic_id", str(ObjectId())), ("created_at", "2020-01-01T00:00:00Z"), ("initial_pages", [])):
            with self.subTest(field=field):
                self.assertEqual(self.client.post(self.url, json={**self.payload, field: value}).status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_duplicate_number_returns_conflict_without_internal_details(self):
        self.chapters.insert_one.side_effect = DuplicateKeyError("internal database details")
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("internal", response.text)

    def test_database_errors_at_each_stage_return_503(self):
        for operation in (self.catalogs.find_one, self.prepare_index, self.chapters.insert_one):
            with self.subTest(operation=operation):
                operation.side_effect = ServerSelectionTimeoutError("secret")
                response = self.client.post(self.url, json=self.payload)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret", response.text)
                operation.side_effect = None

    def test_oversized_document_returns_413(self):
        self.chapters.insert_one.side_effect = DocumentTooLarge("internal details")
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 413)
        self.assertNotIn("internal", response.text)

    def test_index_failure_does_not_insert_chapter(self):
        self.prepare_index.side_effect = DuplicateKeyError("existing duplicates")
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 503)
        self.chapters.insert_one.assert_not_awaited()


class ChapterIndexTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state = SimpleNamespace(chapter_index_ready=False, chapter_index_lock=asyncio.Lock())
        self.request = SimpleNamespace(app=SimpleNamespace(state=self.state))
        self.database = MagicMock()
        self.create_index = AsyncMock()
        self.database.get_collection.return_value.create_index = self.create_index

    async def test_concurrent_preparation_runs_once(self):
        async def build(*args, **kwargs):
            await asyncio.sleep(0)
        self.create_index.side_effect = build
        await asyncio.gather(*(ensure_chapter_index(self.request, self.database) for _ in range(3)))
        self.create_index.assert_awaited_once_with(
            [("comic_id", 1), ("chapter_number", 1)], unique=True, name="comic_chapter_number_unique",
        )

    async def test_failure_can_be_retried(self):
        self.create_index.side_effect = [ServerSelectionTimeoutError("offline"), "index"]
        with self.assertRaises(ServerSelectionTimeoutError):
            await ensure_chapter_index(self.request, self.database)
        self.assertFalse(self.state.chapter_index_ready)
        await ensure_chapter_index(self.request, self.database)
        self.assertTrue(self.state.chapter_index_ready)
        self.assertEqual(self.create_index.await_count, 2)
