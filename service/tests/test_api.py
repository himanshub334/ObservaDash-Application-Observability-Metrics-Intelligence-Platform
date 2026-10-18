from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_route_is_registered():
    response = client.get('/openapi.json')
    assert response.status_code == 200
    assert '/ingest' in response.json()['paths']
    assert '/metrics' in response.json()['paths']

def test_ingest_requires_at_least_one_metric():
    response = client.post('/ingest', json={'resource': {'service.name': 'demo'}, 'metrics': []})
    assert response.status_code == 422
