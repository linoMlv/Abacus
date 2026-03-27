import sys
import uuid
from decimal import Decimal
from datetime import datetime
from sqlmodel import Session, select, create_engine
from models import Operation, OperationType, Association
from database import engine

def test():
    with Session(engine) as session:
        op = Operation(
            name="test",
            description="test",
            group="test",
            amount=Decimal(10),
            type=OperationType.EXPENSE,
            date=datetime.now(),
            invoice="http://test.com/invoice1.pdf"
        )
        session.add(op)
        session.commit()
        session.refresh(op)
        print("Created:", op.invoice)
        
        op.invoice = "http://test.com/invoice2.pdf"
        session.add(op)
        session.commit()
        session.refresh(op)
        print("Updated:", op.invoice)

        # Cleanup
        session.delete(op)
        session.commit()

test()
