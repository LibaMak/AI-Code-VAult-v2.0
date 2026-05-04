# ============================================================================
# REPOSITORY SCANNER - Git Repository Analysis & Chunking
# ============================================================================

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any

def _log_debug(message: str):
    """Log debug messages."""
    print(f"[SCANNER_DEBUG] {message}")

def get_repo_chunks(repo_path: str, max_chunk_size: int = 2000) -> List[Dict[str, Any]]:
    """
    Scan a repository and create code chunks for indexing.
    
    Args:
        repo_path: Path to the repository
        max_chunk_size: Maximum characters per chunk
        
    Returns:
        List of code chunks with metadata
    """
    chunks = []
    supported_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.go', '.rb', '.php'}
    
    try:
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common exclusions
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                if ext in supported_extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Split into chunks
                        if len(content) > max_chunk_size:
                            chunk_lines = []
                            current_chunk = ""
                            for line in content.split('\n'):
                                if len(current_chunk) + len(line) > max_chunk_size:
                                    if current_chunk:
                                        chunk_lines.append(current_chunk)
                                    current_chunk = line
                                else:
                                    current_chunk += line + "\n"
                            if current_chunk:
                                chunk_lines.append(current_chunk)
                        else:
                            chunk_lines = [content]
                        
                        for idx, chunk in enumerate(chunk_lines):
                            chunks.append({
                                'name': file,
                                'path': file_path,
                                'type': ext,
                                'snippet': chunk[:max_chunk_size],
                                'chunk_id': idx,
                                'language': ext_to_language(ext)
                            })
                    except Exception as e:
                        _log_debug(f"Error reading {file_path}: {str(e)}")
                        continue
        
        _log_debug(f"Scanned {len(chunks)} code chunks")
    except Exception as e:
        _log_debug(f"Error scanning repository: {str(e)}")
    
    return chunks

def ext_to_language(ext: str) -> str:
    """Convert file extension to language name."""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php'
    }
    return ext_map.get(ext, 'text')

def analyze_code_metrics(code_snippet: str) -> Dict[str, Any]:
    """
    Analyze code snippet for complexity metrics.
    
    Args:
        code_snippet: Source code to analyze
        
    Returns:
        Dictionary with metrics
    """
    lines = code_snippet.split('\n')
    
    # Count metrics
    loc = len(lines)
    code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    complexity = estimate_complexity(code_snippet)
    functions = len(re.findall(r'def |function |func ', code_snippet))
    classes = len(re.findall(r'class ', code_snippet))
    
    return {
        'lines_of_code': loc,
        'code_lines': code_lines,
        'complexity_estimate': complexity,
        'functions': functions,
        'classes': classes
    }

def estimate_complexity(code: str) -> str:
    """Estimate cyclomatic complexity (Low/Medium/High)."""
    # Simple heuristic based on control flow keywords
    keywords = ['if', 'else', 'for', 'while', 'try', 'except', 'switch', 'case']
    count = sum(len(re.findall(rf'\b{kw}\b', code)) for kw in keywords)
    
    if count < 5:
        return 'Low'
    elif count < 15:
        return 'Medium'
    else:
        return 'High'
