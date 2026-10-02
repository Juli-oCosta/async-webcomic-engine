"""Teste opt-in do fluxo HTTP com MongoDB local, em banco temporário isolado."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from backend.main import app


@unittest.skipUnless(os.getenv("RUN_MONGO_TESTS") == "1", "Defina RUN_MONGO_TESTS=1 para MongoDB real")
class MongoIntegrationTests(unittest.TestCase):
    def test_create_and_paginate_more_than_one_hundred_comics(self):
        database_name = "tgi_validation_" + uuid4().hex
        uri = "mongodb://localhost:27017"
        with MongoClient(uri, serverSelectionTimeoutMS=5000) as cleanup_client:
            cleanup_client.admin.command("ping")
            self.assertNotIn(database_name, cleanup_client.list_database_names())
            try:
                with patch.dict(os.environ, {"MONGO_URL": uri, "MONGO_DB_NAME": database_name}):
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/api/db-check").status_code, 200)
                        self.assertEqual(client.get("/api/comics").json(), [])
                        created_ids = []
                        for index in range(105):
                            response = client.post("/api/comics", json={
                                "title": f"Obra de teste {index}",
                                "author": "Teste de integração", "description": "Dado temporário",
                            })
                            self.assertEqual(response.status_code, 201, response.text)
                            created_ids.append(response.json()["id"])
                        response = client.get("/api/comics")
                        self.assertEqual(response.status_code, 200)
                        first = response.json()
                        self.assertEqual(len(first), 100)
                        details = client.get(f"/api/comics/{first[0]['id']}")
                        self.assertEqual(details.status_code, 200)
                        self.assertEqual(details.json(), first[0])
                        self.assertEqual(client.get(f"/api/comics/{ObjectId()}").status_code, 404)
                        self.assertEqual(client.get("/api/comics/invalid").status_code, 422)
                        response = client.get("/api/comics", params={"after": first[-1]["id"]})
                        self.assertEqual(response.status_code, 200)
                        second = response.json()
                        self.assertEqual(len(second), 5)
                        read_ids = [comic["id"] for comic in first + second]
                        self.assertEqual(read_ids, sorted(created_ids))
                        self.assertEqual(len(set(read_ids)), 105)
                        self.assertEqual(client.get("/api/comics", params={"after": second[-1]["id"]}).json(), [])
                        self.assertEqual(client.get("/api/comics?limit=101").status_code, 422)
                        self.assertEqual(client.post("/api/comics", json={
                            "title": " ", "author": "Teste", "description": "",
                        }).status_code, 422)
                        self.assertEqual(cleanup_client[database_name].catalogs.count_documents({}), 105)
                        oversized = client.post("/api/comics", json={
                            "title": "Documento grande", "author": "Teste",
                            "description": "x" * (17 * 1024 * 1024),
                        })
                        self.assertEqual(oversized.status_code, 413, oversized.text)
                        self.assertEqual(cleanup_client[database_name].catalogs.count_documents({}), 105)
            finally:
                # Nome gerado neste teste, nunca recebido de configuração externa.
                cleanup_client.drop_database(database_name)
                self.assertNotIn(database_name, cleanup_client.list_database_names())
