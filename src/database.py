"""
Database module for Sift.

Provides SQLite-based persistence for document tracking,
activity logging, and history management.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """Represents a processed document in the database."""
    id: int
    original_filename: str
    original_path: str
    current_path: str
    category: str
    subcategory: str
    document_type: str
    confidence: float
    reasoning: str
    processed_at: str
    status: str  # 'processed', 'needs_review', 'manual_override'
    content_summary: str = ''  # LLM's understanding of the document
    
    @classmethod
    def from_row(cls, row: tuple) -> 'DocumentRecord':
        return cls(
            id=row[0],
            original_filename=row[1],
            original_path=row[2],
            current_path=row[3],
            category=row[4],
            subcategory=row[5] or '',
            document_type=row[6] or '',
            confidence=row[7] or 0.0,
            reasoning=row[8] or '',
            processed_at=row[9],
            status=row[10],
            content_summary=row[11] if len(row) > 11 else ''
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'original_path': self.original_path,
            'current_path': self.current_path,
            'category': self.category,
            'subcategory': self.subcategory,
            'document_type': self.document_type,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'processed_at': self.processed_at,
            'status': self.status,
            'content_summary': self.content_summary
        }


class DocumentDatabase:
    """
    SQLite database for tracking processed documents.
    
    Provides:
    - Document history tracking
    - Activity logging
    - Statistics queries
    - Undo support
    """
    
    def __init__(self, db_path: Path):
        """Initialize the database."""
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Documents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_filename TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    current_path TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    document_type TEXT,
                    confidence REAL,
                    reasoning TEXT,
                    content_snippet TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'processed'
                )
            ''')
            
            # Add columns if they don't exist (for upgrades)
            for column in ['content_snippet TEXT', 'content_summary TEXT']:
                try:
                    cursor.execute(f'ALTER TABLE documents ADD COLUMN {column}')
                except:
                    pass  # Column already exists
            
            # Activity log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    document_id INTEGER,
                    details TEXT,
                    old_path TEXT,
                    new_path TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            ''')
            
            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_documents_processed_at 
                ON documents(processed_at DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_documents_status 
                ON documents(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_documents_category 
                ON documents(category)
            ''')
            
            conn.commit()
            logger.debug(f"Database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()
    
    def add_document(
        self,
        original_filename: str,
        original_path: str,
        current_path: str,
        category: str,
        subcategory: str = '',
        document_type: str = '',
        confidence: float = 0.0,
        reasoning: str = '',
        content_snippet: str = '',
        content_summary: str = '',
        status: str = 'processed'
    ) -> int:
        """
        Add a processed document to the database.
        
        Args:
            content_snippet: First ~2000 chars of document content for searching
            content_summary: LLM's understanding of what the document contains
        
        Returns:
            The ID of the inserted document
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents 
                (original_filename, original_path, current_path, category, 
                 subcategory, document_type, confidence, reasoning, content_snippet,
                 content_summary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                original_filename, original_path, current_path, category,
                subcategory, document_type, confidence, reasoning, 
                content_snippet[:2000] if content_snippet else '',
                content_summary[:1000] if content_summary else '', status
            ))
            conn.commit()
            doc_id = cursor.lastrowid
            
            # Log the activity
            self._log_activity(
                conn, 'processed', doc_id,
                f"Classified as {category}/{subcategory}" if subcategory else f"Classified as {category}",
                original_path, current_path
            )
            
            logger.debug(f"Added document {doc_id}: {original_filename}")
            return doc_id
    
    def _log_activity(
        self,
        conn: sqlite3.Connection,
        action: str,
        document_id: Optional[int],
        details: str,
        old_path: str = '',
        new_path: str = ''
    ) -> None:
        """Log an activity to the activity log."""
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activity_log (action, document_id, details, old_path, new_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (action, document_id, details, old_path, new_path))
        conn.commit()
    
    def get_recent_documents(self, limit: int = 20) -> List[DocumentRecord]:
        """Get recently processed documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, original_filename, original_path, current_path,
                       category, subcategory, document_type, confidence,
                       reasoning, processed_at, status, content_summary
                FROM documents
                ORDER BY processed_at DESC
                LIMIT ?
            ''', (limit,))
            return [DocumentRecord.from_row(row) for row in cursor.fetchall()]
    
    def get_documents_needing_review(self) -> List[DocumentRecord]:
        """Get documents that need manual review."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, original_filename, original_path, current_path,
                       category, subcategory, document_type, confidence,
                       reasoning, processed_at, status, content_summary
                FROM documents
                WHERE status = 'needs_review'
                ORDER BY processed_at DESC
            ''')
            return [DocumentRecord.from_row(row) for row in cursor.fetchall()]
    
    def get_document_by_id(self, doc_id: int) -> Optional[DocumentRecord]:
        """Get a specific document by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, original_filename, original_path, current_path,
                       category, subcategory, document_type, confidence,
                       reasoning, processed_at, status
                FROM documents
                WHERE id = ?
            ''', (doc_id,))
            row = cursor.fetchone()
            return DocumentRecord.from_row(row) if row else None
    
    def update_document_location(
        self,
        doc_id: int,
        new_path: str,
        new_category: str,
        new_subcategory: str = '',
        status: str = 'manual_override'
    ) -> bool:
        """Update a document's location after reassignment."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get old path for logging
            cursor.execute('SELECT current_path FROM documents WHERE id = ?', (doc_id,))
            row = cursor.fetchone()
            if not row:
                return False
            old_path = row[0]
            
            # Update the document
            cursor.execute('''
                UPDATE documents
                SET current_path = ?, category = ?, subcategory = ?, status = ?
                WHERE id = ?
            ''', (new_path, new_category, new_subcategory, status, doc_id))
            
            # Log the activity
            self._log_activity(
                conn, 'reassigned', doc_id,
                f"Moved to {new_category}/{new_subcategory}" if new_subcategory else f"Moved to {new_category}",
                old_path, new_path
            )
            
            conn.commit()
            return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total documents
            cursor.execute('SELECT COUNT(*) FROM documents')
            total = cursor.fetchone()[0]
            
            # Documents needing review
            cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'needs_review'")
            needs_review = cursor.fetchone()[0]
            
            # Documents processed today
            cursor.execute('''
                SELECT COUNT(*) FROM documents 
                WHERE date(processed_at) = date('now', 'localtime')
            ''')
            today = cursor.fetchone()[0]
            
            # Documents by category
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM documents
                GROUP BY category
                ORDER BY count DESC
            ''')
            by_category = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Recent activity count (last 7 days)
            cursor.execute('''
                SELECT COUNT(*) FROM documents
                WHERE processed_at >= datetime('now', '-7 days', 'localtime')
            ''')
            last_week = cursor.fetchone()[0]
            
            return {
                'total': total,
                'needs_review': needs_review,
                'today': today,
                'last_week': last_week,
                'by_category': by_category
            }
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity log entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.action, a.details, a.old_path, a.new_path, 
                       a.timestamp, d.original_filename
                FROM activity_log a
                LEFT JOIN documents d ON a.document_id = d.id
                ORDER BY a.timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            return [{
                'id': row[0],
                'action': row[1],
                'details': row[2],
                'old_path': row[3],
                'new_path': row[4],
                'timestamp': row[5],
                'filename': row[6]
            } for row in cursor.fetchall()]
    
    def get_last_action(self) -> Optional[Dict[str, Any]]:
        """Get the last action for undo functionality."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.action, a.document_id, a.old_path, a.new_path,
                       d.original_filename
                FROM activity_log a
                LEFT JOIN documents d ON a.document_id = d.id
                WHERE a.action IN ('processed', 'reassigned')
                ORDER BY a.timestamp DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'action': row[1],
                    'document_id': row[2],
                    'old_path': row[3],
                    'new_path': row[4],
                    'filename': row[5]
                }
            return None
    
    def get_all_categories(self) -> List[str]:
        """Get all unique categories from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM documents ORDER BY category')
            return [row[0] for row in cursor.fetchall()]
    
    def search_documents(
        self, 
        query: str,
        search_terms: Optional[List[str]] = None,
        category_hint: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search documents using multiple strategies.
        
        Args:
            query: Original natural language query (for context)
            search_terms: Extracted search terms (keywords)
            category_hint: Suggested category to prioritize
            limit: Maximum results to return
            
        Returns:
            List of matching documents with relevance scores
        """
        if not search_terms:
            # Simple fallback: split query into words
            search_terms = [w.lower() for w in query.split() if len(w) > 2]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            results = []
            seen_ids = set()
            
            # Strategy 1: Exact category/subcategory match
            if category_hint:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at
                    FROM documents
                    WHERE LOWER(category) = LOWER(?) 
                       OR LOWER(subcategory) = LOWER(?)
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (category_hint, category_hint, limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        results.append(self._row_to_search_result(row, 'category_match', 0.9))
            
            # Strategy 2: Document type match
            for term in search_terms:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at
                    FROM documents
                    WHERE LOWER(document_type) LIKE ?
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (f'%{term}%', limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        results.append(self._row_to_search_result(row, f'type_match:{term}', 0.85))
            
            # Strategy 3: Filename match
            for term in search_terms:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at
                    FROM documents
                    WHERE LOWER(original_filename) LIKE ?
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (f'%{term}%', limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        results.append(self._row_to_search_result(row, f'filename_match:{term}', 0.8))
            
            # Strategy 4: AI Summary match (semantic/conceptual matching)
            for term in search_terms:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at, content_summary
                    FROM documents
                    WHERE LOWER(content_summary) LIKE ?
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (f'%{term}%', limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        # Use the summary as the match snippet
                        result = self._row_to_search_result(row, f'summary_match:{term}', 0.78)
                        result['match_snippet'] = row[9] if len(row) > 9 and row[9] else ''
                        results.append(result)
            
            # Strategy 5: Content snippet match (raw text keyword matching)
            for term in search_terms:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at
                    FROM documents
                    WHERE LOWER(content_snippet) LIKE ?
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (f'%{term}%', limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        # Extract snippet around the match
                        snippet = self._extract_match_snippet(row[7], term) if row[7] else ''
                        result = self._row_to_search_result(row, f'content_match:{term}', 0.7)
                        result['match_snippet'] = snippet
                        results.append(result)
            
            # Strategy 6: Subcategory match
            for term in search_terms:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at
                    FROM documents
                    WHERE LOWER(subcategory) LIKE ?
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (f'%{term}%', limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        results.append(self._row_to_search_result(row, f'subcategory_match:{term}', 0.75))
            
            # Sort by relevance score
            results.sort(key=lambda x: x['relevance'], reverse=True)
            
            return results[:limit]
    
    def _row_to_search_result(
        self, 
        row: tuple, 
        match_type: str, 
        relevance: float
    ) -> Dict[str, Any]:
        """Convert database row to search result dict."""
        return {
            'id': row[0],
            'filename': row[1],
            'current_path': row[2],
            'category': row[3],
            'subcategory': row[4] or '',
            'document_type': row[5] or '',
            'confidence': row[6] or 0,
            'processed_at': row[8],
            'match_type': match_type,
            'relevance': relevance,
            'match_snippet': ''
        }
    
    def _extract_match_snippet(self, content: str, term: str, context_chars: int = 100) -> str:
        """Extract a snippet around a matching term."""
        if not content:
            return ''
        
        content_lower = content.lower()
        term_lower = term.lower()
        
        pos = content_lower.find(term_lower)
        if pos == -1:
            return ''
        
        start = max(0, pos - context_chars)
        end = min(len(content), pos + len(term) + context_chars)
        
        snippet = content[start:end]
        
        # Add ellipsis if truncated
        if start > 0:
            snippet = '...' + snippet
        if end < len(content):
            snippet = snippet + '...'
        
        return snippet

