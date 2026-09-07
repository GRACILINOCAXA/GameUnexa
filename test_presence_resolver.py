import inspect
import unittest
from unittest.mock import patch

import app as app_module
import steam_api
from process_detector import resolve_playing_game
from modelos.usuario import Usuario, USUARIOS_DB
from modelos.amigos_biblioteca import BibliotecaJogo
from presenca_sync import _sincronizar_usuario_automaticamente


class PresenceResolverTests(unittest.TestCase):
    def test_explicit_no_game_clears_stale_steam_game(self):
        user = Usuario(1, 'Teste', 'teste-presenca@example.com', 'x')
        user.steam_current_game = 'Boomerang Fu'
        user.steam_current_game_appid = 123
        user.steam_online = True
        USUARIOS_DB[user.email] = user
        estado = {
            'online': True,
            'steam_ativo': True,
            'hydra_ativo': False,
            'jogo_atual': '',
            'appid': None,
            'launcher': 'Steam',
        }

        try:
            with patch('presenca_sync.obter_status', return_value={'online': True, 'game': 'Jogo antigo'}), \
                    patch('database.persistir_usuario'):
                changed = _sincronizar_usuario_automaticamente(user.email, estado)
        finally:
            USUARIOS_DB.pop(user.email, None)

        self.assertTrue(changed)
        self.assertEqual(user.steam_current_game, '')
        self.assertIsNone(user.steam_current_game_appid)
        self.assertTrue(user.steam_online)

    def test_steam_uses_appid_and_friendly_name(self):
        result = resolve_playing_game(
            {'pid': 10, 'name': 're4.exe', 'exe': r'D:\SteamLibrary\steamapps\common\RE4\re4.exe', 'appid': 2050650},
            [{'titulo': 'Resident Evil 4', 'appid': 2050650, 'origem': 'steam_instalada',
              'caminho_exe': r'D:\SteamLibrary\steamapps\common\RE4\re4.exe',
              'pasta_instalacao': r'D:\SteamLibrary\steamapps\common\RE4'}],
        )
        self.assertEqual(result['name'], 'Resident Evil 4')
        self.assertEqual(result['appid'], 2050650)
        self.assertNotEqual(result['name'], 're4')

    def test_generic_unreal_executable_uses_install_folder(self):
        result = resolve_playing_game(
            {'pid': 11, 'name': 'Win64.exe', 'exe': r'D:\Games\Dragon Ball Sparking ZERO\Binaries\Win64\Win64.exe'},
            [{'titulo': 'Dragon Ball Sparking ZERO', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Dragon Ball Sparking ZERO\Binaries\Win64\Win64.exe',
              'pasta_instalacao': r'D:\Games\Dragon Ball Sparking ZERO'}],
        )
        self.assertEqual(result['name'], 'Dragon Ball Sparking ZERO')
        self.assertEqual(result['executable'], 'Win64.exe')

    def test_same_executable_outside_registered_folder_is_rejected(self):
        result = resolve_playing_game(
            {'pid': 12, 'name': 'Game.exe', 'exe': r'D:\Other\Game.exe'},
            [{'titulo': 'Resident Evil 5 OptiPana', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Resident Evil 5 OptiPana\re5.exe',
              'pasta_instalacao': r'D:\Games\Resident Evil 5 OptiPana'}],
        )
        self.assertEqual(result, {})

    def test_system_process_without_executable_path_is_rejected(self):
        result = resolve_playing_game(
            {'pid': 148, 'name': 'Registry', 'exe': 'Registry'},
            [{'titulo': 'Castle Crashers', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Castle Crashers\CastleCrashers.exe',
              'pasta_instalacao': r'D:\Games\Castle Crashers'}],
        )
        self.assertEqual(result, {})

    def test_windows_console_process_is_rejected(self):
        result = resolve_playing_game(
            {'pid': 1532, 'name': 'OpenConsole.exe', 'exe': r'C:\Windows\System32\OpenConsole.exe'},
            [{'titulo': 'Castle Crashers', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Castle Crashers\CastleCrashers.exe',
              'pasta_instalacao': r'D:\Games\Castle Crashers'}],
        )
        self.assertEqual(result, {})

    def test_launcher_is_not_a_game(self):
        result = resolve_playing_game(
            {'pid': 13, 'name': 'launcher.exe', 'exe': r'D:\Games\Resident Evil\launcher.exe'},
            [{'titulo': 'Resident Evil', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Resident Evil\launcher.exe',
              'pasta_instalacao': r'D:\Games\Resident Evil'}],
        )
        self.assertEqual(result, {})

    def test_background_service_is_not_a_game(self):
        result = resolve_playing_game(
            {'pid': 14, 'name': 'helperservice.exe',
             'exe': r'C:\Program Files\Softdeluxe\Free Download Manager\helperservice.exe'},
            [{'titulo': 'Registered Game', 'origem': 'biblioteca_local',
              'caminho_exe': r'C:\Program Files\Softdeluxe\Free Download Manager\helperservice.exe',
              'pasta_instalacao': r'C:\Program Files\Softdeluxe\Free Download Manager'}],
        )
        self.assertEqual(result, {})

    def test_non_game_software_path_is_not_a_game(self):
        result = resolve_playing_game(
            {'pid': 15, 'name': 'wenativehost.exe',
             'exe': r'C:\Program Files\Softdeluxe\Free Download Manager\wenativehost.exe'},
            [{'titulo': 'Registered Game', 'origem': 'biblioteca_local',
              'caminho_exe': r'C:\Program Files\Softdeluxe\Free Download Manager\wenativehost.exe',
              'pasta_instalacao': r'C:\Program Files\Softdeluxe\Free Download Manager'}],
        )
        self.assertEqual(result, {})

    def test_unrelated_program_files_process_is_not_a_game(self):
        result = resolve_playing_game(
            {'pid': 16, 'name': 'amdow.exe',
             'exe': r'C:\Program Files\AMD\CNext\CNext\amdow.exe'},
            [{'titulo': 'Registered Game', 'origem': 'biblioteca_local',
              'caminho_exe': r'C:\Program Files\AMD\CNext\CNext\amdow.exe',
              'pasta_instalacao': r'C:\Program Files\AMD\CNext\CNext'}],
        )
        self.assertEqual(result, {})

    def test_any_registered_executable_resolves_same_game(self):
        result = resolve_playing_game(
            {'pid': 14, 'name': 'BIO4-Win64-Shipping.exe',
             'exe': r'D:\Games\Resident Evil 4\BIO4-Win64-Shipping.exe'},
            [{'titulo': 'Resident Evil 4', 'origem': 'biblioteca_local',
              'caminho_exe': r'D:\Games\Resident Evil 4\re4.exe',
              'executaveis': [r'D:\Games\Resident Evil 4\launcher.exe',
                              r'D:\Games\Resident Evil 4\BIO4-Win64-Shipping.exe'],
              'pasta_instalacao': r'D:\Games\Resident Evil 4'}],
        )
        self.assertEqual(result['name'], 'Resident Evil 4')

    def test_expected_game_prioritizes_registered_candidate(self):
        from process_detector import DetectorPresenca

        detector = DetectorPresenca()
        detector.registrar_jogo_esperado('Resident Evil 4', 2050650)
        result = detector._identificar_jogo_info(
            [{'pid': 15, 'name': 're4.exe', 'exe': r'D:\Games\Resident Evil 4\re4.exe'}],
            [{'titulo': 'Resident Evil 4', 'appid': 2050650, 'origem': 'steam_instalada',
              'caminho_exe': r'D:\Games\Resident Evil 4\re4.exe',
              'pasta_instalacao': r'D:\Games\Resident Evil 4'}],
        )
        self.assertEqual(result['name'], 'Resident Evil 4')
        self.assertEqual(result['appid'], 2050650)

    def test_windows_folder_picker_uses_native_dialog_without_relaunching_exe(self):
        src = inspect.getsource(app_module._escolher_pasta_windows)
        self.assertIn('SHBrowseForFolderW', src)
        self.assertIn('SHGetPathFromIDListW', src)
        self.assertNotIn('sys.executable', src)
        self.assertNotIn('subprocess.run', src)

    def test_steam_library_sync_deduplicates_by_appid_and_removes_stale_games(self):
        email = 'steam-dup@example.com'
        user = Usuario(99, 'Steam Dup', email, 'x')
        app_module.USUARIOS_DB[email] = user
        app_module.BIBLIOTECA_DB.clear()
        app_module.JOGOS_DB.clear()

        for appid in (111, 222, 730, 570):
            app_module.JOGOS_DB[appid] = app_module.Jogo(appid, f'Jogo {appid}', 'Steam', 'Steam', 2024)

        stale = BibliotecaJogo(1, email, 111, origem='steam', launcher='steam')
        stale.codigo_origem = '111'
        old_steam = BibliotecaJogo(2, email, 222, origem='steam', launcher='steam')
        old_steam.codigo_origem = '222'
        app_module.BIBLIOTECA_DB[f'{email}_111'] = stale
        app_module.BIBLIOTECA_DB[f'{email}_222'] = old_steam

        with patch.object(app_module, 'montar_steam_contexto', return_value={
            'steam_id64': '76561198000000001',
            'jogos': [
                {'appid': 730, 'name': 'Counter-Strike 2', 'playtime_forever': 500},
                {'appid': 570, 'name': 'Dota 2', 'playtime_forever': 200},
                {'appid': 730, 'name': 'Counter-Strike 2 Duplicate', 'playtime_forever': 800},
            ],
            'erro': None,
        }), patch.object(app_module, 'listar_jogos_instalados', return_value=[
            {'appid': 730, 'name': 'Counter-Strike 2', 'playtime_forever': 500},
            {'appid': 570, 'name': 'Dota 2', 'playtime_forever': 200},
        ]), patch.object(app_module, '_capa_steam_jogo', return_value=''), patch.object(app_module, 'persistir_jogo'), patch.object(app_module, 'persistir_biblioteca_item'):
            importados, ja_existiam, erro = app_module.importar_steam_para_biblioteca_local(email)

        steam_items = [
            item for item in app_module.BIBLIOTECA_DB.values()
            if item.email_usuario == email and (item.launcher == 'steam' or item.origem == 'steam')
        ]

        self.assertIsNone(erro)
        self.assertEqual(importados, 2)
        self.assertEqual(ja_existiam, 0)
        self.assertEqual(len(steam_items), 2)
        self.assertNotIn(111, {int(item.codigo_origem or 0) for item in steam_items})
        self.assertNotIn(222, {int(item.codigo_origem or 0) for item in steam_items})
        self.assertEqual({int(item.codigo_origem or 0) for item in steam_items}, {570, 730})

        app_module.USUARIOS_DB.pop(email, None)
        app_module.BIBLIOTECA_DB.clear()
        app_module.JOGOS_DB.clear()

    def test_steam_library_filters_out_non_game_types(self):
        with patch.object(steam_api, '_steam_fetch_json', side_effect=[
            {
                'response': {
                    'games': [
                        {'appid': 111, 'name': 'Real Game', 'playtime_forever': 120},
                        {'appid': 222, 'name': 'DLC Extra', 'playtime_forever': 90},
                        {'appid': 333, 'name': 'Game Demo', 'playtime_forever': 10},
                    ]
                }
            },
            {
                '111': {'success': True, 'data': {'type': 'game'}},
            },
            {
                '222': {'success': True, 'data': {'type': 'dlc'}},
            },
            {
                '333': {'success': True, 'data': {'type': 'demo'}},
            },
        ]):
            result = steam_api.obter_jogos('76561198000000001', 'FAKEKEY')

        self.assertEqual([item['appid'] for item in result], [111])

    def test_steam_import_removes_old_manual_entries_with_steam_appids(self):
        email = 'steam-manual-old@example.com'
        user = Usuario(100, 'Steam Manual Old', email, 'x')
        app_module.USUARIOS_DB[email] = user
        app_module.BIBLIOTECA_DB.clear()
        app_module.JOGOS_DB.clear()

        for appid in (730, 570, 111, 222):
            app_module.JOGOS_DB[appid] = app_module.Jogo(appid, f'Jogo {appid}', 'Steam', 'Steam', 2024)

        stale_manual = BibliotecaJogo(10, email, 111, origem='manual', launcher='manual')
        stale_manual.codigo_origem = '111'
        stale_manual.manual_override = False

        stale_steam = BibliotecaJogo(11, email, 222, origem='steam', launcher='steam')
        stale_steam.codigo_origem = '222'

        current_ok = BibliotecaJogo(12, email, 730, origem='steam', launcher='steam')
        current_ok.codigo_origem = '730'

        app_module.BIBLIOTECA_DB[f'{email}_111'] = stale_manual
        app_module.BIBLIOTECA_DB[f'{email}_222'] = stale_steam
        app_module.BIBLIOTECA_DB[f'{email}_730'] = current_ok

        with patch.object(app_module, 'montar_steam_contexto', return_value={
            'steam_id64': '76561198000000002',
            'jogos': [
                {'appid': 730, 'name': 'Counter-Strike 2', 'playtime_forever': 400},
                {'appid': 570, 'name': 'Dota 2', 'playtime_forever': 250},
            ],
            'erro': None,
        }), patch.object(app_module, 'listar_jogos_instalados', return_value=[
            {'appid': 730, 'name': 'Counter-Strike 2', 'playtime_forever': 400},
            {'appid': 570, 'name': 'Dota 2', 'playtime_forever': 250},
        ]), patch.object(app_module, '_capa_steam_jogo', return_value=''), patch.object(app_module, 'persistir_jogo'), patch.object(app_module, 'persistir_biblioteca_item'):
            importados, ja_existiam, erro = app_module.importar_steam_para_biblioteca_local(email)

        final_appids = {
            int(str(item.codigo_origem or item.jogo_id).strip())
            for item in app_module.BIBLIOTECA_DB.values()
            if item.email_usuario == email
            and (str(item.codigo_origem or item.jogo_id).strip().isdigit())
        }

        self.assertIsNone(erro)
        self.assertEqual(importados, 1)
        self.assertEqual(ja_existiam, 1)
        self.assertEqual(final_appids, {570, 730})
        self.assertNotIn(111, final_appids)
        self.assertNotIn(222, final_appids)

        app_module.USUARIOS_DB.pop(email, None)
        app_module.BIBLIOTECA_DB.clear()
        app_module.JOGOS_DB.clear()


if __name__ == '__main__':
    unittest.main()
