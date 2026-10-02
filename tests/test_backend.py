import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pymongo.errors import DocumentTooLarge, ServerSelectionTimeoutError

from backend.database import get_database
from backend.main import app
from backend.models import ChapterSchema, ComicSchema, PageDocumentSchema, PageSchema


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        self.database.command = AsyncMock(return_value={"ok": 1})
        app.dependency_overrides[get_database] = lambda: self.database
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_ping_success(self):
        response = self.client.get("/api/db-check")
        self.assertEqual(response.status_code, 200)
        self.database.command.assert_awaited_once_with("ping")

    def test_database_failure_is_503_without_connection_details(self):
        self.database.command.side_effect = ServerSelectionTimeoutError("mongodb://user:secret@host")
        response = self.client.get("/api/db-check")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)
        self.assertEqual(self.client.get("/api/status").status_code, 200)

    def test_slow_ping_is_cancelled(self):
        cancelled = []

        async def slow_ping(*args):
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)

        self.database.command.side_effect = slow_ping
        with patch("backend.main.DB_CHECK_TIMEOUT_SECONDS", 0.01):
            self.assertEqual(self.client.get("/api/db-check").status_code, 503)
        self.assertEqual(cancelled, [True])

    def test_unexpected_errors_are_not_disguised_as_database_outages(self):
        self.database.command.side_effect = RuntimeError("programming error")
        with self.assertRaises(RuntimeError):
            self.client.get("/api/db-check")

    def test_lifespan_recreates_and_closes_client(self):
        with patch("backend.database.AsyncIOMotorClient") as factory:
            for _ in range(2):
                with TestClient(app) as client:
                    self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(factory.call_count, 2)
            self.assertEqual(factory.return_value.close.call_count, 2)

    def test_lifespan_closes_client_if_setup_fails(self):
        with patch("backend.database.AsyncIOMotorClient") as factory:
            factory.return_value.__getitem__.side_effect = ValueError("invalid database")
            with self.assertRaises(ValueError):
                with TestClient(app):
                    pass
            factory.return_value.close.assert_called_once()

    def test_configuration_from_environment(self):
        with patch("backend.database.load_dotenv"), patch.dict(
            "os.environ", {"MONGO_URL": "mongodb://localhost:27018", "MONGO_DB_NAME": "test_db"}
        ), patch("backend.database.AsyncIOMotorClient") as factory:
            with TestClient(app):
                self.assertEqual(factory.call_args.args[0], "mongodb://localhost:27018")
                factory.return_value.__getitem__.assert_called_once_with("test_db")

    def test_swagger_documents_service_unavailable(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("503", schema["paths"]["/api/db-check"]["get"]["responses"])

    def test_create_comic_preserves_response_and_persists_validated_data(self):
        identifier = ObjectId()
        collection = self.database.get_collection.return_value
        collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=identifier))
        response = self.client.post("/api/comics", json={
            "title": " Obra ", "author": "Julio", "description": "Descrição",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], str(identifier))
        self.assertIn("mensagem", response.json())
        self.database.get_collection.assert_called_with("catalogs")
        collection.insert_one.assert_awaited_once_with({
            "title": "Obra", "author": "Julio", "description": "Descrição",
            "tags": [], "cover_url": None,
        })

    def test_invalid_comic_does_not_reach_database(self):
        response = self.client.post("/api/comics", json={
            "title": "  ", "author": "Julio", "description": "",
        })
        self.assertEqual(response.status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_create_failure_is_503(self):
        self.database.get_collection.return_value.insert_one = AsyncMock(
            side_effect=ServerSelectionTimeoutError("mongodb://secret@host")
        )
        response = self.client.post("/api/comics", json={
            "title": "Obra", "author": "Julio", "description": "",
        })
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_oversized_comic_returns_413_without_driver_details(self):
        self.database.get_collection.return_value.insert_one = AsyncMock(
            side_effect=DocumentTooLarge("internal document details")
        )
        response = self.client.post("/api/comics", json={
            "title": "Obra", "author": "Julio", "description": "",
        })
        self.assertEqual(response.status_code, 413)
        self.assertNotIn("internal", response.text)

    def make_cursor(self, documents):
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=documents)
        self.database.get_collection.return_value.find.return_value = cursor
        return cursor

    def test_catalog_default_keeps_list_contract_and_limit(self):
        identifier = ObjectId()
        cursor = self.make_cursor([{"_id": identifier, "title": "Obra"}])
        response = self.client.get("/api/comics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": str(identifier), "title": "Obra"}])
        cursor.limit.assert_called_once_with(100)
        cursor.to_list.assert_awaited_once_with(length=100)

    def test_catalog_cursor_filters_and_limits_the_query(self):
        after = ObjectId()
        cursor = self.make_cursor([])
        response = self.client.get(f"/api/comics?limit=2&after={after}")
        self.assertEqual(response.json(), [])
        self.database.get_collection.return_value.find.assert_called_once_with({"_id": {"$gt": after}})
        cursor.sort.assert_called_once_with("_id", 1)
        cursor.limit.assert_called_once_with(2)
        cursor.to_list.assert_awaited_once_with(length=2)

    def test_invalid_pagination_does_not_query_database(self):
        for query in ("limit=0", "limit=101", "limit=-1", "after=wrong", "after="):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(f"/api/comics?{query}").status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_catalog_database_failure_is_503(self):
        cursor = self.make_cursor([])
        cursor.to_list.side_effect = ServerSelectionTimeoutError("secret")
        response = self.client.get("/api/comics")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_get_comic_returns_requested_document_with_string_id(self):
        identifier = ObjectId()
        document = {
            "_id": identifier, "title": "Obra", "author": "Julio",
            "description": "Descrição", "tags": ["aventura"], "cover_url": None,
        }
        collection = self.database.get_collection.return_value
        collection.find_one = AsyncMock(return_value=document.copy())
        response = self.client.get(f"/api/comics/{str(identifier).upper()}")
        self.assertEqual(response.status_code, 200)
        expected = {key: value for key, value in document.items() if key != "_id"}
        expected["id"] = str(identifier)
        self.assertEqual(response.json(), expected)
        self.database.get_collection.assert_called_once_with("catalogs")
        collection.find_one.assert_awaited_once_with({"_id": identifier})

    def test_get_comic_with_invalid_id_does_not_query_database(self):
        for identifier in ("invalid", "a" * 23, "a" * 25, "z" * 24):
            with self.subTest(identifier=identifier):
                response = self.client.get(f"/api/comics/{identifier}")
                self.assertEqual(response.status_code, 422)
        self.database.get_collection.assert_not_called()

    def test_get_comic_returns_404_when_not_found(self):
        self.database.get_collection.return_value.find_one = AsyncMock(return_value=None)
        response = self.client.get(f"/api/comics/{ObjectId()}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Obra não encontrada."})

    def test_get_comic_database_failure_is_503_without_connection_details(self):
        self.database.get_collection.return_value.find_one = AsyncMock(
            side_effect=ServerSelectionTimeoutError("mongodb://user:secret@host")
        )
        response = self.client.get(f"/api/comics/{ObjectId()}")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)


class ConcurrentRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_requests_can_wait_for_database_at_the_same_time(self):
        database = MagicMock()
        both_started = asyncio.Event()
        started = 0

        async def insert_one(document):
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return MagicMock(inserted_id=ObjectId())

        database.get_collection.return_value.insert_one = insert_one
        # Usa a dependência real; só a operação de banco é simulada.
        with patch.object(app.state, "database", database, create=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                payload = {"title": "Teste", "author": "Teste", "description": ""}
                responses = await asyncio.wait_for(asyncio.gather(
                    client.post("/api/comics", json=payload),
                    client.post("/api/comics", json=payload),
                ), timeout=2)
        self.assertEqual([response.status_code for response in responses], [201, 201])
        self.assertEqual(started, 2)


class SchemaTests(unittest.TestCase):
    def chapter(self, numbers):
        return ChapterSchema(comic_id="comic-1", chapter_number=1, title="Início", initial_pages=[
            {"page_number": n, "image_url": f"/storage/{n}.webp"} for n in numbers
        ])

    def test_initial_subset_does_not_impose_a_fixed_quantity(self):
        for numbers in ([], [1], [1, 2, 3, 4], list(range(1, 11))):
            with self.subTest(numbers=numbers):
                self.assertEqual(len(self.chapter(numbers).initial_pages), len(numbers))

    def test_page_number_must_be_positive_integer(self):
        for number in (0, -1, True, 1.5, "1"):
            with self.subTest(number=number), self.assertRaises(ValidationError):
                PageSchema(page_number=number, image_url="/storage/a.webp")

    def test_references_and_titles_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            PageSchema(page_number=1, image_url="   ")
        with self.assertRaises(ValidationError):
            ComicSchema(title="  ", author="Julio", description="")
        with self.assertRaises(ValidationError):
            PageDocumentSchema(page_number=1, image_url="/a.webp", chapter_id=" ")

    def test_page_document_requires_chapter_reference(self):
        with self.assertRaises(ValidationError):
            PageDocumentSchema(page_number=1, image_url="/a.webp")
        page = PageDocumentSchema(page_number=1, image_url="/a.webp", chapter_id="chapter-1")
        self.assertEqual(page.chapter_id, "chapter-1")

    def test_creation_date_has_timezone(self):
        self.assertIsNotNone(self.chapter([]).created_at.utcoffset())
        with self.assertRaises(ValidationError):
            ChapterSchema(comic_id="c", chapter_number=1, title="t", created_at="2026-09-12T12:00:00")

    def test_extra_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            PageSchema(page_number=1, image_url="/a.webp", image_urll="typo")

    def test_lists_are_independent(self):
        first = ComicSchema(title=" A ", author=" B ", description="")
        second = ComicSchema(title="C", author="D", description="")
        first.tags.append("ação")
        self.assertEqual(second.tags, [])
        self.assertEqual(first.title, "A")


if __name__ == "__main__":
    unittest.main()
