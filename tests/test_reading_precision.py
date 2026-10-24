from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient

from backend.database import get_database
from backend.main import app
from backend.models import ChapterSummarySchema, PageResponseSchema

BOUNDARIES = (2**53 - 1, 2**53, 2**53 + 1, 2**53 + 2, 2**53 + 3, 2**63 - 3, 2**63 - 2, 2**63 - 1)


class ReadingPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.parent_id = ObjectId()
        self.child_id = ObjectId()
        self.collection = MagicMock()
        self.collection.find_one = AsyncMock(return_value={'_id': self.parent_id})
        self.collection.insert_one = AsyncMock(return_value=SimpleNamespace(inserted_id=self.child_id))
        self.cursor = MagicMock()
        self.cursor.sort.return_value = self.cursor
        self.cursor.limit.return_value = self.cursor
        self.cursor.to_list = AsyncMock(return_value=[])
        self.collection.find.return_value = self.cursor
        self.database = MagicMock()
        self.database.get_collection.return_value = self.collection
        app.dependency_overrides[get_database] = lambda: self.database
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_computed_fields_keep_exact_digits_and_numeric_compatibility(self):
        for number in BOUNDARIES:
            with self.subTest(number=number):
                chapter = ChapterSummarySchema(id=str(self.child_id), comic_id=str(self.parent_id),
                    chapter_number=number, title='Fronteira', created_at=datetime.now(timezone.utc)).model_dump(mode='json')
                page = PageResponseSchema(id=str(self.child_id), chapter_id=str(self.parent_id),
                    page_number=number, image_url='/static/demo/page-01.svg', width=900, height=1200).model_dump(mode='json')
                self.assertEqual(chapter['chapter_number'], number)
                self.assertEqual(chapter['chapter_number_text'], str(number))
                self.assertEqual(page['page_number'], number)
                self.assertEqual(page['page_number_text'], str(number))

    def test_reading_responses_and_numeric_query_keep_int64_exact(self):
        for number in BOUNDARIES:
            for kind, route, field, extra in (
                ('chapters', f'/api/comics/{self.parent_id}/chapters', 'chapter_number',
                 {'comic_id':str(self.parent_id),'title':'Fronteira','created_at':datetime.now(timezone.utc)}),
                ('pages', f'/api/chapters/{self.parent_id}/pages', 'page_number',
                 {'chapter_id':str(self.parent_id),'image_url':'/static/demo/page-01.svg','width':900,'height':1200}),
            ):
                with self.subTest(kind=kind,number=number):
                    self.cursor.to_list.return_value = [{'_id':self.child_id,field:number,**extra}]
                    response = self.client.get(route + f'?after={number-1}&limit=2')
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()[0][field+'_text'],str(number))
                    self.assertEqual(response.json()[0][field],number)
                    self.assertEqual(self.collection.find.call_args.args[0][field],{'$gt':number-1})
        for route in (f'/api/comics/{self.parent_id}/chapters',f'/api/chapters/{self.parent_id}/pages'):
            self.cursor.to_list.return_value = []
            self.assertEqual(self.client.get(route+f'?after={2**63-1}').status_code,200)
            self.assertEqual(self.client.get(route+f'?after={2**63}').status_code,422)

    def test_legacy_chapter_post_contract_still_accepts_all_int64_boundaries(self):
        with patch('backend.main.ensure_chapter_index',new_callable=AsyncMock):
            for number in BOUNDARIES:
                with self.subTest(number=number):
                    response = self.client.post(f'/api/comics/{self.parent_id}/chapters',json={'chapter_number':number,'title':'Fronteira'})
                    self.assertEqual(response.status_code,201,response.text)
                    self.assertEqual(response.json()['chapter_number'],number)
                    self.assertNotIn('chapter_number_text',response.json())
                    self.assertEqual(self.collection.insert_one.call_args.args[0]['chapter_number'],number)

    def test_page_post_retains_numeric_field_and_adds_exact_text(self):
        with patch('backend.reading.ensure_page_index',new_callable=AsyncMock):
            for number in BOUNDARIES:
                with self.subTest(number=number):
                    response=self.client.post(f'/api/chapters/{self.parent_id}/pages',json={
                        'page_number':number,'image_url':'/static/demo/page-01.svg','width':900,'height':1200})
                    self.assertEqual(response.status_code,201,response.text)
                    self.assertEqual(response.json()['page_number'],number)
                    self.assertEqual(response.json()['page_number_text'],str(number))
