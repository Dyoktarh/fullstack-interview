
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, Base, get_db


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_create_product():
    response = client.post(
        "/products",
        json={"nome": "Produto de teste", "preco": 100.0},
    )

    assert response.status_code == 201
    assert response.json()["nome"] == "Produto de teste"
    assert response.json()["preco"] == 100.0
    assert "id" in response.json()


def test_create_product_with_negative_price():
    response = client.post(
        "/products",
        json={"nome": "Produto inválido", "preco": -10.0},
    )

    assert response.status_code == 422



def test_product_stats():
    # Cadastra dois produtos para testar os cálculos
    client.post(
        "/products",
        json={"nome": "Teclado", "preco": 100.0},
    )

    client.post(
        "/products",
        json={"nome": "Mouse", "preco": 50.0},
    )

    # Consulta as estatísticas
    response = client.get("/products/stats")

    assert response.status_code == 200

    data = response.json()

    # Confere os valores calculados
    assert data["total_produtos"] == 2
    assert data["valor_total"] == 150.0
    assert data["preco_medio"] == 75.0

    
def test_update_product():
    # Cria um produto
    create_response = client.post(
        "/products",
        json={"nome": "Teclado", "preco": 100.0},
    )

    product_id = create_response.json()["id"]

    # Atualiza o produto
    response = client.put(
        f"/products/{product_id}",
        json={"nome": "Teclado Mecânico", "preco": 250.0},
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Teclado Mecânico"
    assert response.json()["preco"] == 250.0


def test_delete_product():
    # Cria um produto
    create_response = client.post(
        "/products",
        json={"nome": "Mouse", "preco": 50.0},
    )

    product_id = create_response.json()["id"]

    # Exclui o produto
    response = client.delete(f"/products/{product_id}")

    assert response.status_code == 200

    # Confirma que o produto não existe mais
    get_response = client.get(f"/products/{product_id}")

    assert get_response.status_code == 404

    
def test_update_nonexistent_product():
    response = client.put(
        "/products/999999",
        json={"nome": "Produto inexistente", "preco": 100.0},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Produto não encontrado"


def test_delete_nonexistent_product():
    response = client.delete("/products/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Produto não encontrado"