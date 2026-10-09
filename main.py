from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from pwdlib import PasswordHash
import jwt
from datetime import datetime, timedelta, timezone

app = FastAPI()
password_hash = PasswordHash.recommended()

SECRET_KEY = "chave-local-de-desenvolvimento-altere-depois"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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


class UserCreate(BaseModel):
    username: str
    password: str

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

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


@app.post("/users", status_code=201)
def create_user(
    user: UserCreate,
    db=Depends(get_db)
):
    existing_user = db.query(UserDB).filter(
        UserDB.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Nome de usuário já cadastrado"
        )

    hashed_password = password_hash.hash(user.password)

    new_user = UserDB(
        username=user.username,
        hashed_password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username
    }


@app.post("/login")
def login(
    user: UserCreate,
    db=Depends(get_db)
):
    existing_user = db.query(UserDB).filter(
        UserDB.username == user.username
    ).first()

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos"
        )

    password_is_valid = password_hash.verify(
        user.password,
        existing_user.hashed_password
    )

    if not password_is_valid:
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos"
        )

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    token = jwt.encode(
        {
            "sub": existing_user.username,
            "exp": expire
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


def get_current_user(
    authorization: str | None = Header(default=None),
    db=Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token de autenticação ausente ou inválido"
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=401,
                detail="Token inválido"
            )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado"
        )

    current_user = db.query(UserDB).filter(
        UserDB.username == username
    ).first()

    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado"
        )

    return current_user


@app.get("/me")
def read_current_user(
    current_user: UserDB = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "username": current_user.username
    }