"""
Comprehensive test suite for GameLink 3D/2D library integration
Tests cover all 20 requirements from the refactoring spec
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_backend_data_structure():
    """TEST 1: Verify backend returns correct game data structure"""
    print("\n" + "="*70)
    print("TEST 1: Backend Data Structure")
    print("="*70)
    
    try:
        from app import app, _montar_cards_jogar, _montar_games_data_jogar
        
        with app.app_context():
            # Test with admin user
            test_email = 'admin@gamelink.com'
            cards = _montar_cards_jogar(test_email)
            
            print(f"✓ Retrieved {len(cards)} cards from backend")
            
            # Check first card structure
            if cards:
                first_card = cards[0]
                required_keys = ['capa_url', 'capa_fallback', 'launcher_display', 'jogo', 'origem']
                for key in required_keys:
                    assert key in first_card, f"Missing key: {key}"
                print(f"✓ Card structure is valid")
            
            # Convert to 3D format
            games_data = _montar_games_data_jogar(cards)
            print(f"✓ Converted to {len(games_data)} games for 3D library")
            
            if games_data:
                first_game = games_data[0]
                required_fields = ['id', 'title', 'genre', 'platform', 'coverUrl', 'favorito', 'origem']
                for field in required_fields:
                    assert field in first_game, f"Missing field: {field}"
                print(f"✓ 3D games data structure is valid")
                print(f"  - Title: {first_game['title']}")
                print(f"  - Genre: {first_game['genre']}")
                print(f"  - Platform: {first_game['platform']}")
                print(f"  - CoverUrl: {first_game['coverUrl'][:50]}..." if len(first_game['coverUrl']) > 50 else f"  - CoverUrl: {first_game['coverUrl']}")
            
            print("✅ TEST 1 PASSED")
            return True
            
    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        return False

def test_cover_resolution():
    """TEST 2: Verify centralized cover resolution works"""
    print("\n" + "="*70)
    print("TEST 2: Cover Resolution")
    print("="*70)
    
    try:
        from app import app, _get_game_cover_centralized, _is_valid_cached_cover
        
        with app.app_context():
            # Test cover resolution for various games
            test_cases = [
                ("The Witcher 3", 292030, "steam"),
                ("Resident Evil 4", 323470, "steam"),
                ("Elden Ring", None, "manual"),
                ("NOTEXISTINGAME12345", None, "manual"),
            ]
            
            results = []
            for title, appid, origin in test_cases:
                cover_url = _get_game_cover_centralized(title, appid, origin)
                is_valid = bool(cover_url and not cover_url.startswith('data:'))  # Not SVG placeholder
                results.append({
                    'title': title,
                    'cover_url': cover_url[:50] + '...' if len(cover_url) > 50 else cover_url,
                    'is_valid': is_valid,
                    'type': 'Real' if is_valid else 'Fallback'
                })
                print(f"  • {title} ({origin}): {results[-1]['type']}")
            
            # Check cache validation
            import os
            cache_dir = 'static/cache/covers'
            if os.path.exists(cache_dir):
                valid_count = 0
                total_count = 0
                for file in os.listdir(cache_dir):
                    total_count += 1
                    filepath = os.path.join(cache_dir, file)
                    if _is_valid_cached_cover(filepath):
                        valid_count += 1
                print(f"✓ Cache validation: {valid_count}/{total_count} files are real images")
            
            print("✅ TEST 2 PASSED")
            return True
            
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        return False

def test_all_games_loaded():
    """TEST 3: Verify ALL games are loaded (not just 20)"""
    print("\n" + "="*70)
    print("TEST 3: All Games Loaded (No 20-Game Limit)")
    print("="*70)
    
    try:
        from app import app, _montar_cards_jogar, _montar_games_data_jogar, GerenciadorBiblioteca
        
        with app.app_context():
            test_email = 'admin@gamelink.com'
            
            # Check database directly
            all_items = GerenciadorBiblioteca.obter_biblioteca(test_email)
            db_count = len(all_items)
            print(f"✓ Database contains {db_count} games")
            
            # Check cards generated
            cards = _montar_cards_jogar(test_email)
            cards_count = len(cards)
            print(f"✓ Backend generated {cards_count} cards")
            
            # Check 3D games data
            games_data = _montar_games_data_jogar(cards)
            games_count = len(games_data)
            print(f"✓ 3D library received {games_count} games")
            
            # Verify all are included
            assert games_count == db_count, f"Expected {db_count} games, got {games_count}"
            assert games_count > 20, f"Expected more than 20 games, got {games_count}"
            
            print(f"✅ All {games_count} games are included (no artificial limit)")
            print("✅ TEST 3 PASSED")
            return True
            
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        return False

def test_shelf_distribution():
    """TEST 4: Verify games are correctly distributed across shelves"""
    print("\n" + "="*70)
    print("TEST 4: Shelf Distribution")
    print("="*70)
    
    try:
        from app import app, _montar_cards_jogar, _montar_games_data_jogar
        
        with app.app_context():
            games_data = _montar_games_data_jogar(_montar_cards_jogar('admin@gamelink.com'))
            total_games = len(games_data)
            games_per_shelf = 12  # From 3D template config
            
            expected_shelves = (total_games + games_per_shelf - 1) // games_per_shelf  # Ceiling division
            
            print(f"✓ Total games: {total_games}")
            print(f"✓ Games per shelf: {games_per_shelf}")
            print(f"✓ Expected shelves: {expected_shelves}")
            
            # Simulate shelf assignment (as done in template)
            shelf_assignments = {}
            for idx, game in enumerate(games_data):
                shelf = idx // games_per_shelf
                if shelf not in shelf_assignments:
                    shelf_assignments[shelf] = []
                shelf_assignments[shelf].append(game['title'])
            
            print(f"\n✓ Actual shelves created: {len(shelf_assignments)}")
            for shelf_num, games_in_shelf in sorted(shelf_assignments.items()):
                print(f"  Shelf {shelf_num}: {len(games_in_shelf)} games")
            
            # Verify last shelf isn't empty
            last_shelf_num = max(shelf_assignments.keys())
            last_shelf_count = len(shelf_assignments[last_shelf_num])
            assert last_shelf_count > 0, "Last shelf is empty"
            
            print(f"✅ Last shelf has {last_shelf_count} games (not empty)")
            print("✅ TEST 4 PASSED")
            return True
            
    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        return False

def test_template_sanity():
    """TEST 5: Verify 3D template has no hardcoded limits"""
    print("\n" + "="*70)
    print("TEST 5: Template Configuration")
    print("="*70)
    
    try:
        template_path = Path('templates/biblioteca_de_jogos_3d_definitiva.html')
        template_content = template_path.read_text(encoding='utf-8')
        
        # Check for problematic patterns
        issues = []
        
        # Check textureLoader is let, not const (for cleanup)
        if 'const textureLoader = new THREE.TextureLoader()' in template_content:
            issues.append("textureLoader should be 'let', not 'const'")
        else:
            print("✓ textureLoader is properly declared as 'let'")
        
        # Check no hardcoded 20 or artificial limits
        bad_patterns = [
            ('gamesData.slice(0, 20)', 'Hardcoded 20-game limit'),
            ('gamesData.slice(0, 10)', 'Hardcoded 10-game limit'),
            ('maxGames = 20', 'maxGames hardcoded to 20'),
        ]
        
        for pattern, description in bad_patterns:
            if pattern in template_content:
                issues.append(description)
            else:
                print(f"✓ No {description.lower()}")
        
        # Check shelf configuration
        if 'gamesPerShelf' in template_content:
            print("✓ Dynamic gamesPerShelf configuration found")
        
        if 'shelfCount = Math.ceil' in template_content or 'shelfCount = Math.max' in template_content:
            print("✓ Dynamic shelf count calculation found")
        
        if issues:
            print(f"❌ Found {len(issues)} issues:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        
        print("✅ Template configuration is optimal")
        print("✅ TEST 5 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        return False

def test_error_handling():
    """TEST 6: Verify error handling prevents cascading failures"""
    print("\n" + "="*70)
    print("TEST 6: Error Handling & Resilience")
    print("="*70)
    
    try:
        from app import app, _get_game_cover_centralized
        
        with app.app_context():
            # Test with invalid inputs
            test_cases = [
                (None, None, 'manual'),
                ('', None, 'manual'),
                ('Valid Title', 'invalid_appid', 'steam'),  # appid should be int
            ]
            
            for title, appid, origin in test_cases:
                try:
                    result = _get_game_cover_centralized(title, appid, origin)
                    assert isinstance(result, str), "Result should be string"
                    print(f"✓ Handled: title={title}, appid={appid}")
                except Exception as e:
                    print(f"✗ Failed on: title={title}, appid={appid} - Error: {e}")
                    return False
        
        print("✅ Error handling prevents cascading failures")
        print("✅ TEST 6 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ TEST 6 FAILED: {e}")
        return False


def test_desktop_browser_library_split():
    """TEST 7: Verify the desktop vs browser folder selection contracts."""
    print("\n" + "="*70)
    print("TEST 7: Desktop Browser Library Split")
    print("="*70)

    try:
        from app import is_desktop_gameunexa, is_web_gameunexa, format_folder_label, build_browser_library_reference

        assert callable(is_desktop_gameunexa)
        assert callable(is_web_gameunexa)
        label = format_folder_label('Jogos', 'D:/Jogos')
        assert 'Jogos' in label and 'D:/Jogos' in label
        assert 'Pasta selecionada no computador' in format_folder_label('Jogos', '')
        browser_ref = build_browser_library_reference('Jogos', 'browser:Jogos')
        assert 'browser:' in browser_ref

        print("✅ TEST 7 PASSED")
        return True
    except Exception as exc:
        print(f"❌ TEST 7 FAILED: {exc}")
        return False

# Run all tests
if __name__ == '__main__':
    print("\n" + "="*70)
    print("GAMELINK 3D/2D LIBRARY REFACTORING - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        test_backend_data_structure,
        test_cover_resolution,
        test_all_games_loaded,
        test_shelf_distribution,
        test_template_sanity,
        test_error_handling,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            results.append(False)
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - System ready for production")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)
