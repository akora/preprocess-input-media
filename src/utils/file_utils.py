"""
File utility functions for media pre-processing.

This module provides utility functions for file operations such as
extension normalization, directory creation, and file tracking.
"""

import os
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Tuple

from src.config import EXTENSION_MAPPING


def get_file_extension(file_path: str | Path) -> str:
    """
    Get the extension of a file.
    
    Args:
        file_path: Path to the file
    
    Returns:
        File extension with leading dot (e.g., '.jpg')
    """
    if isinstance(file_path, Path):
        return file_path.suffix
    return os.path.splitext(file_path)[1]


def get_normalized_extension(extension: str) -> str:
    """
    Normalize file extension to lowercase 3-letter format.
    
    Args:
        extension: File extension with leading dot (e.g., '.JPG')
    
    Returns:
        Normalized extension (e.g., '.jpg')
    """
    ext = extension.lower()
    return EXTENSION_MAPPING.get(ext, ext)


def create_output_directory(base_dir: str | Path, timestamp: datetime, media_type: str = None) -> Path:
    """
    Create output directory structure based on date and media type.
    
    Args:
        base_dir: Base output directory
        timestamp: Datetime object for directory structure
        media_type: Type of media ('image' or 'video')
    
    Returns:
        Path object for the created directory
    """
    # Get date components
    year = timestamp.strftime('%Y')
    month = timestamp.strftime('%m')
    day = timestamp.strftime('%d')
    
    # Create base path with media type if provided
    base_path = Path(base_dir)
    if media_type:
        if media_type == 'image':
            base_path = base_path / 'photos'
        elif media_type == 'video':
            base_path = base_path / 'videos'
    
    # Create directory structure: [photos|videos]/YYYY/YYYY-MM/YYYY-MM-DD
    output_dir = base_path / year / f"{year}-{month}" / f"{year}-{month}-{day}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir


def initialize_processed_files_db(db_path: str) -> None:
    """Initialize the processed files database.
    
    Args:
        db_path: Path to the database file
    """
    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created directory for database: {db_dir}")
        except Exception as e:
            print(f"Warning: Could not create directory for database: {e}")
            # Fall back to current directory if home directory is not writable
            db_path = '.preprocess_media_files.db'
            print(f"Using fallback database location: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            id INTEGER PRIMARY KEY,
            source_path TEXT UNIQUE,
            output_path TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        print(f"Database initialized at: {db_path}")
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Processing will continue but processed files won't be tracked.")


def mark_file_as_processed(db_path: str, source_path: str, output_path: str) -> None:
    """
    Mark a file as processed in the tracking database.
    
    Args:
        db_path: Path to the SQLite database file
        source_path: Original file path
        output_path: Processed file path
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert with the new schema (id is auto-incremented)
        cursor.execute(
            'INSERT OR REPLACE INTO processed_files (source_path, output_path) VALUES (?, ?)',
            (source_path, output_path)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not mark file as processed in database: {e}")
        print("Processing will continue but this file won't be tracked.")


def is_file_already_processed(source_path: str, output_path: str, db_path: Optional[str] = None) -> bool:
    """
    Check if a file has already been processed.
    
    This function checks both the tracking database and the existence of the output file.
    
    Args:
        source_path: Original file path
        output_path: Processed file path
        db_path: Path to the SQLite database file
    
    Returns:
        True if the file has been processed, False otherwise
    """
    # Import here to avoid circular imports
    from src.config import PROCESSED_FILES_DB
    
    if not db_path:
        db_path = PROCESSED_FILES_DB
    
    # Check if the output file exists
    if os.path.exists(output_path):
        return True
    
    # Make sure the database exists
    if not os.path.exists(db_path):
        initialize_processed_files_db(db_path)
        return False
    
    try:
        # Check the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT output_path FROM processed_files WHERE source_path = ?',
            (source_path,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        # If we found a record, the file has been processed
        return result is not None
    except Exception as e:
        print(f"Warning: Error checking if file was processed: {e}")
        return False


def get_processed_files(db_path: Optional[str] = None) -> Set[str]:
    """
    Get a set of all processed file paths.
    
    Args:
        db_path: Path to the SQLite database file
    
    Returns:
        Set of paths to files that have been processed
    """
    from src.config import PROCESSED_FILES_DB
    
    if db_path is None:
        db_path = PROCESSED_FILES_DB
    
    if not os.path.exists(db_path):
        return set()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT source_path FROM processed_files')
    
    result = cursor.fetchall()
    conn.close()
    
    return {row[0] for row in result}
