# DBMS Transaction Manager Simulator

A from-scratch DBMS transaction management simulator that demonstrates how database systems handle concurrency, isolation, deadlocks, recovery, and transaction scheduling.

## Overview

This project simulates core database transaction-management concepts using a Python backend and an interactive React frontend.

It provides a visual environment for experimenting with:

- Transaction execution
- Two-Phase Locking (2PL)
- Deadlock detection and recovery
- Wait-For Graphs
- Transaction rollback
- Write-Ahead Logging (WAL)
- Crash recovery
- Isolation-level anomalies
- Serializability checking
- MVCC time-travel
- Concurrency-control protocols
- Transaction benchmarks

The system is built from first principles using an in-memory storage engine, real threads, and an on-disk WAL rather than relying on an external database engine.

## Features

### Live Control Room
Execute concurrent transactions and observe their behavior in real time.

### Concurrency Control
Experiment with transaction scheduling and concurrency-control protocols including:

- Strict Two-Phase Locking
- MVCC
- Optimistic Concurrency Control
- Timestamp Ordering

### Deadlock Detection

The simulator uses a Wait-For Graph to detect cyclic dependencies between transactions.

It demonstrates:

1. Transaction blocking
2. Cycle detection
3. Victim selection
4. Transaction abort
5. Rollback
6. Lock cleanup
7. Transaction retry

### Isolation Lab

Experiment with common transaction anomalies:

- Dirty Read
- Non-Repeatable Read
- Lost Update
- Phantom Read

and observe how different isolation levels affect them:

- Read Uncommitted
- Read Committed
- Repeatable Read
- Serializable

### Serializability Checker

Analyze transaction histories and determine whether their execution is conflict-serializable.

### MVCC Time-Travel

Inspect multiple versions of data and observe how MVCC allows transactions to work with consistent historical snapshots.

### Write-Ahead Logging & Recovery

Transactions generate WAL records that can be flushed to disk and used during recovery.

The recovery system demonstrates database concepts such as:

- BEGIN
- WRITE
- COMMIT
- ABORT
- REDO
- ROLLBACK

### Benchmarking

Run transaction workloads and observe execution and concurrency behavior.

## Architecture

```text
                    React Frontend
                         │
                         │ REST / WebSocket
                         ▼
                  FastAPI Backend
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
     Transaction Manager       Concurrency Control
             │                ┌──────┼──────┐
             │                │      │      │
             │               2PL    MVCC    OCC
             │
             ▼
       Lock Manager
             │
             ▼
      Deadlock Detector
       Wait-For Graph
             │
             ▼
       Storage Engine
             │
             ├──────────────► In-Memory State
             │
             └──────────────► Write-Ahead Log
                                  │
                                  ▼
                            Recovery Manager
Tech Stack
Backend
Python
FastAPI
WebSockets
Pytest
Multithreading
Frontend
React
JavaScript / JSX
Vite
CSS
Database Concepts
Transactions
ACID properties
Strict 2PL
MVCC
OCC
Timestamp Ordering
Deadlock Detection
Wait-For Graphs
WAL
Recovery
Isolation Levels
Serializability
Project Structure
DBMS-Transaction-Manager-Simulator/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── concurrency/
│   │   ├── scenarios/
│   │   ├── benchmark.py
│   │   ├── deadlock_detector.py
│   │   ├── lock_manager.py
│   │   ├── log_manager.py
│   │   ├── recovery_manager.py
│   │   ├── serializability.py
│   │   ├── storage_engine.py
│   │   └── transaction_manager.py
│   │
│   ├── tests/
│   ├── demo_cli.py
│   ├── requirements.txt
│   └── run_server.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   └── ...
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
Running Locally
1. Start the Backend
cd backend
python run_server.py

Backend:

http://localhost:8000

API documentation:

http://localhost:8000/docs
2. Start the Frontend

Open another terminal:

cd frontend
npm install
npm run dev

Then open:

http://localhost:5173
Testing

Run the backend test suite:

cd backend
python -m pytest tests -v

Run the command-line demonstration:

python demo_cli.py
Example Scenarios
High Contention Transfer

Multiple transactions concurrently access shared data.

The simulator visualizes:

Lock acquisition
Transaction blocking
Reads and writes
Commit
Retry behavior
WAL records
Cyclic Deadlock Challenge

Two transactions acquire conflicting resources and create a circular dependency.

The simulator detects the cycle through the Wait-For Graph and resolves it by aborting a selected transaction and rolling back its changes.

Why This Project?

Database transaction management is often taught through diagrams and theory.

This project turns those concepts into an interactive system where transaction execution, locking, deadlocks, isolation anomalies, logging, and recovery can be observed directly.

Status

Core transaction-management features are implemented and tested.

The project is intended as an educational DBMS simulation and is not a production database system.

Author

Anaitha Rajesh

Computer Science Student
