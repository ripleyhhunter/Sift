"""
Dashboard module for Sift.

Provides a local web interface for:
- Viewing recent document activity
- Reviewing low-confidence classifications
- Reassigning documents to different categories
- Viewing statistics
"""

import logging
import shutil
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from flask import Flask, render_template_string, jsonify, request

from .database import DocumentDatabase
from .config import Config

logger = logging.getLogger(__name__)

# The dashboard HTML template (embedded for easy distribution)
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Folder Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --bg-primary: #0a0a12;
            --bg-secondary: #12121f;
            --bg-card: #1a1a2e;
            --bg-hover: #242442;
            --border: #2d2d4a;
            --text-primary: #e4e4e7;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent: #22d3ee;
            --accent-hover: #06b6d4;
            --success: #34d399;
            --warning: #fbbf24;
            --error: #f87171;
            --gradient-start: #1a1a2e;
            --gradient-end: #0f0f1a;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }
        
        .header h1 {
            font-size: 1.75rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .header h1 .icon {
            font-size: 1.5rem;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: var(--bg-card);
            border-radius: 24px;
            font-size: 0.875rem;
            border: 1px solid var(--border);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }
        
        .status-dot.offline {
            background: var(--error);
            animation: none;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Profile Selector */
        .profile-selector {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 16px;
            background: var(--bg-card);
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        
        .profile-selector label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            white-space: nowrap;
        }
        
        .profile-selector select {
            background: var(--bg);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.875rem;
            cursor: pointer;
            min-width: 120px;
        }
        
        .profile-selector select:hover {
            border-color: var(--accent);
        }
        
        .profile-selector select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }
        
        .profile-model {
            font-size: 0.75rem;
            color: var(--text-secondary);
            padding: 4px 8px;
            background: rgba(99, 102, 241, 0.1);
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', monospace;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            transition: transform 0.2s, border-color 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent);
        }
        
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent);
            line-height: 1;
            margin-bottom: 8px;
        }
        
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Main Grid */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        
        @media (max-width: 1024px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            background: rgba(255,255,255,0.02);
        }
        
        .card-title {
            font-size: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .card-badge {
            background: var(--accent);
            color: var(--bg-primary);
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 12px;
        }
        
        .card-badge.warning {
            background: var(--warning);
        }
        
        .card-body {
            padding: 16px 24px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        /* Document List */
        .doc-list {
            list-style: none;
        }
        
        .doc-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            margin: 8px 0;
            background: var(--bg-secondary);
            border-radius: 8px;
            border: 1px solid transparent;
            transition: all 0.2s;
        }
        
        .doc-item:hover {
            background: var(--bg-hover);
            border-color: var(--border);
        }
        
        .doc-expandable {
            cursor: pointer;
            flex-direction: column;
            align-items: stretch;
        }
        
        .doc-expandable .doc-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }
        
        /* Thumbnail styles */
        .doc-thumbnail {
            width: 48px;
            height: 48px;
            min-width: 48px;
            border-radius: 6px;
            overflow: hidden;
            background: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
        }
        
        .doc-thumbnail img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .thumbnail-placeholder {
            font-size: 24px;
            opacity: 0.7;
        }
        
        .doc-text-info {
            flex: 1;
            min-width: 0;
        }
        
        /* Batch selection styles */
        .doc-checkbox {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            cursor: pointer;
            accent-color: var(--accent);
        }
        
        .doc-item.selected {
            background: rgba(59, 130, 246, 0.15);
            border-color: var(--accent);
        }
        
        .batch-actions {
            display: none;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-bottom: 12px;
            gap: 10px;
            align-items: center;
        }
        
        .batch-actions.visible {
            display: flex;
        }
        
        .batch-count {
            font-weight: 600;
            color: var(--accent);
            margin-right: auto;
        }
        
        /* Keyboard shortcut hints */
        .shortcut-hint {
            display: inline-block;
            padding: 2px 6px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            font-size: 11px;
            font-family: monospace;
            color: var(--text-muted);
            margin-left: 6px;
        }
        
        .expand-icon {
            display: inline-block;
            margin-right: 8px;
            transition: transform 0.2s;
            font-size: 0.7em;
            color: var(--text-muted);
        }
        
        .doc-expandable.expanded .expand-icon {
            transform: rotate(90deg);
        }
        
        .doc-details {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            width: 100%;
        }
        
        .ai-analysis {
            background: var(--bg-primary);
            border-radius: 6px;
            padding: 12px;
        }
        
        .analysis-section {
            margin-bottom: 10px;
        }
        
        .analysis-section:last-child {
            margin-bottom: 0;
        }
        
        .analysis-label {
            display: block;
            font-size: 0.75rem;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
            font-weight: 600;
        }
        
        .analysis-value {
            display: block;
            color: var(--text-primary);
            font-size: 0.9rem;
            line-height: 1.5;
        }
        
        .doc-main {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }
        
        .review-analysis {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            background: var(--bg-primary);
            border-radius: 6px;
            padding: 12px;
        }
        
        .doc-info {
            flex: 1;
            min-width: 0;
        }
        
        .doc-name {
            font-family: 'Cascadia Code', 'Consolas', monospace;
            font-size: 0.875rem;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        
        .doc-meta {
            font-size: 0.75rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .doc-category {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            background: rgba(34, 211, 238, 0.1);
            color: var(--accent);
            border-radius: 4px;
            font-size: 0.75rem;
        }
        
        .doc-time {
            color: var(--text-muted);
        }
        
        .doc-confidence {
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 4px;
        }
        
        .confidence-high { background: rgba(52, 211, 153, 0.2); color: var(--success); }
        .confidence-medium { background: rgba(251, 191, 36, 0.2); color: var(--warning); }
        .confidence-low { background: rgba(248, 113, 113, 0.2); color: var(--error); }
        
        /* Actions */
        .doc-actions {
            display: flex;
            gap: 8px;
            margin-left: 16px;
        }
        
        .btn {
            padding: 6px 12px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--accent);
            color: var(--bg-primary);
        }
        
        .btn-primary:hover {
            background: var(--accent-hover);
        }
        
        .btn-ghost {
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        
        .btn-ghost:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        /* Category Select */
        .category-select {
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 0.75rem;
            cursor: pointer;
        }
        
        .category-select:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        /* Category Stats */
        .category-list {
            list-style: none;
        }
        
        .category-item {
            display: flex;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .category-item:last-child {
            border-bottom: none;
        }
        
        .category-name {
            flex: 1;
            font-size: 0.875rem;
        }
        
        .category-bar {
            flex: 2;
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            margin: 0 16px;
            overflow: hidden;
        }
        
        .category-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--success));
            border-radius: 4px;
            transition: width 0.3s;
        }
        
        .category-count {
            font-size: 0.875rem;
            color: var(--text-secondary);
            min-width: 40px;
            text-align: right;
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 48px 24px;
            color: var(--text-muted);
        }
        
        .empty-state .icon {
            font-size: 3rem;
            margin-bottom: 16px;
            opacity: 0.5;
        }
        
        /* Toast Notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 1000;
        }
        
        .toast {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px 20px;
            margin-top: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease;
        }
        
        .toast.success { border-left: 3px solid var(--success); }
        .toast.error { border-left: 3px solid var(--error); }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        /* Loading spinner */
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
        
        /* Refresh button */
        .refresh-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 4px;
            transition: color 0.2s;
        }
        
        .refresh-btn:hover {
            color: var(--accent);
        }
        
        .refresh-btn.spinning {
            animation: spin 1s linear infinite;
        }
        
        /* Search Styles */
        .search-container {
            margin-bottom: 24px;
        }
        
        .search-box {
            display: flex;
            gap: 12px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 16px;
            transition: border-color 0.2s;
        }
        
        .search-box:focus-within {
            border-color: var(--accent);
        }
        
        .search-input {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 1rem;
            outline: none;
        }
        
        .search-input::placeholder {
            color: var(--text-muted);
        }
        
        .search-btn {
            background: var(--accent);
            color: var(--bg-primary);
            border: none;
            padding: 8px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        .search-btn:hover {
            background: var(--accent-hover);
        }
        
        .search-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .search-results {
            margin-top: 16px;
            display: none;
        }
        
        .search-results.active {
            display: block;
        }
        
        .search-interpretation {
            background: var(--bg-card);
            border: 1px solid var(--accent);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            font-size: 0.85rem;
        }
        
        .interpretation-intent {
            color: var(--text-primary);
            margin-bottom: 6px;
        }
        
        .interpretation-expanded {
            color: var(--text-secondary);
            font-size: 0.8rem;
        }
        
        .search-result-item {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            padding: 16px;
            margin: 8px 0;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .search-result-item:hover {
            border-color: var(--accent);
            background: var(--bg-hover);
        }
        
        .result-main {
            flex: 1;
        }
        
        .result-filename {
            font-family: 'Cascadia Code', 'Consolas', monospace;
            font-size: 0.9rem;
            color: var(--text-primary);
            margin-bottom: 6px;
        }
        
        .result-path {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 8px;
        }
        
        .result-snippet {
            font-size: 0.8rem;
            color: var(--text-secondary);
            background: var(--bg-secondary);
            padding: 8px 12px;
            border-radius: 4px;
            margin-top: 8px;
            font-style: italic;
        }
        
        .result-snippet mark {
            background: rgba(34, 211, 238, 0.3);
            color: var(--accent);
            padding: 0 2px;
            border-radius: 2px;
        }
        
        .result-meta {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .match-badge {
            font-size: 0.7rem;
            padding: 3px 8px;
            border-radius: 4px;
            background: rgba(34, 211, 238, 0.15);
            color: var(--accent);
        }
        
        .search-status {
            text-align: center;
            padding: 24px;
            color: var(--text-muted);
        }
        
        .no-results {
            text-align: center;
            padding: 48px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>
                <span class="icon">📁</span>
                Smart Folder Dashboard
            </h1>
            
            <!-- Model Profile Selector -->
            <div class="profile-selector">
                <label for="profileSelect">🤖 Model:</label>
                <select id="profileSelect" onchange="switchProfile(this.value)">
                    <option value="">Loading...</option>
                </select>
                <span id="profileModel" class="profile-model"></span>
            </div>
            
            <div class="status-badge">
                <span class="status-dot" id="statusDot"></span>
                <span id="statusText">Connecting...</span>
            </div>
        </header>
        
        <!-- Search Section -->
        <div class="search-container">
            <div class="search-box">
                <span style="font-size: 1.2rem;">🔍</span>
                <input type="text" 
                       class="search-input" 
                       id="searchInput" 
                       placeholder="Search your documents... (e.g., 'my resumes', 'dental claim', 'tax 2024')"
                       onkeypress="if(event.key==='Enter') searchDocuments()">
                <button class="search-btn" id="searchBtn" onclick="searchDocuments()">Search</button>
            </div>
            <div class="search-results" id="searchResults">
                <!-- Results will be populated here -->
            </div>
        </div>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="stat-value" id="statTotal">-</div>
                <div class="stat-label">Total Documents</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statReview">-</div>
                <div class="stat-label">Needs Review</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statToday">-</div>
                <div class="stat-label">Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="statWeek">-</div>
                <div class="stat-label">This Week</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">
                        ⚠️ Needs Review
                        <span class="card-badge warning" id="reviewBadge">0</span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button class="btn btn-ghost" onclick="selectAllDocs()" title="Select all (Ctrl+A)">
                            ☑️ All
                        </button>
                    <button class="refresh-btn" onclick="loadReviewDocs()" title="Refresh">🔄</button>
                </div>
                </div>
                
                <!-- Batch actions bar -->
                <div class="batch-actions" id="batchActions">
                    <span class="batch-count" id="batchCount">0 selected</span>
                    <button class="btn btn-primary" onclick="batchApprove()">✓ Approve All</button>
                    <button class="btn btn-secondary" onclick="batchReassign()">📁 Move All</button>
                    <button class="btn btn-ghost" onclick="clearSelection()">✕ Clear</button>
                </div>
                
                <div class="card-body" id="reviewList">
                    <div class="empty-state">
                        <div class="icon">✨</div>
                        <p>All documents reviewed!</p>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-title">
                        📋 Recent Activity
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button class="btn btn-ghost" onclick="undoLast()" title="Undo last action" id="undoBtn">
                            ↩️ Undo
                        </button>
                    <button class="refresh-btn" onclick="loadRecentDocs()" title="Refresh">🔄</button>
                    </div>
                </div>
                <div class="card-body" id="recentList">
                    <div class="loading"></div>
                </div>
            </div>
            
            <div class="card" style="grid-column: span 2;">
                <div class="card-header">
                    <div class="card-title">
                        📊 Categories
                    </div>
                </div>
                <div class="card-body" id="categoryStats">
                    <div class="loading"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <script>
        const API_BASE = '';
        
        // Format relative time
        function formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = (now - date) / 1000;
            
            if (diff < 60) return 'just now';
            if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
            if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
            if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
            return date.toLocaleDateString();
        }
        
        // Get confidence class
        function getConfidenceClass(confidence) {
            if (confidence >= 0.8) return 'confidence-high';
            if (confidence >= 0.6) return 'confidence-medium';
            return 'confidence-low';
        }
        
        // Get file icon based on extension
        function getFileIcon(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            const icons = {
                'pdf': '📄',
                'doc': '📝', 'docx': '📝',
                'xls': '📊', 'xlsx': '📊', 'csv': '📊',
                'ppt': '📽️', 'pptx': '📽️',
                'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
                'txt': '📃',
                'zip': '📦', 'rar': '📦', '7z': '📦'
            };
            return icons[ext] || '📁';
        }
        
        // Load thumbnail for a document
        async function loadThumbnail(element) {
            const path = element.dataset.path;
            if (!path) return;
            
            try {
                const res = await fetch(`${API_BASE}/api/thumbnail?path=${encodeURIComponent(path)}`);
                const data = await res.json();
                
                if (data.thumbnail) {
                    element.innerHTML = `<img src="${data.thumbnail}" alt="Preview" loading="lazy">`;
                }
            } catch (err) {
                // Keep placeholder on error
            }
        }
        
        // Load thumbnails for visible documents
        function loadVisibleThumbnails() {
            document.querySelectorAll('.doc-thumbnail[data-path]').forEach(el => {
                if (!el.querySelector('img')) {
                    loadThumbnail(el);
                }
            });
        }
        
        // Toggle document details expansion
        function toggleDocDetails(element) {
            const details = element.querySelector('.doc-details');
            const isExpanded = element.classList.contains('expanded');
            
            if (isExpanded) {
                element.classList.remove('expanded');
                details.style.display = 'none';
            } else {
                element.classList.add('expanded');
                details.style.display = 'block';
            }
        }
        
        // Show toast notification
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <span>${type === 'success' ? '✓' : '✗'}</span>
                <span>${message}</span>
            `;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }
        
        // Load statistics
        async function loadStats() {
            try {
                const res = await fetch(`${API_BASE}/api/stats`);
                const data = await res.json();
                
                document.getElementById('statTotal').textContent = data.total;
                document.getElementById('statReview').textContent = data.needs_review;
                document.getElementById('statToday').textContent = data.today;
                document.getElementById('statWeek').textContent = data.last_week;
                
                // Update category chart
                const maxCount = Math.max(...Object.values(data.by_category), 1);
                const categoryHtml = Object.entries(data.by_category)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cat, count]) => `
                        <li class="category-item">
                            <span class="category-name">${cat}</span>
                            <div class="category-bar">
                                <div class="category-bar-fill" style="width: ${(count / maxCount) * 100}%"></div>
                            </div>
                            <span class="category-count">${count}</span>
                        </li>
                    `).join('');
                
                document.getElementById('categoryStats').innerHTML = 
                    categoryHtml ? `<ul class="category-list">${categoryHtml}</ul>` :
                    '<div class="empty-state"><div class="icon">📁</div><p>No documents yet</p></div>';
                    
            } catch (err) {
                console.error('Failed to load stats:', err);
            }
        }
        
        // Load recent documents
        async function loadRecentDocs() {
            try {
                const res = await fetch(`${API_BASE}/api/recent`);
                const docs = await res.json();
                
                if (docs.length === 0) {
                    document.getElementById('recentList').innerHTML = `
                        <div class="empty-state">
                            <div class="icon">📄</div>
                            <p>No documents processed yet</p>
                        </div>
                    `;
                    return;
                }
                
                const html = docs.map(doc => `
                    <div class="doc-item doc-expandable" onclick="toggleDocDetails(this)">
                        <div class="doc-info">
                            <div class="doc-thumbnail" data-path="${doc.current_path}">
                                <div class="thumbnail-placeholder">${getFileIcon(doc.original_filename)}</div>
                            </div>
                            <div class="doc-text-info">
                            <div class="doc-name" title="${doc.original_filename}">
                                <span class="expand-icon">▶</span>
                                ${doc.original_filename}
                            </div>
                            <div class="doc-meta">
                                <span class="doc-category">
                                    ${doc.category}${doc.subcategory ? '/' + doc.subcategory : ''}
                                </span>
                                <span class="doc-confidence ${getConfidenceClass(doc.confidence)}">
                                    ${Math.round(doc.confidence * 100)}%
                                </span>
                                <span class="doc-time">${formatTime(doc.processed_at)}</span>
                                </div>
                            </div>
                        </div>
                        <div class="doc-details" style="display: none;">
                            <div class="ai-analysis">
                                <div class="analysis-section">
                                    <span class="analysis-label">AI Summary:</span>
                                    <span class="analysis-value">${doc.content_summary || 'Not available'}</span>
                                </div>
                                <div class="analysis-section">
                                    <span class="analysis-label">Document Type:</span>
                                    <span class="analysis-value">${doc.document_type || 'Unknown'}</span>
                                </div>
                                <div class="analysis-section">
                                    <span class="analysis-label">Reasoning:</span>
                                    <span class="analysis-value">${doc.reasoning || 'Not available'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');
                
                document.getElementById('recentList').innerHTML = `<ul class="doc-list">${html}</ul>`;
                
                // Load thumbnails after a short delay
                setTimeout(loadVisibleThumbnails, 100);
                
            } catch (err) {
                console.error('Failed to load recent docs:', err);
            }
        }
        
        // Load documents needing review
        async function loadReviewDocs() {
            try {
                const res = await fetch(`${API_BASE}/api/review`);
                const docs = await res.json();
                
                document.getElementById('reviewBadge').textContent = docs.length;
                
                if (docs.length === 0) {
                    document.getElementById('reviewList').innerHTML = `
                        <div class="empty-state">
                            <div class="icon">✨</div>
                            <p>All documents reviewed!</p>
                        </div>
                    `;
                    return;
                }
                
                // Get categories for select
                const catsRes = await fetch(`${API_BASE}/api/categories`);
                const categories = await catsRes.json();
                
                const catOptions = categories.map(c => `<option value="${c}">${c}</option>`).join('');
                
                const html = docs.map(doc => `
                    <div class="doc-item" id="review-${doc.id}">
                        <div class="doc-main">
                            <input type="checkbox" class="doc-checkbox" data-doc-id="${doc.id}"
                                   onclick="toggleDocSelection(${doc.id}, this, event)">
                            <div class="doc-info">
                                <div class="doc-name" title="${doc.original_filename}">${doc.original_filename}</div>
                                <div class="doc-meta">
                                    <span class="doc-category">${doc.category}</span>
                                    <span class="doc-confidence ${getConfidenceClass(doc.confidence)}">
                                        ${Math.round(doc.confidence * 100)}%
                                    </span>
                                </div>
                            </div>
                            <div class="doc-actions">
                                <select class="category-select" id="cat-${doc.id}" onclick="event.stopPropagation()">
                                    ${catOptions}
                                </select>
                                <button class="btn btn-primary" onclick="event.stopPropagation(); reassignDoc(${doc.id})">
                                    Move
                                </button>
                                <button class="btn btn-ghost" onclick="event.stopPropagation(); approveDoc(${doc.id})">
                                    OK
                                </button>
                            </div>
                        </div>
                        <div class="review-analysis">
                            <div class="analysis-section">
                                <span class="analysis-label">AI Summary:</span>
                                <span class="analysis-value">${doc.content_summary || 'Not available'}</span>
                            </div>
                            <div class="analysis-section">
                                <span class="analysis-label">Why this classification:</span>
                                <span class="analysis-value">${doc.reasoning || 'Not available'}</span>
                            </div>
                        </div>
                    </div>
                `).join('');
                
                document.getElementById('reviewList').innerHTML = `<ul class="doc-list">${html}</ul>`;
                
            } catch (err) {
                console.error('Failed to load review docs:', err);
            }
        }
        
        // Reassign document
        async function reassignDoc(docId) {
            const category = document.getElementById(`cat-${docId}`).value;
            
            try {
                const res = await fetch(`${API_BASE}/api/reassign`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doc_id: docId, category: category })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast(`Moved to ${category}`);
                    document.getElementById(`review-${docId}`).remove();
                    loadStats();
                    loadRecentDocs();
                    
                    // Check if review list is empty
                    const remaining = document.querySelectorAll('[id^="review-"]').length;
                    document.getElementById('reviewBadge').textContent = remaining;
                    if (remaining === 0) {
                        loadReviewDocs();
                    }
                } else {
                    showToast(data.error || 'Failed to move', 'error');
                }
            } catch (err) {
                showToast('Failed to reassign', 'error');
            }
        }
        
        // Approve document as-is
        async function approveDoc(docId) {
            try {
                const res = await fetch(`${API_BASE}/api/approve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doc_id: docId })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast('Approved');
                    document.getElementById(`review-${docId}`).remove();
                    loadStats();
                    
                    const remaining = document.querySelectorAll('[id^="review-"]').length;
                    document.getElementById('reviewBadge').textContent = remaining;
                    if (remaining === 0) {
                        loadReviewDocs();
                    }
                }
            } catch (err) {
                showToast('Failed to approve', 'error');
            }
        }
        
        // Undo functionality
        async function undoLast() {
            const undoBtn = document.getElementById('undoBtn');
            undoBtn.disabled = true;
            undoBtn.textContent = '↩️ Undoing...';
            
            try {
                const res = await fetch(`${API_BASE}/api/undo-last`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast(`Undone: ${data.filename} moved back`);
                    loadStats();
                    loadRecentDocs();
                    loadReviewDocs();
                } else {
                    showToast(data.error || 'Nothing to undo', 'error');
                }
            } catch (err) {
                showToast('Undo failed', 'error');
            } finally {
                undoBtn.disabled = false;
                undoBtn.textContent = '↩️ Undo';
            }
        }
        
        async function undoAction(actionId) {
            try {
                const res = await fetch(`${API_BASE}/api/undo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action_id: actionId })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast(`Undone: ${data.filename}`);
                    loadStats();
                    loadRecentDocs();
                } else {
                    showToast(data.error || 'Undo failed', 'error');
                }
            } catch (err) {
                showToast('Undo failed', 'error');
            }
        }
        
        // ========================================
        // Batch Operations
        // ========================================
        
        let selectedDocIds = new Set();
        
        function toggleDocSelection(docId, checkbox, event) {
            if (event) event.stopPropagation();
            
            if (checkbox.checked) {
                selectedDocIds.add(docId);
            } else {
                selectedDocIds.delete(docId);
            }
            
            // Update visual selection
            const docItem = checkbox.closest('.doc-item');
            if (docItem) {
                docItem.classList.toggle('selected', checkbox.checked);
            }
            
            updateBatchActions();
        }
        
        function updateBatchActions() {
            const batchBar = document.getElementById('batchActions');
            const countSpan = document.getElementById('batchCount');
            
            if (selectedDocIds.size > 0) {
                batchBar.classList.add('visible');
                countSpan.textContent = `${selectedDocIds.size} selected`;
            } else {
                batchBar.classList.remove('visible');
            }
        }
        
        function selectAllDocs() {
            const checkboxes = document.querySelectorAll('.doc-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = true;
                const docId = parseInt(cb.dataset.docId);
                if (docId) selectedDocIds.add(docId);
                cb.closest('.doc-item')?.classList.add('selected');
            });
            updateBatchActions();
        }
        
        function clearSelection() {
            selectedDocIds.clear();
            document.querySelectorAll('.doc-checkbox').forEach(cb => {
                cb.checked = false;
                cb.closest('.doc-item')?.classList.remove('selected');
            });
            updateBatchActions();
        }
        
        async function batchApprove() {
            if (selectedDocIds.size === 0) return;
            
            const res = await fetch(`${API_BASE}/api/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'approve', doc_ids: Array.from(selectedDocIds) })
            });
            
            const data = await res.json();
            showToast(`Approved ${data.processed} documents`);
            clearSelection();
            loadStats();
            loadReviewDocs();
            loadRecentDocs();
        }
        
        async function batchReassign() {
            if (selectedDocIds.size === 0) return;
            
            const category = prompt('Enter category name:');
            if (!category) return;
            
            const subcategory = prompt('Enter subcategory (optional):') || '';
            
            const res = await fetch(`${API_BASE}/api/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    action: 'reassign', 
                    doc_ids: Array.from(selectedDocIds),
                    category: category,
                    subcategory: subcategory
                })
            });
            
            const data = await res.json();
            showToast(`Moved ${data.processed} documents to ${category}`);
            clearSelection();
            loadStats();
            loadReviewDocs();
            loadRecentDocs();
        }
        
        // ========================================
        // Keyboard Shortcuts
        // ========================================
        
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts when typing in inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            // Ctrl/Cmd + Z = Undo
            if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
                e.preventDefault();
                undoLast();
            }
            
            // Ctrl/Cmd + A = Select all (when in review tab)
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                e.preventDefault();
                selectAllDocs();
            }
            
            // Escape = Clear selection
            if (e.key === 'Escape') {
                clearSelection();
            }
            
            // R = Refresh
            if (e.key === 'r' && !e.ctrlKey && !e.metaKey) {
                loadStats();
                loadRecentDocs();
                loadReviewDocs();
                showToast('Refreshed');
            }
            
            // 1 = Dashboard tab
            if (e.key === '1') {
                document.querySelector('[data-tab="dashboard"]')?.click();
            }
            
            // 2 = Review tab  
            if (e.key === '2') {
                document.querySelector('[data-tab="review"]')?.click();
            }
            
            // 3 = Search tab
            if (e.key === '3') {
                document.querySelector('[data-tab="search"]')?.click();
            }
            
            // / = Focus search
            if (e.key === '/') {
                e.preventDefault();
                document.getElementById('searchInput')?.focus();
            }
        });
        
        // Check status
        async function checkStatus() {
            try {
                const res = await fetch(`${API_BASE}/api/status`);
                const data = await res.json();
                
                const dot = document.getElementById('statusDot');
                const text = document.getElementById('statusText');
                
                if (data.running) {
                    dot.classList.remove('offline');
                    
                    // Show batch progress if processing
                    if (data.batch && data.batch.is_processing) {
                        const done = data.batch.processed + data.batch.failed;
                        const total = data.batch.total_queued;
                        const pending = data.batch.pending + data.batch.retry_pending;
                        
                        if (data.batch.current_file) {
                            // Currently processing a specific file
                            const filename = data.batch.current_file.length > 25 ? 
                                data.batch.current_file.substring(0, 22) + '...' : data.batch.current_file;
                            text.innerHTML = `Processing: <strong>${filename}</strong>`;
                        } else if (total > 0 && pending > 0) {
                            const pct = Math.round((done / total) * 100);
                            text.innerHTML = `Processing: <strong>${done}/${total}</strong> (${pct}%)`;
                        } else if (pending > 0) {
                            text.innerHTML = `Queue: <strong>${pending}</strong> pending`;
                        } else {
                            text.textContent = 'Processing...';
                        }
                    } else if (data.batch && data.batch.pending > 0) {
                        text.innerHTML = `Queue: <strong>${data.batch.pending}</strong> files`;
                    } else {
                        text.textContent = data.lmstudio ? 'Running' : 'LMStudio Offline';
                    }
                } else {
                    dot.classList.add('offline');
                    text.textContent = 'Offline';
                }
            } catch (err) {
                document.getElementById('statusDot').classList.add('offline');
                document.getElementById('statusText').textContent = 'Disconnected';
            }
        }
        
        // Search documents
        async function searchDocuments() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;
            
            const searchBtn = document.getElementById('searchBtn');
            const resultsDiv = document.getElementById('searchResults');
            
            // Show loading state
            searchBtn.disabled = true;
            searchBtn.textContent = 'Searching...';
            resultsDiv.classList.add('active');
            resultsDiv.innerHTML = '<div class="search-status"><div class="loading"></div><p>Understanding your query...</p></div>';
            
            try {
                const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                
                if (data.results && data.results.length > 0) {
                    const html = data.results.map(doc => {
                        let snippet = '';
                        if (doc.match_snippet) {
                            // Highlight search terms in snippet
                            let highlightedSnippet = doc.match_snippet;
                            if (data.search_terms) {
                                data.search_terms.forEach(term => {
                                    try {
                                        // Simple case-insensitive replacement without regex
                                        const termLower = term.toLowerCase();
                                        const snippetLower = highlightedSnippet.toLowerCase();
                                        let idx = snippetLower.indexOf(termLower);
                                        while (idx !== -1) {
                                            const original = highlightedSnippet.substr(idx, term.length);
                                            highlightedSnippet = highlightedSnippet.substring(0, idx) + 
                                                '<mark>' + original + '</mark>' + 
                                                highlightedSnippet.substring(idx + term.length);
                                            idx = highlightedSnippet.toLowerCase().indexOf(termLower, idx + 13 + term.length);
                                        }
                                    } catch (e) {}
                                });
                            }
                            snippet = `<div class="result-snippet">${highlightedSnippet}</div>`;
                        }
                        
                        const matchType = doc.match_type.split(':')[0].replace('_', ' ');
                        
                        return `
                            <div class="search-result-item" data-path="${encodeURIComponent(doc.current_path)}" onclick="openDocumentFromElement(this)">
                                <div class="result-main">
                                    <div class="result-filename">${doc.filename}</div>
                                    <div class="result-path">${doc.category}${doc.subcategory ? '/' + doc.subcategory : ''}</div>
                                    <div class="result-meta">
                                        <span class="doc-category">${doc.document_type || doc.category}</span>
                                        <span class="match-badge">${matchType}</span>
                                    </div>
                                    ${snippet}
                                </div>
                            </div>
                        `;
                    }).join('');
                    
                    // Build search interpretation display
                    let interpretationHtml = '';
                    if (data.intent || data.expanded_terms) {
                        interpretationHtml = `
                            <div class="search-interpretation">
                                ${data.intent ? `<div class="interpretation-intent">🧠 <strong>Understanding:</strong> ${data.intent}</div>` : ''}
                                ${data.expanded_terms && data.expanded_terms.length > 0 ? 
                                    `<div class="interpretation-expanded">🔍 <strong>Also searching:</strong> ${data.expanded_terms.slice(0, 10).join(', ')}${data.expanded_terms.length > 10 ? '...' : ''}</div>` 
                                    : ''}
                            </div>
                        `;
                    }
                    
                    resultsDiv.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span style="color: var(--text-secondary);">${data.results.length} result(s) found</span>
                            <button class="btn btn-ghost" onclick="clearSearch()">Clear</button>
                        </div>
                        ${interpretationHtml}
                        ${html}
                    `;
                } else {
                    resultsDiv.innerHTML = `
                        <div class="no-results">
                            <div style="font-size: 2rem; margin-bottom: 12px;">🔍</div>
                            <p>No documents found matching "${query}"</p>
                            <p style="font-size: 0.8rem; margin-top: 8px;">Try different keywords or check your document categories</p>
                        </div>
                    `;
                }
                
            } catch (err) {
                console.error('Search failed:', err);
                resultsDiv.innerHTML = '<div class="search-status" style="color: var(--error);">Search failed. Please try again.</div>';
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = 'Search';
            }
        }
        
        function clearSearch() {
            document.getElementById('searchInput').value = '';
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchResults').innerHTML = '';
        }
        
        function openDocumentFromElement(element) {
            const path = decodeURIComponent(element.dataset.path);
            openDocument(path);
        }
        
        function openDocument(path) {
            // Open the containing folder in Windows Explorer
            fetch(`${API_BASE}/api/open-folder`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            }).then(() => {
                showToast('Opening folder...');
            }).catch(() => {
                // Fallback: copy path to clipboard
                navigator.clipboard.writeText(path).then(() => {
                    showToast('Path copied to clipboard');
                });
            });
        }
        
        // Profile Management
        let currentProfiles = {};
        
        function loadProfiles() {
            fetch(`${API_BASE}/api/profiles`)
                .then(r => r.json())
                .then(data => {
                    currentProfiles = data.profiles || {};
                    const select = document.getElementById('profileSelect');
                    const modelSpan = document.getElementById('profileModel');
                    
                    // Build options
                    select.innerHTML = '';
                    for (const [name, profile] of Object.entries(currentProfiles)) {
                        const opt = document.createElement('option');
                        opt.value = name;
                        opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
                        if (data.current && name === data.current.name) {
                            opt.selected = true;
                        }
                        select.appendChild(opt);
                    }
                    
                    // Show current model
                    if (data.current) {
                        modelSpan.textContent = data.current.model;
                        modelSpan.title = data.current.description || '';
                    }
                })
                .catch(e => {
                    console.error('Failed to load profiles:', e);
                    document.getElementById('profileSelect').innerHTML = 
                        '<option value="">Error loading</option>';
                });
        }
        
        function switchProfile(profileName) {
            if (!profileName) return;
            
            const select = document.getElementById('profileSelect');
            const modelSpan = document.getElementById('profileModel');
            
            // Show loading state
            select.disabled = true;
            modelSpan.textContent = 'Switching...';
            
            fetch(`${API_BASE}/api/profile`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profile: profileName })
            })
            .then(r => r.json())
            .then(data => {
                select.disabled = false;
                if (data.success) {
                    modelSpan.textContent = data.profile.model;
                    modelSpan.title = data.profile.description || '';
                    showToast(`Switched to ${profileName} profile`);
                } else {
                    showToast(`Failed: ${data.error}`, true);
                    loadProfiles(); // Reload to reset
                }
            })
            .catch(e => {
                select.disabled = false;
                showToast('Failed to switch profile', true);
                loadProfiles();
            });
        }
        
        // Initial load
        loadStats();
        loadRecentDocs();
        loadReviewDocs();
        checkStatus();
        loadProfiles();
        
        // Auto-refresh
        setInterval(loadStats, 30000);
        setInterval(loadRecentDocs, 15000);
        setInterval(loadReviewDocs, 15000);
        setInterval(checkStatus, 10000);
    </script>
</body>
</html>
'''


class DashboardServer:
    """
    Flask-based dashboard server.
    
    Runs in a background thread alongside the main watcher.
    """
    
    def __init__(
        self,
        config: Config,
        database: DocumentDatabase,
        port: int = 5000
    ):
        """Initialize the dashboard server."""
        self.config = config
        self.database = database
        self.port = port
        self.app = Flask(__name__)
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._lmstudio_status = False
        self._llm_client = None  # Set later via set_llm_client()
        self._watcher = None     # Set later via set_watcher()
        
        # Initialize thumbnail generator
        try:
            from .thumbnail import ThumbnailGenerator
            cache_dir = config.folders.base_path / '.sift_cache' / 'thumbnails'
            self._thumbnail_generator = ThumbnailGenerator(cache_dir)
            if self._thumbnail_generator.is_available:
                logger.debug("Thumbnail generation enabled")
            else:
                self._thumbnail_generator = None
        except ImportError:
            self._thumbnail_generator = None
            logger.debug("Thumbnail generation not available")
        
        # Disable Flask's default logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
        
        self._setup_routes()
    
    def set_watcher(self, watcher) -> None:
        """Set the document watcher for batch status reporting."""
        self._watcher = watcher
    
    def _setup_routes(self):
        """Set up Flask routes."""
        app = self.app
        
        @app.route('/')
        def index():
            return render_template_string(DASHBOARD_HTML)
        
        @app.route('/api/stats')
        def api_stats():
            stats = self.database.get_statistics()
            return jsonify(stats)
        
        @app.route('/api/recent')
        def api_recent():
            docs = self.database.get_recent_documents(20)
            return jsonify([d.to_dict() for d in docs])
        
        @app.route('/api/review')
        def api_review():
            docs = self.database.get_documents_needing_review()
            return jsonify([d.to_dict() for d in docs])
        
        @app.route('/api/categories')
        def api_categories():
            # Get categories from actual disk structure, not config
            excluded = {'inbox', '.temp', 'temp', 'needs_review'}
            categories = []
            base_path = self.config.folders.base_path
            
            if base_path.exists():
                try:
                    for item in base_path.iterdir():
                        if item.is_dir() and not item.name.startswith('.'):
                            if item.name.lower() in excluded:
                                continue
                            categories.append(item.name)
                except Exception as e:
                    logger.warning(f"Error scanning categories: {e}")
            
            return jsonify(sorted(categories))
        
        @app.route('/api/status')
        def api_status():
            status = {
                'running': self._is_running,
                'lmstudio': self._lmstudio_status
            }
            
            # Add batch processing status if watcher is available
            if self._watcher:
                batch_status = self._watcher.get_batch_status()
                status['batch'] = batch_status
            
            return jsonify(status)
        
        @app.route('/api/reassign', methods=['POST'])
        def api_reassign():
            from .utils import sanitize_folder_name
            
            data = request.get_json()
            doc_id = data.get('doc_id')
            category = data.get('category', '')
            subcategory = data.get('subcategory', '')
            
            if not doc_id or not category:
                return jsonify({'success': False, 'error': 'Missing parameters'})
            
            # Security: Sanitize folder names to prevent path traversal
            category = sanitize_folder_name(category)
            subcategory = sanitize_folder_name(subcategory) if subcategory else ''
            
            # Security: Block obvious path traversal attempts
            if '..' in category or '..' in subcategory:
                return jsonify({'success': False, 'error': 'Invalid folder name'})
            
            # Get the document
            doc = self.database.get_document_by_id(doc_id)
            if not doc:
                return jsonify({'success': False, 'error': 'Document not found'})
            
            # Calculate new path
            current_path = Path(doc.current_path)
            if not current_path.exists():
                return jsonify({'success': False, 'error': 'File not found on disk'})
            
            # Security: Verify new path is within base folder
            new_folder = self.config.folders.base_path / category
            if subcategory:
                new_folder = new_folder / subcategory
            
            # Resolve and verify path is within bounds
            base_resolved = self.config.folders.base_path.resolve()
            new_folder_resolved = new_folder.resolve()
            if not str(new_folder_resolved).startswith(str(base_resolved)):
                return jsonify({'success': False, 'error': 'Access denied: path outside Sift folder'})
            
            new_folder.mkdir(parents=True, exist_ok=True)
            
            new_path = new_folder / current_path.name
            
            # Handle duplicates
            if new_path.exists():
                stem = new_path.stem
                suffix = new_path.suffix
                counter = 1
                while new_path.exists():
                    new_path = new_folder / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            try:
                shutil.move(str(current_path), str(new_path))
                self.database.update_document_location(
                    doc_id, str(new_path), category, subcategory, 'manual_override'
                )
                
                # Record the correction for learning
                if doc.category != category or doc.subcategory != subcategory:
                    self.database.record_correction(
                        document_id=doc.id,
                        original_category=doc.category,
                        original_subcategory=doc.subcategory,
                        corrected_category=category,
                        corrected_subcategory=subcategory,
                        document_type=doc.document_type,
                        content_snippet=getattr(doc, 'content_summary', ''),
                        filename=doc.original_filename
                    )
                
                logger.info(f"Reassigned {doc.original_filename} to {category}/{subcategory}")
                return jsonify({'success': True, 'new_path': str(new_path)})
            except Exception as e:
                logger.error(f"Failed to reassign document: {e}")
                return jsonify({'success': False, 'error': str(e)})
        
        @app.route('/api/approve', methods=['POST'])
        def api_approve():
            data = request.get_json()
            doc_id = data.get('doc_id')
            
            if not doc_id:
                return jsonify({'success': False, 'error': 'Missing doc_id'})
            
            doc = self.database.get_document_by_id(doc_id)
            if not doc:
                return jsonify({'success': False, 'error': 'Document not found'})
            
            # Update status to approved
            self.database.update_document_location(
                doc_id,
                doc.current_path,
                doc.category,
                doc.subcategory,
                'processed'
            )
            
            return jsonify({'success': True})
        
        @app.route('/api/undo-history')
        def api_undo_history():
            """Get list of undoable actions."""
            limit = request.args.get('limit', 10, type=int)
            actions = self.database.get_undoable_actions(limit)
            return jsonify({'actions': actions})
        
        @app.route('/api/undo', methods=['POST'])
        def api_undo():
            """Undo a specific action."""
            data = request.get_json()
            action_id = data.get('action_id')
            
            if not action_id:
                return jsonify({'success': False, 'error': 'Missing action_id'})
            
            result = self.database.undo_action(action_id)
            return jsonify(result)
        
        @app.route('/api/undo-last', methods=['POST'])
        def api_undo_last():
            """Undo the most recent action."""
            last_action = self.database.get_last_action()
            
            if not last_action:
                return jsonify({'success': False, 'error': 'No actions to undo'})
            
            result = self.database.undo_action(last_action['id'])
            return jsonify(result)
        
        @app.route('/api/batch', methods=['POST'])
        def api_batch():
            """Perform batch operations on multiple documents."""
            from .utils import sanitize_folder_name
            
            data = request.get_json()
            action = data.get('action')
            doc_ids = data.get('doc_ids', [])
            
            if not action or not doc_ids:
                return jsonify({'success': False, 'error': 'Missing action or doc_ids'})
            
            results = {'success': True, 'processed': 0, 'failed': 0, 'errors': []}
            
            if action == 'approve':
                # Batch approve documents
                for doc_id in doc_ids:
                    try:
                        doc = self.database.get_document_by_id(doc_id)
                        if doc:
                            self.database.update_document_location(
                                doc_id, doc.current_path, doc.category,
                                doc.subcategory, 'processed'
                            )
                            results['processed'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append(f"Doc {doc_id} not found")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))
                        
            elif action == 'reassign':
                # Batch move documents to a category
                category = sanitize_folder_name(data.get('category', ''))
                subcategory = sanitize_folder_name(data.get('subcategory', ''))
                
                if not category:
                    return jsonify({'success': False, 'error': 'Missing category'})
                
                for doc_id in doc_ids:
                    try:
                        doc = self.database.get_document_by_id(doc_id)
                        if not doc:
                            results['failed'] += 1
                            continue
                        
                        current_path = Path(doc.current_path)
                        if not current_path.exists():
                            results['failed'] += 1
                            continue
                        
                        new_folder = self.config.folders.base_path / category
                        if subcategory:
                            new_folder = new_folder / subcategory
                        new_folder.mkdir(parents=True, exist_ok=True)
                        
                        new_path = new_folder / current_path.name
                        if new_path.exists():
                            counter = 1
                            while new_path.exists():
                                new_path = new_folder / f"{current_path.stem}_{counter}{current_path.suffix}"
                                counter += 1
                        
                        shutil.move(str(current_path), str(new_path))
                        self.database.update_document_location(
                            doc_id, str(new_path), category, subcategory, 'manual_override'
                        )
                        
                        # Record correction for learning
                        if doc.category != category or doc.subcategory != subcategory:
                            self.database.record_correction(
                                document_id=doc.id,
                                original_category=doc.category,
                                original_subcategory=doc.subcategory,
                                corrected_category=category,
                                corrected_subcategory=subcategory,
                                document_type=doc.document_type,
                                filename=doc.original_filename
                            )
                        
                        results['processed'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))
                        
            elif action == 'delete':
                # Batch delete (move to trash/review for safety)
                for doc_id in doc_ids:
                    try:
                        doc = self.database.get_document_by_id(doc_id)
                        if doc:
                            current_path = Path(doc.current_path)
                            if current_path.exists():
                                # Move to Needs_Review instead of deleting
                                review_folder = self.config.folders.base_path / 'Needs_Review'
                                review_folder.mkdir(parents=True, exist_ok=True)
                                new_path = review_folder / current_path.name
                                shutil.move(str(current_path), str(new_path))
                                self.database.update_document_location(
                                    doc_id, str(new_path), 'Needs_Review', '', 'deleted'
                                )
                            results['processed'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))
            else:
                return jsonify({'success': False, 'error': f'Unknown action: {action}'})
            
            results['success'] = results['failed'] == 0
            return jsonify(results)
        
        @app.route('/api/search')
        def api_search():
            query = request.args.get('q', '').strip()
            if not query:
                return jsonify({'results': [], 'search_terms': []})
            
            # Use LLM to parse and expand query
            search_terms = None
            expanded_terms = []
            category_hint = None
            intent = ''
            
            if self._llm_client and self._lmstudio_status:
                try:
                    parsed = self._llm_client.parse_search_query(query)
                    search_terms = parsed.get('search_terms', [])
                    expanded_terms = parsed.get('expanded_terms', [])
                    category_hint = parsed.get('category_hint')
                    intent = parsed.get('intent', '')
                    logger.info(f"Search expanded: {len(search_terms)} terms, category={category_hint}")
                except Exception as e:
                    logger.warning(f"LLM query parsing failed: {e}")
            
            # Fallback: simple word extraction
            if not search_terms:
                stop_words = {'the', 'a', 'an', 'is', 'are', 'my', 'your', 'where', 
                              'what', 'find', 'show', 'get', 'pull', 'up', 'me',
                              'document', 'file', 'stuff', 'thing', 'all', 'has'}
                search_terms = [w.lower() for w in query.split() 
                               if w.lower() not in stop_words and len(w) > 2]
            
            # Search the database
            results = self.database.search_documents(
                query=query,
                search_terms=search_terms,
                category_hint=category_hint,
                limit=20
            )
            
            return jsonify({
                'results': results,
                'search_terms': search_terms,
                'expanded_terms': expanded_terms,
                'intent': intent,
                'category_hint': category_hint,
                'query': query
            })
        
        @app.route('/api/thumbnail')
        def api_thumbnail():
            """Generate and return a thumbnail for a document."""
            path = request.args.get('path', '')
            
            if not path:
                return jsonify({'error': 'No path provided'}), 400
            
            from pathlib import Path as PathLib
            try:
                resolved_path = PathLib(path).resolve()
                # Security: Only allow paths within Sift base folder
                base_resolved = self.config.folders.base_path.resolve()
                if not str(resolved_path).startswith(str(base_resolved)):
                    return jsonify({'error': 'Access denied'}), 403
                if not resolved_path.exists():
                    return jsonify({'error': 'File not found'}), 404
            except Exception:
                return jsonify({'error': 'Invalid path'}), 400
            
            # Generate thumbnail
            if self._thumbnail_generator:
                thumbnail = self._thumbnail_generator.get_thumbnail(resolved_path)
                if thumbnail:
                    return jsonify({'thumbnail': thumbnail})
            
            return jsonify({'thumbnail': None})
        
        @app.route('/api/open-folder', methods=['POST'])
        def api_open_folder():
            import subprocess
            import sys
            data = request.get_json()
            path = data.get('path', '')
            
            if not path:
                return jsonify({'success': False, 'error': 'No path provided'})
            
            # Security: Validate path exists and is within allowed directories
            from pathlib import Path as PathLib
            try:
                resolved_path = PathLib(path).resolve()
                # Only allow paths within the Sift base folder
                base_resolved = self.config.folders.base_path.resolve()
                if not str(resolved_path).startswith(str(base_resolved)):
                    return jsonify({'success': False, 'error': 'Access denied: path outside Sift folder'})
                if not resolved_path.exists():
                    return jsonify({'success': False, 'error': 'File not found'})
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid path'})
            
            try:
                # Open file explorer - use array form to avoid shell injection
                if sys.platform == 'win32':
                    # Windows: use explorer with /select
                    subprocess.run(['explorer', '/select,', str(resolved_path)], check=False)
                elif sys.platform == 'darwin':
                    # macOS: use open -R to reveal in Finder
                    subprocess.run(['open', '-R', str(resolved_path)], check=True)
                else:
                    # Linux: open containing folder
                    subprocess.run(['xdg-open', str(resolved_path.parent)], check=True)
                return jsonify({'success': True})
            except Exception as e:
                logger.error(f"Failed to open folder: {e}")
                return jsonify({'success': False, 'error': str(e)})
        
        @app.route('/api/profiles')
        def api_profiles():
            """Get all available model profiles."""
            if not self._llm_client:
                return jsonify({'profiles': {}, 'current': None})
            
            profiles = self._llm_client.get_available_profiles()
            current = self._llm_client.get_current_profile()
            
            return jsonify({
                'profiles': profiles,
                'current': current
            })
        
        @app.route('/api/profile', methods=['POST'])
        def api_set_profile():
            """Switch to a different model profile."""
            data = request.get_json()
            profile_name = data.get('profile')
            
            if not profile_name:
                return jsonify({'success': False, 'error': 'No profile specified'})
            
            if not self._llm_client:
                return jsonify({'success': False, 'error': 'LLM client not available'})
            
            # Switch the profile
            success = self._llm_client.switch_profile(profile_name)
            
            if success:
                # Save to settings.yaml for persistence
                self._save_profile_to_config(profile_name)
                
                return jsonify({
                    'success': True,
                    'profile': self._llm_client.get_current_profile()
                })
            else:
                return jsonify({'success': False, 'error': f'Unknown profile: {profile_name}'})
    
    def _save_profile_to_config(self, profile_name: str):
        """Save the active profile to settings.yaml."""
        try:
            config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
            
            if not config_path.exists():
                logger.warning("Settings file not found, can't persist profile change")
                return
            
            # Read the file
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update the active_profile line
            import re
            new_content = re.sub(
                r'(active_profile:\s*)["\']?\w+["\']?',
                f'active_profile: "{profile_name}"',
                content
            )
            
            # Write back
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logger.info(f"Saved profile '{profile_name}' to settings.yaml")
            
        except Exception as e:
            logger.error(f"Failed to save profile to config: {e}")
    
    def set_llm_client(self, llm_client):
        """Set the LLM client for search query parsing."""
        self._llm_client = llm_client
    
    def set_status(self, running: bool, lmstudio: bool = False):
        """Update the status indicators."""
        self._is_running = running
        self._lmstudio_status = lmstudio
    
    def start(self, open_browser: bool = True):
        """Start the dashboard server in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Dashboard already running")
            return
        
        def run_server():
            self.app.run(
                host='127.0.0.1',
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        
        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()
        
        logger.info(f"Dashboard started at http://localhost:{self.port}")
        
        if open_browser:
            # Give the server a moment to start
            import time
            time.sleep(0.5)
            webbrowser.open(f'http://localhost:{self.port}')
    
    def stop(self):
        """Stop the dashboard server."""
        # Flask doesn't have a clean shutdown in threaded mode
        # but since it's a daemon thread, it will stop when the main program exits
        logger.info("Dashboard stopped")

