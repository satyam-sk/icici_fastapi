# app.py - Modified to use request bodies instead of query parameters
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager

app = FastAPI(title="Banking API", description="APIs for LangGraph banking agent")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
# DB_CONFIG = {
#     'host': 'db-identifier.crp0.us-west-2.rds.amazonaws.com',
#     'port': 5432,
#     'database': 'database',
#     'user': 'test',
#     'password': 'testtest',
#     'sslmode': 'verify-full',
#     'sslrootcert': './global-bundle.pem'
# }

# Helper functions to convert tuples to dictionaries
def dict_fetch_all(cursor):
    """Return all rows from a cursor as a list of dictionaries"""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dict_fetch_one(cursor):
    """Return one row from a cursor as a dictionary"""
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    if row:
        return dict(zip(columns, row))
    return None

# Pydantic models
class Customer(BaseModel):
    cust_id: int
    name: str
    mobile: str
    last4digit: str
    email: str

class Account(BaseModel):
    acc_id: int
    cust_id: int
    acc_number: str
    acc_type: str
    acc_balance: float
    acc_branch: str

class Card(BaseModel):
    card_id: int
    cust_id: int
    card_num: str
    card_last4: str
    card_status: str
    card_limit: float
    available_limit: float
    card_type: Optional[str] = None

class Transaction(BaseModel):
    transaction_id: int
    cust_id: int
    transaction_type: str
    amount: float
    merchant_name: Optional[str]
    transaction_timestamp: datetime
    status: str
    card_last4: Optional[str]
    reference_id: Optional[str]
    remarks: Optional[str]

# Request/Response models
class CustomerByLast4Request(BaseModel):
    last4_digit: str = Field(..., min_length=4, max_length=4, pattern="^[0-9]{4}$")

class CustomerByLast4Response(BaseModel):
    customers: List[Customer]

class CustomerByIdRequest(BaseModel):
    customer_id: int

class CardBlockRequest(BaseModel):
    customer_id: int
    card_last4: str = Field(..., min_length=4, max_length=4, pattern="^[0-9]{4}$")

class CardBlockResponse(BaseModel):
    message: str
    card_status: str
    card_last4: str

class TransactionsRequest(BaseModel):
    customer_id: int
    limit: int = Field(10, ge=1, le=100)

# Database connection manager
@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
        host='icici-db-identifier.crppdyphkva0.us-west-2.rds.amazonaws.com',
        port=5432,
        database='icici_database',
        user='test',
        password='testtest123',
        sslmode='verify-full',
    sslrootcert='./global-bundle.pem'
    )
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# API Endpoints

@app.get("/")
def root():
    return {"message": "Banking API is running", "version": "1.0.0"}

# API A: Fetch customer based on last 4 digits of mobile (POST with body)
@app.post("/api/customers/by-mobile-last4", response_model=CustomerByLast4Response)
async def get_customers_by_mobile_last4(request: CustomerByLast4Request):
    """
    Fetch customers based on last 4 digits of mobile number
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cust_id, name, mobile, last4digit, email
                    FROM customers
                    WHERE last4digit = %s
                    ORDER BY cust_id
                """, (request.last4_digit,))
                
                customers = dict_fetch_all(cur)
                
                if not customers:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No customers found with mobile last 4 digits: {request.last4_digit}"
                    )
                
                return CustomerByLast4Response(customers=customers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# API B: Fetch card details based on customer id (POST with body)
@app.post("/api/customers/cards", response_model=List[Card])
async def get_customer_cards(request: CustomerByIdRequest):
    """
    Fetch all cards for a specific customer
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if customer exists
                cur.execute("SELECT cust_id FROM customers WHERE cust_id = %s", (request.customer_id,))
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Customer with ID {request.customer_id} not found"
                    )
                
                # Fetch cards
                cur.execute("""
                    SELECT card_id, cust_id, card_num, card_last4, 
                           card_status, card_limit, available_limit
                    FROM cards
                    WHERE cust_id = %s
                    ORDER BY card_id
                """, (request.customer_id,))
                
                cards = dict_fetch_all(cur)
                
                if not cards:
                    return []
                
                return cards
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# API C: Fetch account details based on customer id (POST with body)
@app.post("/api/customers/accounts", response_model=List[Account])
async def get_customer_accounts(request: CustomerByIdRequest):
    """
    Fetch all accounts for a specific customer
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if customer exists
                cur.execute("SELECT cust_id FROM customers WHERE cust_id = %s", (request.customer_id,))
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Customer with ID {request.customer_id} not found"
                    )
                
                # Fetch accounts
                cur.execute("""
                    SELECT acc_id, cust_id, acc_number, acc_type, 
                           acc_balance, acc_branch
                    FROM accounts
                    WHERE cust_id = %s
                    ORDER BY acc_id
                """, (request.customer_id,))
                
                accounts = dict_fetch_all(cur)
                
                if not accounts:
                    return []
                
                return accounts
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# API D: Fetch last N transactions based on customer id (POST with body - already POST)
@app.post("/api/customers/transactions/recent", response_model=List[Transaction])
async def get_recent_transactions(request: TransactionsRequest):
    """
    Fetch last N transactions for a customer, ordered by timestamp descending
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if customer exists
                cur.execute("SELECT cust_id FROM customers WHERE cust_id = %s", (request.customer_id,))
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Customer with ID {request.customer_id} not found"
                    )
                
                # Fetch recent transactions
                cur.execute("""
                    SELECT transaction_id, cust_id, transaction_type, amount, 
                           merchant_name, transaction_timestamp, status, 
                           card_last4, reference_id, remarks
                    FROM transactions
                    WHERE cust_id = %s
                    ORDER BY transaction_timestamp DESC
                    LIMIT %s
                """, (request.customer_id, request.limit))
                
                transactions = dict_fetch_all(cur)
                
                return transactions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# API E: Block a credit card based on customer id and last 4 digits (already POST)
@app.post("/api/cards/block", response_model=CardBlockResponse)
async def block_credit_card(request: CardBlockRequest):
    """
    Block a specific credit card based on customer ID and last 4 digits
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if card exists and belongs to customer
                cur.execute("""
                    SELECT card_id, card_last4, card_status
                    FROM cards
                    WHERE cust_id = %s AND card_last4 = %s
                """, (request.customer_id, request.card_last4))
                
                card = dict_fetch_one(cur)
                
                if not card:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No card found with last 4 digits {request.card_last4} for customer {request.customer_id}"
                    )
                
                # Check if card is already blocked
                if card['card_status'].lower() == 'blocked':
                    return CardBlockResponse(
                        message=f"Card ending in {request.card_last4} is already blocked",
                        card_status=card['card_status'],
                        card_last4=card['card_last4']
                    )
                
                # Update card status to Blocked
                cur.execute("""
                    UPDATE cards
                    SET card_status = 'Blocked'
                    WHERE cust_id = %s AND card_last4 = %s
                    RETURNING card_status, card_last4
                """, (request.customer_id, request.card_last4))
                
                updated_card = dict_fetch_one(cur)
                
                # Log the block action in transactions table
                try:
                    cur.execute("""
                        INSERT INTO transactions (
                            cust_id, transaction_type, amount, merchant_name, 
                            status, card_last4, remarks
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        request.customer_id,
                        'Card_Block',
                        0.00,
                        'Banking System',
                        'Completed',
                        request.card_last4,
                        f'Card blocked by customer request at {datetime.now()}'
                    ))
                except Exception as log_error:
                    # Don't fail the card blocking if logging fails
                    print(f"Warning: Could not log transaction: {log_error}")
                
                return CardBlockResponse(
                    message=f"Card ending in {request.card_last4} has been successfully blocked",
                    card_status=updated_card['card_status'],
                    card_last4=updated_card['card_last4']
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# Additional utility endpoint to get customer by ID (POST with body)
@app.post("/api/customers/get-by-id", response_model=Customer)
async def get_customer_by_id(request: CustomerByIdRequest):
    """
    Get customer details by customer ID
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cust_id, name, mobile, last4digit, email
                    FROM customers
                    WHERE cust_id = %s
                """, (request.customer_id,))
                
                customer = dict_fetch_one(cur)
                
                if not customer:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Customer with ID {request.customer_id} not found"
                    )
                
                return customer
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
