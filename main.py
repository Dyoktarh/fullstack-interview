from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

app = FastAPI()


# Conexão com o banco SQLite
DATABASE_URL = "sqlite:///./products.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()


# Modelo da tabela no banco
class ProductDB(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    preco = Column(Float)


# Cria a tabela caso ela ainda não exista
Base.metadata.create_all(bind=engine)


# Modelo usado para receber os dados da API
class Product(BaseModel):
    nome: str
    preco: float = Field(gt=0)


@app.get("/")
def home():
    return {"mensagem": "API funcionando!"}



@app.post("/products", status_code=201)
def create_product(
    product: Product,
    db=Depends(get_db)
):
    novo_produto = ProductDB(
        nome=product.nome,
        preco=product.preco
    )

    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)

    return {
        "id": novo_produto.id,
        "nome": novo_produto.nome,
        "preco": novo_produto.preco
    }

@app.get("/products")
def list_products(db=Depends(get_db)):
    return db.query(ProductDB).all()



@app.get("/products/stats")
def get_product_stats(db=Depends(get_db)):
    products = db.query(ProductDB).all()

    total_produtos = len(products)
    valor_total = sum(product.preco for product in products)

    preco_medio = (
        valor_total / total_produtos
        if total_produtos > 0
        else 0
    )

    return {
        "total_produtos": total_produtos,
        "valor_total": round(valor_total, 2),
        "preco_medio": round(preco_medio, 2)
    }


@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    db=Depends(get_db)
):
    produto = db.query(ProductDB).filter(
        ProductDB.id == product_id
    ).first()

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    product: Product,
    db=Depends(get_db)
):
    produto = db.query(ProductDB).filter(
        ProductDB.id == product_id
    ).first()

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    produto.nome = product.nome
    produto.preco = product.preco

    db.commit()
    db.refresh(produto)

    return {
        "id": produto.id,
        "nome": produto.nome,
        "preco": produto.preco
    }


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db=Depends(get_db)
):
    produto = db.query(ProductDB).filter(
        ProductDB.id == product_id
    ).first()

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    db.delete(produto)
    db.commit()

    return {
        "message": "Produto excluído com sucesso"
    }