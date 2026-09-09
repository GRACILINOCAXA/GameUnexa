#!/usr/bin/env python3
"""
Test the centralized cover resolver implementation.
Verifies that _is_valid_cached_cover and _get_game_cover_centralized work correctly.
"""

import os
import sys
from pathlib import Path
from PIL import Image
from io import BytesIO

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the app module functions
try:
    from app import (
        _is_valid_cached_cover,
        _get_game_cover_centralized,
        _capa_fallback,
        JOGOS_DB,
        GerenciadorBiblioteca,
        USUARIOS_DB,
        _normalizar_titulo_capa,
    )
except ImportError as e:
    print(f"❌ Failed to import from app.py: {e}")
    sys.exit(1)

print("=" * 70)
print("TESTING CENTRALIZED COVER RESOLVER")
print("=" * 70)

# Test 1: Verify _is_valid_cached_cover function
print("\n[TEST 1] Validating cache files...")
cache_dir = Path(__file__).parent / "static" / "cache" / "covers"

if not cache_dir.exists():
    print(f"❌ Cache directory not found: {cache_dir}")
    sys.exit(1)

valid_count = 0
invalid_count = 0
sample_valid = []
sample_invalid = []

for cache_file in sorted(cache_dir.glob("*.webp")):
    is_valid = _is_valid_cached_cover(str(cache_file))
    size_kb = cache_file.stat().st_size / 1024
    
    if is_valid:
        valid_count += 1
        if len(sample_valid) < 5:
            sample_valid.append((cache_file.name, size_kb))
    else:
        invalid_count += 1
        if len(sample_invalid) < 5:
            sample_invalid.append((cache_file.name, size_kb))

print(f"✓ Total files analyzed: {valid_count + invalid_count}")
print(f"  - Valid real images: {valid_count}")
print(f"  - Invalid (placeholders): {invalid_count}")

print("\n  Sample VALID files:")
for name, size in sample_valid:
    print(f"    ✓ {name}: {size:.1f}KB")

print("\n  Sample INVALID files (placeholders):")
for name, size in sample_invalid:
    print(f"    ✗ {name}: {size:.1f}KB")

# Test 2: Test the centralized resolver with sample games
print("\n" + "=" * 70)
print("[TEST 2] Testing centralized cover resolver...")
print("=" * 70)

# Get a sample of games from different sources
steam_games = [j for j in JOGOS_DB.values() if j.genero and 'steam' in j.genero.lower()][:3]
other_games = [j for j in JOGOS_DB.values() if j.genero and 'steam' not in j.genero.lower()][:3]

test_games = steam_games + other_games
if not test_games and JOGOS_DB:
    test_games = list(JOGOS_DB.values())[:6]

if test_games:
    print(f"\nTesting {len(test_games)} games:")
    for jogo in test_games:
        titulo = jogo.titulo
        origem = 'steam' if jogo.genero and 'steam' in jogo.genero.lower() else 'manual'
        appid = jogo.id if origem == 'steam' else None
        
        cover_url = _get_game_cover_centralized(titulo, appid, origem)
        
        # Check if it's a real cover or placeholder
        is_placeholder = cover_url.startswith('data:image/svg')
        is_cached = '/static/cache' in cover_url
        is_steam_cdn = 'cdn.cloudflare.steamstatic.com' in cover_url
        
        status_icon = "📦" if is_placeholder else "✓"
        status_type = "PLACEHOLDER" if is_placeholder else ("CACHED" if is_cached else ("STEAM CDN" if is_steam_cdn else "EXTERNAL"))
        
        print(f"\n  {status_icon} {titulo}")
        print(f"     Source: {origem}, AppID: {appid}")
        print(f"     Type: {status_type}")
        print(f"     URL: {cover_url[:60]}...")
else:
    print("  No games found in database")

# Test 3: Test with actual users' libraries
print("\n" + "=" * 70)
print("[TEST 3] Testing resolver with actual user libraries...")
print("=" * 70)

if USUARIOS_DB:
    sample_user = next(iter(USUARIOS_DB.values()))
    print(f"\nTesting with user: {sample_user.nome} ({sample_user.email})")
    
    try:
        biblioteca_items = GerenciadorBiblioteca.obter_biblioteca(sample_user.email)
        print(f"  Library has {len(biblioteca_items)} items")
        
        covers_generated = 0
        covers_from_cache = 0
        covers_placeholder = 0
        
        for item in biblioteca_items[:5]:  # Test first 5
            jogo = JOGOS_DB.get(item.jogo_id)
            if not jogo:
                continue
            
            origem = getattr(item, 'launcher', '') or getattr(item, 'origem', '') or 'manual'
            appid = item.jogo_id if origem == 'steam' else None
            
            cover_url = _get_game_cover_centralized(jogo.titulo, appid, origem)
            
            is_placeholder = cover_url.startswith('data:image/svg')
            is_cached = '/static/cache' in cover_url
            
            if is_placeholder:
                covers_placeholder += 1
            elif is_cached:
                covers_from_cache += 1
            else:
                covers_generated += 1
            
            status = "📦" if is_placeholder else "✓"
            print(f"    {status} {jogo.titulo[:40]}: {cover_url[:50]}...")
        
        print(f"\n  Summary:")
        print(f"    - From cache: {covers_from_cache}")
        print(f"    - Generated: {covers_generated}")
        print(f"    - Placeholders: {covers_placeholder}")
        
    except Exception as e:
        print(f"  ❌ Error testing user library: {e}")
else:
    print("  No users found in database")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
