import unittest
from unittest.mock import patch

from process_detector import resolve_playing_game
from modelos.usuario import Usuario, USUARIOS_DB
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


if __name__ == '__main__':
    unittest.main()
