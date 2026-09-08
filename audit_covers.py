#!/usr/bin/env python3
"""
Diagnostic script to audit the game cover system in GameUnexa.
"""

import os
import re
import json
from pathlib import Path
from PIL import Image
from paths import CACHE_DIR, DB_PATH

# Configuration
CACHE_DIR = CACHE_DIR / 'covers'

def normalize_title_for_cache(titulo: str) -> str:
    """Normalizes title the same way app.py does."""
    texto = (titulo or '').strip()
    texto = texto.replace('™', '').replace('®', '').replace('_', ' ')
    texto = re.sub(r'\b(edition|definitive edition|complete edition|deluxe edition|remastered|goty|gold edition|ultimate edition|hd|remake|demo|beta|alpha|early access)\b', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\b(19\d{2}|20\d{2})\b', '', texto)
    texto = re.sub(r'[^\w\s]+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'\b(the|and)\b', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'\b([ivx]+)\b', lambda m: m.group(1).lower(), texto, flags=re.IGNORECASE)
    if texto.lower().endswith(' edition'):
        texto = texto[:-8].strip()
    return texto

def normalize_for_filename(chave: str) -> str:
    """Converts to filename format."""
    return re.sub(r'[^a-zA-Z0-9._-]+', '_', chave).strip('_') or 'cover'

def get_cache_filename(titulo: str) -> str:
    """Gets the expected cache filename for a title."""
    normalized = normalize_title_for_cache(titulo)
    filename = normalize_for_filename(normalized)
    return f"title_{filename}.webp"

def audit_cache_files():
    """Audits cache files."""
    print("\n" + "="*60)
    print("CACHE FILES AUDIT")
    print("="*60)
    
    if not CACHE_DIR.exists():
        print(f"⚠️  Cache directory not found: {CACHE_DIR}")
        return {}
    
    files = sorted(CACHE_DIR.glob('*.webp'))
    print(f"\nTotal cache files: {len(files)}")
    
    # Group by type
    appid_files = [f for f in files if f.name.startswith('appid_')]
    title_files = [f for f in files if f.name.startswith('title_')]
    
    print(f"  - By AppID: {len(appid_files)}")
    print(f"  - By Title: {len(title_files)}")
    
    cache_map = {}
    for f in files:
        try:
            if f.stat().st_size < 5000:
                raise ValueError('arquivo pequeno: provavelmente placeholder')
            img = Image.open(f)
            width, height = img.size
            size_kb = f.stat().st_size / 1024
            cache_map[f.name] = {
                'path': str(f),
                'size_kb': size_kb,
                'width': width,
                'height': height,
                'valid': True
            }
        except Exception as e:
            cache_map[f.name] = {
                'path': str(f),
                'valid': False,
                'error': str(e)
            }
    
    # Show some examples
    print("\nSample AppID files:")
    for f in appid_files[:3]:
        info = cache_map.get(f.name, {})
        status = '[OK]' if info.get('valid') else '[FAIL]'
        print(f"  - {f.name}: {info.get('size_kb', 0):.1f}KB {info.get('width', '?')}x{info.get('height', '?')} {status}")
    
    print("\nSample Title files:")
    for f in title_files[:5]:
        info = cache_map.get(f.name, {})
        status = '[OK]' if info.get('valid') else '[FAIL]'
        print(f"  - {f.name}: {info.get('size_kb', 0):.1f}KB {info.get('width', '?')}x{info.get('height', '?')} {status}")
    
    return cache_map

def audit_database():
    """Audits database covers."""
    print("\n" + "="*60)
    print("DATABASE AUDIT")
    print("="*60)
    
    if not DB_PATH.exists():
        print(f"⚠️  Database not found: {DB_PATH}")
        return
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        
        # Check biblioteca table structure
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(biblioteca)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print("\nBiblioteca table columns:")
        print(f"  - Has 'cover_url' column: {'cover_url' in column_names}")
        print(f"  - Has 'jogo_id' column: {'jogo_id' in column_names}")
        print(f"  - Has 'codigo_origem' column: {'codigo_origem' in column_names}")
        
        # Count games with covers
        cursor.execute("SELECT COUNT(*) FROM biblioteca WHERE cover_url IS NOT NULL AND cover_url != ''")
        with_cover = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM biblioteca")
        total = cursor.fetchone()[0]
        
        print(f"\nGames in biblioteca: {total}")
        print(f"  - With cover_url set: {with_cover} ({100*with_cover//total if total > 0 else 0}%)")
        print(f"  - Without cover_url: {total - with_cover}")

        cursor.execute("""
            SELECT b.email_usuario, b.jogo_id, j.titulo, b.origem,
                   b.codigo_origem, b.cover_url
            FROM biblioteca b LEFT JOIN jogos j ON j.id = b.jogo_id
            ORDER BY b.email_usuario, b.jogo_id
        """)
        findings = {
            'missing': [],
            'invalid_cache': [],
            'mismatched_appid': [],
            'fallback': [],
            'no_identity': [],
        }
        for email, game_id, title, origin, source_code, cover_url in cursor.fetchall():
            title = (title or '').strip()
            cover_url = (cover_url or '').strip()
            if not title and not game_id:
                findings['no_identity'].append((email, game_id, title))
            if not cover_url:
                findings['missing'].append((email, game_id, title))
                continue
            if cover_url.lower().startswith('data:image'):
                findings['fallback'].append((email, game_id, title))
            if cover_url.startswith('/static/cache/covers/'):
                cache_file = CACHE_DIR / Path(cover_url).name
                if not cache_file.exists() or cache_file.stat().st_size < 5000:
                    findings['invalid_cache'].append((email, game_id, title, cover_url))
                appid_match = re.search(r'appid_(\d+)\.webp$', cache_file.name)
                if appid_match and (not str(source_code or '').isdigit() or int(appid_match.group(1)) != int(source_code)):
                    findings['mismatched_appid'].append((email, game_id, title, source_code, cover_url))

        print("\nRecord-level cover findings:")
        for category, records in findings.items():
            print(f"  - {category}: {len(records)}")
        for category in ('missing', 'invalid_cache', 'mismatched_appid', 'no_identity'):
            if findings[category]:
                print(f"\n  {category} samples:")
                for record in findings[category][:10]:
                    print(f"    - {record}")
        
        # Show some examples
        print("\nSample games with cover_url:")
        cursor.execute("SELECT jogo_id, origem, launcher, cover_url FROM biblioteca WHERE cover_url IS NOT NULL AND cover_url != '' LIMIT 5")
        for row in cursor.fetchall():
            jogo_id = row[0]
            origem = row[1]
            cover_url = row[3]
            print(f"  - Game {jogo_id} ({origem}): {cover_url[:50]}..." if len(cover_url) > 50 else f"  - Game {jogo_id} ({origem}): {cover_url}")
        
        print("\nSample games without cover_url:")
        cursor.execute("SELECT jogo_id, origem, launcher FROM biblioteca WHERE cover_url IS NULL OR cover_url = '' LIMIT 5")
        for row in cursor.fetchall():
            jogo_id = row[0]
            origem = row[1]
            print(f"  - Game {jogo_id} ({origem})")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Error auditing database: {e}")

def test_normalization():
    """Tests normalization function."""
    print("\n" + "="*60)
    print("NORMALIZATION TEST")
    print("="*60)
    
    test_cases = [
        "Resident Evil 4",
        "The Witcher 3: Wild Hunt",
        "God of War™ Ragnarök",
        "Elden Ring (2022)",
        "Grand Theft Auto V",
        "Assassin's Creed Shadows",
        "Dragon Ball Sparking! ZERO",
        "Portal 2",
    ]
    
    print("\nNormalization results:")
    for title in test_cases:
        normalized = normalize_title_for_cache(title)
        filename = get_cache_filename(title)
        exists = (CACHE_DIR / filename).exists()
        print(f"\n  Title: {title}")
        print(f"    Normalized: {normalized}")
        print(f"    Expected filename: {filename}")
        status = '[YES]' if exists else '[NO]'
        print(f"    Exists in cache: {status}")

def main():
    print("\n" + "="*60)
    print("GAMEUNEXA COVER SYSTEM AUDIT")
    print("="*60)
    
    cache_files = audit_cache_files()
    audit_database()
    test_normalization()
    
    print("\n" + "="*60)
    print("AUDIT COMPLETE")
    print("="*60)

if __name__ == '__main__':
    main()
