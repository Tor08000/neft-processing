from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient


def test_multipart_upload_smoke() -> None:
    app = FastAPI()

    @app.post('/_multipart-smoke')
    async def multipart_smoke(file: UploadFile = File(...)) -> dict[str, str]:
        return {'filename': file.filename or ''}

    client = TestClient(app)
    response = client.post(
        '/_multipart-smoke',
        files={'file': ('prices.csv', b'product_code,price\nA95,56.7\n', 'text/csv')},
    )

    assert response.status_code == 200
    assert response.json() == {'filename': 'prices.csv'}
