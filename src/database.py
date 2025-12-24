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
                    logger.debug(f"Added column: {column}")
                except sqlite3.OperationalError as e:
                    # Column already exists - this is expected during upgrades
                    if 'duplicate column name' not in str(e).lower():
                        logger.warning(f"Unexpected error adding column {column}: {e}")
            
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
            
            # Processing queue table for crash recovery
            # Tracks files that are in-flight (being processed) so they can be
            # recovered if the application crashes mid-processing
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_processing_queue_status 
                ON processing_queue(status)
            ''')
            
            # Corrections table for learning from user feedback
            # When users manually reassign documents, we store the correction
            # to improve future classifications
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classification_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    original_category TEXT NOT NULL,
                    original_subcategory TEXT,
                    corrected_category TEXT NOT NULL,
                    corrected_subcategory TEXT,
                    document_type TEXT,
                    content_snippet TEXT,
                    filename_pattern TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_corrections_category 
                ON classification_corrections(corrected_category)
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
            
            # Create FTS5 virtual table for full-text search
            # This enables fast text searching across document content
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    original_filename,
                    document_type,
                    content_snippet,
                    content_summary,
                    category,
                    subcategory,
                    content='documents',
                    content_rowid='id',
                    tokenize='porter unicode61'
                )
            ''')
            
            # Create triggers to keep FTS index in sync with documents table
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, original_filename, document_type, 
                        content_snippet, content_summary, category, subcategory)
                    VALUES (new.id, new.original_filename, new.document_type,
                        new.content_snippet, new.content_summary, new.category, new.subcategory);
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, original_filename, 
                        document_type, content_snippet, content_summary, category, subcategory)
                    VALUES ('delete', old.id, old.original_filename, old.document_type,
                        old.content_snippet, old.content_summary, old.category, old.subcategory);
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, original_filename,
                        document_type, content_snippet, content_summary, category, subcategory)
                    VALUES ('delete', old.id, old.original_filename, old.document_type,
                        old.content_snippet, old.content_summary, old.category, old.subcategory);
                    INSERT INTO documents_fts(rowid, original_filename, document_type,
                        content_snippet, content_summary, category, subcategory)
                    VALUES (new.id, new.original_filename, new.document_type,
                        new.content_snippet, new.content_summary, new.category, new.subcategory);
                END
            ''')
            
            conn.commit()
            logger.debug(f"Database initialized at {self.db_path}")
            
            # Rebuild FTS index if it's empty but documents exist
            self._rebuild_fts_if_needed(conn)
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            # Enable WAL mode for better concurrent access
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
            yield conn
        finally:
            conn.close()
    
    def _rebuild_fts_if_needed(self, conn: sqlite3.Connection) -> None:
        """Rebuild FTS index if it's empty but documents exist (migration case)."""
        try:
            cursor = conn.cursor()
            
            # Check if documents exist but FTS is empty
            cursor.execute('SELECT COUNT(*) FROM documents')
            doc_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM documents_fts')
            fts_count = cursor.fetchone()[0]
            
            if doc_count > 0 and fts_count == 0:
                logger.info(f"Rebuilding FTS index for {doc_count} existing documents...")
                self._rebuild_fts_index(conn)
                logger.info("FTS index rebuild complete")
                
        except sqlite3.OperationalError as e:
            logger.debug(f"FTS check skipped (table may not exist yet): {e}")
    
    def _rebuild_fts_index(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """Rebuild the entire FTS index from the documents table."""
        should_close = conn is None
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
        
        try:
            cursor = conn.cursor()
            
            # Delete all existing FTS data
            cursor.execute("INSERT INTO documents_fts(documents_fts) VALUES('delete-all')")
            
            # Repopulate from documents table
            cursor.execute('''
                INSERT INTO documents_fts(rowid, original_filename, document_type,
                    content_snippet, content_summary, category, subcategory)
                SELECT id, original_filename, document_type, content_snippet,
                    content_summary, category, subcategory
                FROM documents
            ''')
            
            conn.commit()
            
        finally:
            if should_close:
                conn.close()
    
    def rebuild_search_index(self) -> int:
        """
        Manually rebuild the FTS search index.
        
        Call this if search results seem stale or after manual database edits.
        
        Returns:
            Number of documents indexed
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM documents')
            count = cursor.fetchone()[0]
            
            self._rebuild_fts_index(conn)
            logger.info(f"Rebuilt FTS index for {count} documents")
            return count
    
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
                       d.original_filename, a.timestamp
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
                    'filename': row[5],
                    'timestamp': row[6]
                }
            return None
    
    def get_undoable_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent actions that can be undone.
        
        Args:
            limit: Maximum number of actions to return
            
        Returns:
            List of undoable actions with details
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.action, a.document_id, a.old_path, a.new_path,
                       d.original_filename, a.timestamp, d.current_path, d.category,
                       d.subcategory
                FROM activity_log a
                LEFT JOIN documents d ON a.document_id = d.id
                WHERE a.action IN ('processed', 'reassigned')
                  AND a.old_path IS NOT NULL
                  AND a.new_path IS NOT NULL
                ORDER BY a.timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            actions = []
            for row in cursor.fetchall():
                actions.append({
                    'id': row[0],
                    'action': row[1],
                    'document_id': row[2],
                    'old_path': row[3],
                    'new_path': row[4],
                    'filename': row[5],
                    'timestamp': row[6],
                    'current_path': row[7],
                    'category': row[8],
                    'subcategory': row[9]
                })
            return actions
    
    def undo_action(self, action_id: int) -> Dict[str, Any]:
        """
        Undo a specific action by moving the file back to its original location.
        
        Args:
            action_id: ID of the action to undo
            
        Returns:
            Dict with success status and details
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get the action details
            cursor.execute('''
                SELECT a.id, a.action, a.document_id, a.old_path, a.new_path,
                       d.original_filename, d.current_path
                FROM activity_log a
                LEFT JOIN documents d ON a.document_id = d.id
                WHERE a.id = ?
            ''', (action_id,))
            
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': 'Action not found'}
            
            action_type = row[1]
            document_id = row[2]
            old_path = row[3]
            new_path = row[4]
            filename = row[5]
            current_path = row[6]
            
            if not old_path or not new_path:
                return {'success': False, 'error': 'Cannot undo: missing path information'}
            
            # Check if file is still at the expected location
            from pathlib import Path
            current_file = Path(current_path) if current_path else Path(new_path)
            target_path = Path(old_path)
            
            if not current_file.exists():
                return {
                    'success': False, 
                    'error': f'File no longer exists at expected location: {current_file}'
                }
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle filename conflicts at target
            final_target = target_path
            if final_target.exists():
                counter = 1
                while final_target.exists():
                    final_target = target_path.parent / f"{target_path.stem}_{counter}{target_path.suffix}"
                    counter += 1
            
            try:
                import shutil
                shutil.move(str(current_file), str(final_target))
                
                # Update document record
                if document_id:
                    # Extract category from old path
                    old_category = target_path.parent.name
                    old_subcategory = ''
                    
                    cursor.execute('''
                        UPDATE documents
                        SET current_path = ?, status = 'undone'
                        WHERE id = ?
                    ''', (str(final_target), document_id))
                
                # Log the undo action
                self._log_activity(
                    conn, 'undone', document_id,
                    f"Undid action: moved back from {new_path}",
                    str(current_file), str(final_target)
                )
                
                conn.commit()
                
                return {
                    'success': True,
                    'filename': filename,
                    'old_location': str(current_file),
                    'new_location': str(final_target),
                    'action_undone': action_type
                }
                
            except Exception as e:
                logger.error(f"Undo failed: {e}")
                return {'success': False, 'error': str(e)}
    
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
        Search documents using FTS5 full-text search with fallback strategies.
        
        Uses SQLite FTS5 for fast, indexed text search with ranking.
        Falls back to LIKE queries if FTS5 is unavailable.
        
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
            
            # Strategy 1: Exact category/subcategory match (high priority)
            if category_hint:
                cursor.execute('''
                    SELECT id, original_filename, current_path, category, 
                           subcategory, document_type, confidence, content_snippet,
                           processed_at, content_summary
                    FROM documents
                    WHERE LOWER(category) = LOWER(?) 
                       OR LOWER(subcategory) = LOWER(?)
                    ORDER BY processed_at DESC
                    LIMIT ?
                ''', (category_hint, category_hint, limit))
                
                for row in cursor.fetchall():
                    if row[0] not in seen_ids:
                        seen_ids.add(row[0])
                        result = self._row_to_search_result(row, 'category_match', 0.9)
                        result['match_snippet'] = row[9] if row[9] else ''
                        results.append(result)
            
            # Strategy 2: FTS5 full-text search (fast, indexed)
            if search_terms:
                try:
                    # Build FTS5 query - OR together all terms for broad matching
                    # FTS5 uses special syntax: term1 OR term2 OR term3
                    fts_query = ' OR '.join(f'"{term}"' for term in search_terms if term)
                    
                    if fts_query:
                        # FTS5 search with BM25 ranking (lower score = better match)
                        cursor.execute('''
                            SELECT d.id, d.original_filename, d.current_path, d.category,
                                   d.subcategory, d.document_type, d.confidence, d.content_snippet,
                                   d.processed_at, d.content_summary,
                                   bm25(documents_fts) as rank
                            FROM documents_fts
                            JOIN documents d ON d.id = documents_fts.rowid
                            WHERE documents_fts MATCH ?
                            ORDER BY rank
                            LIMIT ?
                        ''', (fts_query, limit * 2))  # Fetch extra to account for dedup
                        
                        for row in cursor.fetchall():
                            if row[0] not in seen_ids:
                                seen_ids.add(row[0])
                                # Convert BM25 rank to relevance (BM25 gives negative scores, more negative = better)
                                bm25_score = row[10] if row[10] else 0
                                # Normalize to 0-1 range (assuming typical BM25 range of -20 to 0)
                                relevance = min(1.0, max(0.5, 1.0 + (bm25_score / 20)))
                                
                                result = self._row_to_search_result(row[:10], 'fts_match', relevance)
                                # Extract snippet around match
                                content = row[7] or row[9] or ''
                                if content:
                                    for term in search_terms:
                                        snippet = self._extract_match_snippet(content, term)
                                        if snippet:
                                            result['match_snippet'] = snippet
                                            break
                                results.append(result)
                                
                except sqlite3.OperationalError as e:
                    # FTS5 not available or error - fall back to LIKE queries
                    logger.debug(f"FTS5 search failed, using fallback: {e}")
                    results.extend(self._search_documents_fallback(
                        cursor, search_terms, seen_ids, limit
                    ))
            
            # Sort by relevance score
            results.sort(key=lambda x: x['relevance'], reverse=True)
            
            return results[:limit]
    
    def _search_documents_fallback(
        self,
        cursor: sqlite3.Cursor,
        search_terms: List[str],
        seen_ids: set,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback search using LIKE queries when FTS5 is unavailable.
        
        This is slower but works on older SQLite versions.
        """
        results = []
        
        # Search document type
        for term in search_terms[:5]:  # Limit terms to avoid too many queries
            cursor.execute('''
                SELECT id, original_filename, current_path, category, 
                       subcategory, document_type, confidence, content_snippet,
                       processed_at, content_summary
                FROM documents
                WHERE LOWER(document_type) LIKE ? 
                   OR LOWER(original_filename) LIKE ?
                   OR LOWER(content_summary) LIKE ?
                ORDER BY processed_at DESC
                LIMIT ?
            ''', (f'%{term}%', f'%{term}%', f'%{term}%', limit))
            
            for row in cursor.fetchall():
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    result = self._row_to_search_result(row, f'fallback_match:{term}', 0.7)
                    result['match_snippet'] = row[9] if row[9] else ''
                    results.append(result)
        
        return results
    
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
    
    # =========================================================================
    # Processing Queue Methods (Crash Recovery)
    # =========================================================================
    
    def queue_file_for_processing(self, file_path: str) -> int:
        """
        Add a file to the processing queue.
        
        Args:
            file_path: Absolute path to the file
            
        Returns:
            Queue entry ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO processing_queue (file_path, status)
                    VALUES (?, 'pending')
                    ON CONFLICT(file_path) DO UPDATE SET
                        status = 'pending',
                        retry_count = retry_count + 1,
                        queued_at = CURRENT_TIMESTAMP,
                        error_message = NULL
                ''', (file_path,))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Error queueing file: {e}")
                return -1
    
    def mark_processing_started(self, file_path: str) -> bool:
        """
        Mark a file as currently being processed.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if successfully marked
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE processing_queue 
                SET status = 'processing', started_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            ''', (file_path,))
            conn.commit()
            return cursor.rowcount > 0
    
    def mark_processing_completed(self, file_path: str, success: bool = True, 
                                   error_message: str = None) -> bool:
        """
        Mark a file as completed (successfully or with error).
        
        Args:
            file_path: Path to the file
            success: Whether processing succeeded
            error_message: Error message if failed
            
        Returns:
            True if successfully marked
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if success:
                # Remove from queue on success
                cursor.execute('''
                    DELETE FROM processing_queue WHERE file_path = ?
                ''', (file_path,))
            else:
                # Mark as failed with error
                cursor.execute('''
                    UPDATE processing_queue 
                    SET status = 'failed', 
                        completed_at = CURRENT_TIMESTAMP,
                        error_message = ?
                    WHERE file_path = ?
                ''', (error_message, file_path))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_pending_queue_items(self, include_failed: bool = False) -> List[Dict[str, Any]]:
        """
        Get all pending items from the processing queue.
        
        Used for crash recovery to resume processing.
        
        Args:
            include_failed: Whether to include failed items for retry
            
        Returns:
            List of queue items with file paths and status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if include_failed:
                cursor.execute('''
                    SELECT id, file_path, status, retry_count, error_message,
                           queued_at, started_at
                    FROM processing_queue
                    WHERE status IN ('pending', 'processing', 'failed')
                    ORDER BY queued_at ASC
                ''')
            else:
                cursor.execute('''
                    SELECT id, file_path, status, retry_count, error_message,
                           queued_at, started_at
                    FROM processing_queue
                    WHERE status IN ('pending', 'processing')
                    ORDER BY queued_at ASC
                ''')
            
            return [{
                'id': row[0],
                'file_path': row[1],
                'status': row[2],
                'retry_count': row[3],
                'error_message': row[4],
                'queued_at': row[5],
                'started_at': row[6]
            } for row in cursor.fetchall()]
    
    def get_interrupted_items(self) -> List[Dict[str, Any]]:
        """
        Get items that were being processed when the app crashed.
        
        These are items with status='processing' that never completed.
        
        Returns:
            List of interrupted queue items
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, file_path, retry_count, queued_at, started_at
                FROM processing_queue
                WHERE status = 'processing'
                ORDER BY started_at ASC
            ''')
            
            return [{
                'id': row[0],
                'file_path': row[1],
                'retry_count': row[2],
                'queued_at': row[3],
                'started_at': row[4]
            } for row in cursor.fetchall()]
    
    def reset_interrupted_items(self) -> int:
        """
        Reset interrupted items back to pending status for reprocessing.
        
        Call this on startup to recover from crashes.
        
        Returns:
            Number of items reset
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE processing_queue 
                SET status = 'pending', started_at = NULL
                WHERE status = 'processing'
            ''')
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Reset {count} interrupted processing items for recovery")
            return count
    
    def clear_completed_queue_items(self, older_than_hours: int = 24) -> int:
        """
        Clean up old completed/failed queue items.
        
        Args:
            older_than_hours: Remove items older than this many hours
            
        Returns:
            Number of items removed
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM processing_queue
                WHERE status = 'failed'
                  AND completed_at < datetime('now', ? || ' hours')
            ''', (f'-{older_than_hours}',))
            conn.commit()
            return cursor.rowcount
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get processing queue statistics.
        
        Returns:
            Dict with counts by status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM processing_queue 
                GROUP BY status
            ''')
            return {row[0]: row[1] for row in cursor.fetchall()}
    
    # =========================================================================
    # Classification Corrections (Learning from User Feedback)
    # =========================================================================
    
    def record_correction(
        self, 
        document_id: int,
        original_category: str,
        original_subcategory: str,
        corrected_category: str,
        corrected_subcategory: str,
        document_type: str = '',
        content_snippet: str = '',
        filename: str = ''
    ) -> int:
        """
        Record a classification correction for future learning.
        
        Called when a user manually reassigns a document to a different category.
        
        Args:
            document_id: ID of the document being corrected
            original_category: The AI's original classification
            original_subcategory: The AI's original subcategory
            corrected_category: The user's corrected category
            corrected_subcategory: The user's corrected subcategory
            document_type: Type of document (e.g., "invoice", "receipt")
            content_snippet: First portion of document text for pattern matching
            filename: Original filename for pattern extraction
            
        Returns:
            ID of the correction record
        """
        # Extract filename pattern (remove numbers, dates, keep structure)
        import re
        filename_pattern = ''
        if filename:
            # Remove date patterns, numbers, keep structure
            pattern = re.sub(r'\d{4}[-_]\d{2}[-_]\d{2}', 'DATE', filename)
            pattern = re.sub(r'\d+', 'N', pattern)
            filename_pattern = pattern
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO classification_corrections 
                    (document_id, original_category, original_subcategory,
                     corrected_category, corrected_subcategory, document_type,
                     content_snippet, filename_pattern)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (document_id, original_category, original_subcategory,
                  corrected_category, corrected_subcategory, document_type,
                  content_snippet[:500] if content_snippet else '',  # Limit size
                  filename_pattern))
            conn.commit()
            
            logger.info(f"Recorded correction: {original_category} -> {corrected_category}")
            return cursor.lastrowid
    
    def get_relevant_corrections(
        self, 
        document_type: str = '',
        content_hint: str = '',
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant past corrections to use as few-shot examples.
        
        Finds corrections that may be relevant to the current document
        based on document type and content similarity.
        
        Args:
            document_type: Type of document being classified
            content_hint: Brief content description or keywords
            limit: Maximum corrections to return
            
        Returns:
            List of relevant corrections with original/corrected categories
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            corrections = []
            seen_pairs = set()  # Avoid duplicate correction patterns
            
            # Strategy 1: Same document type
            if document_type:
                cursor.execute('''
                    SELECT original_category, original_subcategory,
                           corrected_category, corrected_subcategory,
                           document_type, content_snippet
                    FROM classification_corrections
                    WHERE LOWER(document_type) LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (f'%{document_type.lower()}%', limit))
                
                for row in cursor.fetchall():
                    pair_key = f"{row[0]}|{row[2]}"  # orig_cat|corrected_cat
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        corrections.append({
                            'original_category': row[0],
                            'original_subcategory': row[1] or '',
                            'corrected_category': row[2],
                            'corrected_subcategory': row[3] or '',
                            'document_type': row[4] or '',
                            'reason': f"Similar document type: {row[4]}"
                        })
            
            # Strategy 2: Get most common corrections overall
            if len(corrections) < limit:
                cursor.execute('''
                    SELECT original_category, original_subcategory,
                           corrected_category, corrected_subcategory,
                           document_type, COUNT(*) as freq
                    FROM classification_corrections
                    GROUP BY original_category, corrected_category
                    ORDER BY freq DESC
                    LIMIT ?
                ''', (limit - len(corrections),))
                
                for row in cursor.fetchall():
                    pair_key = f"{row[0]}|{row[2]}"
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        corrections.append({
                            'original_category': row[0],
                            'original_subcategory': row[1] or '',
                            'corrected_category': row[2],
                            'corrected_subcategory': row[3] or '',
                            'document_type': row[4] or '',
                            'reason': f"Common correction pattern ({row[5]} times)"
                        })
            
            return corrections[:limit]
    
    def get_correction_stats(self) -> Dict[str, Any]:
        """
        Get statistics about classification corrections.
        
        Returns:
            Dict with correction counts and patterns
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total corrections
            cursor.execute('SELECT COUNT(*) FROM classification_corrections')
            total = cursor.fetchone()[0]
            
            # Most common corrections
            cursor.execute('''
                SELECT original_category, corrected_category, COUNT(*) as freq
                FROM classification_corrections
                GROUP BY original_category, corrected_category
                ORDER BY freq DESC
                LIMIT 10
            ''')
            
            common = [{
                'from': row[0],
                'to': row[1],
                'count': row[2]
            } for row in cursor.fetchall()]
            
            return {
                'total_corrections': total,
                'common_patterns': common
            }

