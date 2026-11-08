import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
import backend
from core.forecast_ledger import ingest_actuals as real_ingest
from core.workspace_store import init_db,connect


class FeedAPITests(unittest.TestCase):
 def tearDown(self):backend.app.dependency_overrides.clear()
 def test_agent_cannot_read_ledger_or_feed_actuals(self):
  backend.app.dependency_overrides[backend._auth_required]=lambda:{'position':'agent'}
  with TestClient(backend.app) as client:
   self.assertEqual(client.get('/forecast-ledger/runs').status_code,403)
   self.assertEqual(client.post('/actuals/intervals',json={'rows':[]}).status_code,403)
 def test_authenticated_actual_feed_and_bad_input(self):
  backend.app.dependency_overrides[backend._auth_required]=lambda:{'position':'wfm'}
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'db';init_db(path)
   with patch('core.forecast_ledger.ingest_actuals',side_effect=lambda raw:real_ingest(raw,path)):
    with TestClient(backend.app) as client:
     response=client.post('/actuals/intervals',json={'rows':[{'tarih':'2026-11-02','slot':17,'cagri_sayisi':25}]})
     self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['updated'],1)
     self.assertEqual(client.post('/actuals/intervals',json={'rows':[{'tarih':'bad','slot':60,'cagri_sayisi':-1}]}).status_code,400)
   with connect(path) as db:self.assertEqual(db.execute('SELECT cagri_sayisi FROM calls_interval').fetchone()[0],25)

if __name__=='__main__':unittest.main()
