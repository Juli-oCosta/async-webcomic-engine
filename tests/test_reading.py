from datetime import datetime, timezone
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DocumentTooLarge, DuplicateKeyError, ServerSelectionTimeoutError

from backend.database import ensure_page_index, get_database
from backend.main import app


class ChapterReadingTests(unittest.TestCase):
    def setUp(self):
        self.comic_id = ObjectId()
        self.catalogs = MagicMock(find_one=AsyncMock(return_value={"_id": self.comic_id}))
        self.chapters = MagicMock()
        self.cursor = MagicMock()
        self.cursor.sort.return_value = self.cursor
        self.cursor.limit.return_value = self.cursor
        self.cursor.to_list = AsyncMock(return_value=[])
        self.chapters.find.return_value = self.cursor
        self.database = MagicMock()
        self.database.get_collection.side_effect = {"catalogs": self.catalogs, "chapters": self.chapters}.__getitem__
        app.dependency_overrides[get_database] = lambda: self.database
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.url = f"/api/comics/{self.comic_id}/chapters"

    def test_reading_order_cursor_and_parent_filter(self):
        identifier = ObjectId()
        self.cursor.to_list.return_value = [{
            "_id": identifier, "comic_id": str(self.comic_id), "chapter_number": 5,
            "title": "Capítulo cinco", "created_at": datetime.now(timezone.utc),
        }]
        response = self.client.get(self.url + "?limit=2&after=3")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["id"], str(identifier))
        self.assertNotIn("initial_pages", response.json()[0])
        self.chapters.find.assert_called_once_with(
            {"comic_id": str(self.comic_id), "chapter_number": {"$gt": 3}}, {"initial_pages": 0},
        )
        self.cursor.sort.assert_called_once_with("chapter_number", 1)
        self.cursor.limit.assert_called_once_with(2)

    def test_existing_work_without_chapters_is_empty(self):
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_missing_work_is_not_an_empty_list(self):
        self.catalogs.find_one.return_value = None
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.chapters.find.assert_not_called()

    def test_invalid_query_does_not_read_database(self):
        for suffix in ("?limit=0", "?limit=101", "?after=-1", "?after=1.5", f"?after={2**63}"):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(self.url + suffix).status_code, 422)
        self.assertEqual(self.client.get('/api/comics/invalid/chapters').status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_database_failure_is_503_without_details(self):
        self.cursor.to_list.side_effect = ServerSelectionTimeoutError("secret")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)


class PageApiTests(unittest.TestCase):
    def setUp(self):
        self.chapter_id = ObjectId()
        self.page_id = ObjectId()
        self.chapters = MagicMock(find_one=AsyncMock(return_value={"_id": self.chapter_id}))
        self.pages = MagicMock(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=self.page_id)))
        self.database = MagicMock()
        self.database.get_collection.side_effect = {"chapters": self.chapters, "pages": self.pages}.__getitem__
        app.dependency_overrides[get_database] = lambda: self.database
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        index_patch = patch("backend.reading.ensure_page_index", new_callable=AsyncMock)
        self.prepare_index = index_patch.start()
        self.addCleanup(index_patch.stop)
        self.url = f"/api/chapters/{self.chapter_id}/pages"
        self.payload = {"page_number": 1, "image_url": "/static/demo/page-01.svg", "width": 900, "height": 1200}

    def make_cursor(self, rows):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=rows)
        self.pages.find.return_value = cursor
        return cursor

    def test_create_owns_parent_and_handles_driver_mutation(self):
        async def insert(document):
            document["_id"] = self.page_id
            return SimpleNamespace(inserted_id=self.page_id)
        self.pages.insert_one.side_effect = insert
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json(), {**self.payload, "id": str(self.page_id), "chapter_id": str(self.chapter_id), "page_number_text": "1"})
        self.prepare_index.assert_awaited_once()

    def test_missing_parent_prevents_insert_and_read(self):
        self.chapters.find_one.return_value = None
        for method in ("get", "post"):
            response = self.client.get(self.url) if method == "get" else self.client.post(self.url, json=self.payload)
            self.assertEqual(response.status_code, 404)
        self.pages.insert_one.assert_not_awaited()
        self.pages.find.assert_not_called()

    def test_invalid_reference_number_size_and_server_fields(self):
        changes = [
            {"page_number": v} for v in (True, "1", 0, 2**63)
        ] + [
            {"image_url": v} for v in ("javascript:alert(1)", "data:image/png,a", "//other.test/x", "/static/../README.md", "/static/%2e%2e/README.md", "/static/a\\b", "x" * 2049)
        ] + [{"width": 0}, {"height": True}, {"chapter_id": str(ObjectId())}]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.client.post(self.url, json={**self.payload, **change}).status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_duplicate_and_oversized_without_leaking_driver_details(self):
        for error, code in ((DuplicateKeyError("secret"), 409), (DocumentTooLarge("secret"), 413)):
            self.pages.insert_one.side_effect = error
            response = self.client.post(self.url, json=self.payload)
            self.assertEqual(response.status_code, code)
            self.assertNotIn("secret", response.text)

    def test_database_errors_at_each_write_stage_are_503(self):
        for operation in (self.chapters.find_one, self.prepare_index, self.pages.insert_one):
            with self.subTest(operation=operation):
                operation.side_effect = ServerSelectionTimeoutError("secret")
                response = self.client.post(self.url, json=self.payload)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret", response.text)
                operation.side_effect = None

    def test_list_filters_chapter_and_paginates_by_number(self):
        cursor = self.make_cursor([{**self.payload, "page_number": 7, "chapter_id": str(self.chapter_id), "_id": self.page_id}])
        response = self.client.get(self.url + "?after=5&limit=2")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]["page_number"], 7)
        self.pages.find.assert_called_once_with({"chapter_id": str(self.chapter_id), "page_number": {"$gt": 5}})
        cursor.sort.assert_called_once_with("page_number", 1)
        cursor.limit.assert_called_once_with(2)

    def test_empty_pages_and_read_failure(self):
        cursor = self.make_cursor([])
        self.assertEqual(self.client.get(self.url).json(), [])
        cursor.to_list.side_effect = ServerSelectionTimeoutError("secret")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_invalid_query_or_parent_does_not_read_database(self):
        for suffix in ("?limit=101", "?limit=0", "?after=-1", f"?after={2**63}"):
            self.assertEqual(self.client.get(self.url + suffix).status_code, 422)
        self.assertEqual(self.client.get('/api/chapters/invalid/pages').status_code, 422)
        self.database.get_collection.assert_not_called()


class PageIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_index_build_and_failure_retry(self):
        state = SimpleNamespace(page_index_ready=False, page_index_lock=asyncio.Lock())
        request = SimpleNamespace(app=SimpleNamespace(state=state))
        database = MagicMock()
        create_index = AsyncMock(side_effect=[ServerSelectionTimeoutError("offline"), "index"])
        database.get_collection.return_value.create_index = create_index
        with self.assertRaises(ServerSelectionTimeoutError):
            await ensure_page_index(request, database)
        self.assertFalse(state.page_index_ready)
        await asyncio.gather(*(ensure_page_index(request, database) for _ in range(3)))
        self.assertTrue(state.page_index_ready)
        self.assertEqual(create_index.await_count, 2)
