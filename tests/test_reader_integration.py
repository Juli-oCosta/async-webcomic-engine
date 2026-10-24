"""Fluxo de leitura com banco temporário e contratos estáticos do leitor."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from backend.main import app
from scripts.seed_database import seed_demo


class ReaderStaticTests(unittest.TestCase):
    def test_reader_and_assets_preserve_api_root(self):
        with TestClient(app) as client:
            self.assertIn("mensagem", client.get('/').json())
            response = client.get('/reader')
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/html', response.headers['content-type'])
            self.assertIn('id="chapters"', response.text)
            for path in ('/static/css/style.css', '/static/js/observer.js'):
                self.assertEqual(client.get(path).status_code, 200)

    def test_static_root_does_not_expose_repository_or_arbitrary_files(self):
        with TestClient(app) as client:
            for path in ('/static/%2e%2e/README.md', '/static/%2e%2e/.env', '/static/%2e%2e/backend/main.py', '/static/.env', '/static/C:/Windows/win.ini'):
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 404)


class DemoSeedSafetyTests(unittest.TestCase):
    def test_permanent_database_names_are_rejected_before_connection(self):
        with patch('scripts.seed_database.MongoClient') as factory:
            for name in ('webcomics_db', 'admin', 'tgi_demo_', 'tgi_demo_../x'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    seed_demo(name)
            factory.assert_not_called()

    def test_existing_unmarked_database_is_never_overwritten(self):
        database = MagicMock()
        database.list_collection_names.return_value = ['catalogs']
        database.demo_metadata.find_one.return_value = None
        with patch('scripts.seed_database.MongoClient') as factory, patch('scripts.seed_database.generate_assets') as generate:
            factory.return_value.__enter__.return_value.__getitem__.return_value = database
            with self.assertRaises(ValueError):
                seed_demo('tgi_demo_existing')
            database.demo_metadata.update_one.assert_not_called()
            database.catalogs.replace_one.assert_not_called()
            generate.assert_not_called()


@unittest.skipUnless(os.getenv('RUN_MONGO_TESTS') == '1', 'Defina RUN_MONGO_TESTS=1 para MongoDB real')
class ReaderMongoTests(unittest.TestCase):
    def test_complete_reading_order_isolation_and_concurrent_page_duplicate(self):
        name = 'tgi_validation_' + uuid4().hex
        uri = 'mongodb://localhost:27017'
        with MongoClient(uri, serverSelectionTimeoutMS=3000) as mongo:
            mongo.admin.command('ping')
            self.assertNotIn(name, mongo.list_database_names())
            try:
                with patch.dict(os.environ, {'MONGO_URL': uri, 'MONGO_DB_NAME': name}), TestClient(app) as client:
                    comics = [client.post('/api/comics', json={'title': title, 'author': 'Teste', 'description': ''}).json()['id'] for title in ('A', 'B')]
                    chapters = {}
                    for number in (5, 1, 3):
                        response = client.post(f'/api/comics/{comics[0]}/chapters', json={'chapter_number': number, 'title': str(number)})
                        self.assertEqual(response.status_code, 201, response.text)
                        chapters[number] = response.json()['id']
                    other = client.post(f'/api/comics/{comics[1]}/chapters', json={'chapter_number': 1, 'title': 'Outra obra'}).json()['id']
                    first = client.get(f'/api/comics/{comics[0]}/chapters?limit=2').json()
                    second = client.get(f'/api/comics/{comics[0]}/chapters?limit=2&after=3').json()
                    self.assertEqual([item['chapter_number'] for item in first + second], [1, 3, 5])
                    self.assertEqual(len({item['id'] for item in first + second}), 3)
                    self.assertEqual(client.get(f'/api/chapters/{chapters[3]}/pages').json(), [])
                    payload = {'page_number': 1, 'image_url': '/static/demo/page-01.svg', 'width': 900, 'height': 1200}
                    barrier = Barrier(2)
                    def create_same_page():
                        barrier.wait(timeout=5)
                        return client.post(f'/api/chapters/{chapters[1]}/pages', json=payload)
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        responses = list(executor.map(lambda _: create_same_page(), range(2)))
                    self.assertEqual(sorted(item.status_code for item in responses), [201, 409])
                    for number in (4, 2, 3):
                        self.assertEqual(client.post(f'/api/chapters/{chapters[1]}/pages', json={**payload, 'page_number': number}).status_code, 201)
                    self.assertEqual(client.post(f'/api/chapters/{other}/pages', json=payload).status_code, 201)
                    one = client.get(f'/api/chapters/{chapters[1]}/pages?limit=2').json()
                    two = client.get(f'/api/chapters/{chapters[1]}/pages?limit=2&after=2').json()
                    self.assertEqual([item['page_number'] for item in one + two], [1, 2, 3, 4])
                    self.assertTrue(all(item['chapter_id'] == chapters[1] for item in one + two))
                    self.assertEqual(client.get(f'/api/chapters/{chapters[1]}/pages?after=4').json(), [])
                    self.assertEqual(client.get(f'/api/chapters/{ObjectId()}/pages').status_code, 404)
                    self.assertEqual(client.get('/api/chapters/invalid/pages').status_code, 422)
                    self.assertEqual(client.get(f'/api/comics/{ObjectId()}/chapters').status_code, 404)
                    self.assertEqual(client.get(f'/api/chapters/{chapters[1]}/pages?limit=101').status_code, 422)
                    index = mongo[name].pages.index_information()['chapter_page_number_unique']
                    self.assertTrue(index['unique'])
                    self.assertEqual(mongo[name].pages.count_documents({}), 5)
                    self.assertEqual(mongo[name].chapters.find_one({'_id': ObjectId(chapters[1])})['initial_pages'], [])
            finally:
                mongo.drop_database(name)
                self.assertNotIn(name, mongo.list_database_names())
