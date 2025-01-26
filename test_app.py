import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_root(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.json == {'msg':'Homepage for Habit Tracker', 'data': {}}

# def test_signup(client):
#     request_data = {
#         "username": "test_username12",
#         "password": "test_password"
#     }

#     response = client.post('/api/auth/signup', json=request_data)

#     assert response.status_code == 201

#     response_json = response.get_json()
#     print(response_json)

#     assert response.json['msg'] == 'signup successful'
#     assert response.json['data']['username'] == 'test_username12'