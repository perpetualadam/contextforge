"""
Database Connection and Utilities Module

This module provides database connection management, query execution utilities,
and data access patterns for the application. It supports connection pooling,
transaction management, and common database operations.
"""

import sqlite3
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    database_path: str
    pool_size: int = 10
    timeout: float = 30.0
    check_same_thread: bool = False
    enable_foreign_keys: bool = True


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class QueryError(DatabaseError):
    """Raised when query execution fails."""
    pass


class DatabaseManager:
    """
    Manages database connections and provides query execution utilities.
    
    This class handles connection pooling, transaction management,
    and provides convenient methods for common database operations.
    """
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize the database manager.
        
        Args:
            config: Database configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._connection = None
        
        # Initialize database
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database connection and create tables if needed."""
        try:
            self._connection = sqlite3.connect(
                self.config.database_path,
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread
            )
            
            # Enable foreign keys if configured
            if self.config.enable_foreign_keys:
                self._connection.execute("PRAGMA foreign_keys = ON")
            
            # Set row factory for dict-like access
            self._connection.row_factory = sqlite3.Row
            
            self.logger.info(f"Database initialized: {self.config.database_path}")
            
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to initialize database: {e}")
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection with automatic cleanup.
        
        Yields:
            Database connection object
            
        Raises:
            ConnectionError: If connection fails
        """
        if not self._connection:
            self._initialize_database()
        
        try:
            yield self._connection
        except sqlite3.Error as e:
            self._connection.rollback()
            raise QueryError(f"Database operation failed: {e}")
    
    @contextmanager
    def transaction(self):
        """
        Execute operations within a database transaction.
        
        Automatically commits on success or rolls back on error.
        
        Yields:
            Database connection object
        """
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
                self.logger.debug("Transaction committed successfully")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Transaction rolled back: {e}")
                raise
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """
        Execute a SQL query with optional parameters.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            Database cursor with results
            
        Raises:
            QueryError: If query execution fails
        """
        with self.get_connection() as conn:
            try:
                if params:
                    cursor = conn.execute(query, params)
                else:
                    cursor = conn.execute(query)
                
                self.logger.debug(f"Query executed: {query[:100]}...")
                return cursor
                
            except sqlite3.Error as e:
                raise QueryError(f"Query execution failed: {e}")
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row from query results.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            Single row as dictionary or None if no results
        """
        cursor = self.execute_query(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Fetch all rows from query results.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            List of rows as dictionaries
        """
        cursor = self.execute_query(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert a record into a table.
        
        Args:
            table: Table name
            data: Dictionary of column names and values
            
        Returns:
            ID of inserted record
            
        Raises:
            QueryError: If insert fails
        """
        columns = list(data.keys())
        placeholders = ["?" for _ in columns]
        values = list(data.values())
        
        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        
        with self.transaction() as conn:
            cursor = conn.execute(query, values)
            return cursor.lastrowid
    
    def update(self, table: str, data: Dict[str, Any], where_clause: str, where_params: Tuple) -> int:
        """
        Update records in a table.
        
        Args:
            table: Table name
            data: Dictionary of column names and new values
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
            
        Returns:
            Number of affected rows
        """
        set_clauses = [f"{col} = ?" for col in data.keys()]
        values = list(data.values()) + list(where_params)
        
        query = f"""
            UPDATE {table}
            SET {', '.join(set_clauses)}
            WHERE {where_clause}
        """
        
        with self.transaction() as conn:
            cursor = conn.execute(query, values)
            return cursor.rowcount
    
    def delete(self, table: str, where_clause: str, where_params: Tuple) -> int:
        """
        Delete records from a table.
        
        Args:
            table: Table name
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
            
        Returns:
            Number of deleted rows
        """
        query = f"DELETE FROM {table} WHERE {where_clause}"
        
        with self.transaction() as conn:
            cursor = conn.execute(query, where_params)
            return cursor.rowcount
    
    def create_tables(self) -> None:
        """Create application tables if they don't exist."""
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        ]
        
        with self.transaction() as conn:
            for sql in tables_sql:
                conn.execute(sql)
        
        self.logger.info("Database tables created successfully")
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get information about table structure.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        query = f"PRAGMA table_info({table_name})"
        return self.fetch_all(query)
    
    def backup_database(self, backup_path: str) -> None:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file
        """
        with self.get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        
        self.logger.info(f"Database backed up to: {backup_path}")
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self.logger.info("Database connection closed")


def create_database_manager(database_path: str = "app.db") -> DatabaseManager:
    """
    Create and configure a database manager instance.
    
    Args:
        database_path: Path to SQLite database file
        
    Returns:
        Configured DatabaseManager instance
    """
    config = DatabaseConfig(
        database_path=database_path,
        pool_size=10,
        timeout=30.0,
        enable_foreign_keys=True
    )
    
    db_manager = DatabaseManager(config)
    db_manager.create_tables()
    
    return db_manager


# Example usage
if __name__ == "__main__":
    # Initialize database
    db = create_database_manager("example.db")
    
    try:
        # Insert a user
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "hashed_password_here",
            "role": "user"
        }
        
        user_id = db.insert("users", user_data)
        print(f"User created with ID: {user_id}")
        
        # Fetch the user
        user = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        print(f"User found: {user}")
        
        # Update the user
        updated_rows = db.update(
            "users",
            {"last_login": datetime.now().isoformat()},
            "id = ?",
            (user_id,)
        )
        print(f"Updated {updated_rows} rows")
        
    finally:
        db.close()
