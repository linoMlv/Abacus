from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
import os
import bcrypt

from database import get_session
from models import Association, Balance, Operation, OperationType, AssociationRead, BalanceRead


SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app = FastAPI()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password using bcrypt."""
    # Convert plain password to bytes and truncate to 72 bytes (bcrypt's limit)
    password_bytes = plain_password.encode('utf-8')[:72]
    # Convert hashed password to bytes
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    # Truncate to 72 bytes to comply with bcrypt's limit
    password_bytes = password.encode('utf-8')[:72]
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_association(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        name: str = payload.get("sub")
        if name is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    statement = select(Association).where(Association.name == name)
    association = session.exec(statement).first()
    if association is None:
        raise credentials_exception
    return association

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:9873",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pydantic import BaseModel

class BalanceCreate(BaseModel):
    name: str
    amount: str

class SignupRequest(BaseModel):
    name: str
    password: str
    balances: List[BalanceCreate]

class LoginRequest(BaseModel):
    name: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    association: AssociationRead

class OperationCreate(BaseModel):
    name: str
    description: str
    group: str
    amount: float
    type: OperationType
    date: datetime
    balance_id: str
    invoice: str | None = None

def association_to_read(association: Association) -> AssociationRead:
    all_operations = []
    balance_reads = []
    for balance in association.balances:
        ops = balance.operations
        all_operations.extend(ops)
        balance_reads.append(BalanceRead(
            id=balance.id,
            name=balance.name,
            initialAmount=balance.initialAmount,
            position=balance.position,
            operations=ops
        ))
    
    return AssociationRead(
        id=association.id,
        name=association.name,
        balances=balance_reads,
        operations=all_operations
    )

@app.post("/api/signup", response_model=AssociationRead)
def signup(request: SignupRequest, session: Session = Depends(get_session)):
    statement = select(Association).where(Association.name == request.name)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="Association already exists")
    
    hashed_password = get_password_hash(request.password)
    association = Association(name=request.name, password=hashed_password)
    session.add(association)
    session.commit()
    session.refresh(association)
    
    for b in request.balances:
        balance = Balance(
            name=b.name,
            initialAmount=float(b.amount),
            association_id=association.id,
            position=0
        )
        session.add(balance)
    
    session.commit()
    session.refresh(association)
    return association_to_read(association)

@app.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    statement = select(Association).where(Association.name == request.name)
    association = session.exec(statement).first()
    if not association or not verify_password(request.password, association.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": association.name}, expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        association=association_to_read(association)
    )

@app.get("/api/associations/{association_id}", response_model=AssociationRead)
def get_association(
    association_id: str, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    if current_association.id != association_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this association")

    from sqlalchemy.orm import selectinload
    statement = select(Association).where(Association.id == association_id).options(
        selectinload(Association.balances).selectinload(Balance.operations)
    )
    association = session.exec(statement).first()
    
    if not association:
        raise HTTPException(status_code=404, detail="Association not found")
    
    return association_to_read(association)

@app.post("/api/operations")
def create_operation(
    op: OperationCreate, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    balance = session.get(Balance, op.balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    if balance.association_id != current_association.id:
         raise HTTPException(status_code=403, detail="Not authorized to add operation to this balance")

    operation = Operation(
        name=op.name,
        description=op.description,
        group=op.group,
        amount=op.amount,
        type=op.type,
        date=op.date,
        balance_id=op.balance_id,
        invoice=op.invoice
    )
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return operation

@app.delete("/api/operations/{operation_id}")
def delete_operation(
    operation_id: str, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    operation = session.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    # Ensure operation's balance belongs to current association
    # We might need to fetch the balance first or rely on lazy loading if configured, 
    # but `session.get` returns the object. `operation.balance` might not be loaded.
    # Let's perform a query to be safe or check the balance_id.
    balance = session.get(Balance, operation.balance_id)
    if not balance or balance.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this operation")

    session.delete(operation)
    session.commit()
    return {"ok": True}

class OperationUpdate(BaseModel):
    name: str
    description: str
    group: str
    amount: float
    type: OperationType
    date: datetime
    balance_id: str
    invoice: str | None = None

@app.put("/api/operations/{operation_id}")
def update_operation(
    operation_id: str, 
    op: OperationUpdate, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    operation = session.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    balance = session.get(Balance, operation.balance_id)
    if not balance or balance.association_id != current_association.id:
         raise HTTPException(status_code=403, detail="Not authorized to update this operation")
    
    # Also if changing balance_id, verify new balance is owned by user
    if op.balance_id != operation.balance_id:
        new_balance = session.get(Balance, op.balance_id)
        if not new_balance or new_balance.association_id != current_association.id:
            raise HTTPException(status_code=403, detail="Not authorized to move to this balance")

    operation.name = op.name
    operation.description = op.description
    operation.group = op.group
    operation.amount = op.amount
    operation.type = op.type
    operation.date = op.date
    operation.balance_id = op.balance_id
    operation.invoice = op.invoice
    
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return operation

@app.post("/api/balances")
def create_balance(balance: BalanceCreate, association_id: str, session: Session = Depends(get_session)):
    pass

class BalanceAddRequest(BaseModel):
    name: str
    initialAmount: float
    association_id: str

@app.post("/api/balances_add")
def add_balance(
    request: BalanceAddRequest, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    if request.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to add balance to this association")

    statement = select(Balance).where(Balance.association_id == request.association_id).order_by(Balance.position.desc())
    last_balance = session.exec(statement).first()
    new_position = (last_balance.position + 1) if last_balance else 0

    balance = Balance(
        name=request.name,
        initialAmount=request.initialAmount,
        association_id=request.association_id,
        position=new_position
    )
    session.add(balance)
    session.commit()
    session.refresh(balance)
    return balance

@app.delete("/api/balances/{balance_id}")
def delete_balance(
    balance_id: str, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    balance = session.get(Balance, balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    if balance.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this balance")
    
    session.delete(balance)
    session.commit()
    return {"ok": True}

class BalanceUpdate(BaseModel):
    name: str
    initialAmount: float
    position: int

@app.put("/api/balances/{balance_id}")
def update_balance(
    balance_id: str, 
    data: BalanceUpdate, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    balance = session.get(Balance, balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    if balance.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this balance")
    
    balance.name = data.name
    balance.initialAmount = data.initialAmount
    balance.position = data.position
    
    session.add(balance)
    session.commit()
    session.refresh(balance)
    return balance

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok"}
