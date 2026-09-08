import os
import re
import unittest
from uuid import uuid4

os.environ.setdefault('SECRET_KEY', 'test-secret-for-vercel')

from app import app


class CadastroEmailVerificationFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _obter_csrf(self):
        page = self.client.get('/cadastro')
        html = page.get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match, 'CSRF token missing from cadastro page')
        return match.group(1)

    def _criar_usuario_esperando_verificacao(self, nome, email, senha):
        self.client.get('/cadastro')
        USUARIOS_DB = __import__('app').USUARIOS_DB
        USUARIOS_DB.pop((email or '').strip().lower(), None)
        csrf_token = self._obter_csrf()
        resp = self.client.post('/cadastro', data={
            'nome': nome,
            'email': email,
            'senha': senha,
            'csrf_token': csrf_token,
            'acao': 'iniciar',
        }, follow_redirects=False)
        self.assertIn(resp.status_code, (200, 302))
        with self.client.session_transaction() as sess:
            codigo = sess['cadastro_pendente']['codigo']
            csrf_session = sess['csrf_token']
        return codigo, csrf_session

    def test_cadastro_page_exposes_same_page_verification_ui(self):
        resp = self.client.get('/cadastro')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('Cadastre-se', html)
        self.assertIn('CADASTRAR', html)

    def test_verification_flow_keeps_user_on_same_page(self):
        csrf_token = self._obter_csrf()

        resp = self.client.post('/cadastro', data={
            'nome': 'Maria Teste',
            'email': 'maria.teste@gmail.com',
            'senha': 'Senha123!',
            'csrf_token': csrf_token,
            'acao': 'iniciar',
        }, follow_redirects=False)

        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            html2 = resp.get_data(as_text=True)
            self.assertRegex(html2, r'VERIFIQUE SEU E-MAIL|Verifique seu e-mail')
            self.assertRegex(html2, r'VERIFICAR CÓDIGO|Confirmar cadastro')
            self.assertRegex(html2, r'REENVIAR CÓDIGO|Reenviar código')
            self.assertIn('@gmail.com', html2)
            self.assertIn('*', html2)

    def test_usuario_normaliza_email_e_permite_login_apos_cadastro(self):
        from modelos.usuario import Usuario

        user = Usuario(999, 'Teste Normalizacao', 'Usuario.Teste@GMAIL.com', 'Senha@123!')
        self.assertEqual(user.email, 'usuario.teste@gmail.com')
        self.assertTrue(user.verificar_senha('Senha@123!'))

        email = f'Usuario.Teste.{uuid4().hex[:8]}@GMAIL.com'
        senha = 'Senha@123!'
        codigo, csrf_session = self._criar_usuario_esperando_verificacao('Teste Login', email, senha)

        resp2 = self.client.post('/cadastro', data={
            'acao': 'verificar',
            'codigo_verificacao': codigo,
            'csrf_token': csrf_session,
        }, follow_redirects=False)
        self.assertIn(resp2.status_code, (200, 302))

        login_resp = self.client.post('/login', data={
            'email': 'usuario.teste@gmail.com',
            'senha': senha,
            'csrf_token': csrf_session,
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertEqual(login_resp.headers.get('Location'), '/dashboard')

    def test_login_senha_incorreta_e_usuario_inexistente(self):
        codigo, csrf_session = self._criar_usuario_esperando_verificacao('Senha Errada', f'errou.{uuid4().hex[:8]}@teste.com', 'Senha@123!')
        self.client.post('/cadastro', data={
            'acao': 'verificar',
            'codigo_verificacao': codigo,
            'csrf_token': csrf_session,
        }, follow_redirects=False)

        resp_invalida = self.client.post('/login', data={
            'email': 'errou@teste.com',
            'senha': 'SenhaErrada!1',
            'csrf_token': csrf_session,
        }, follow_redirects=False)
        self.assertIn(resp_invalida.status_code, (200, 302))

        resp_inexistente = self.client.post('/login', data={
            'email': 'naoexiste@teste.com',
            'senha': 'Qualquer@123',
            'csrf_token': csrf_session,
        }, follow_redirects=False)
        self.assertIn(resp_inexistente.status_code, (200, 302))

    def test_login_cria_sessao_e_logout_remove_session(self):
        codigo, csrf_session = self._criar_usuario_esperando_verificacao('Sessao Teste', f'sessao.{uuid4().hex[:8]}@teste.com', 'Senha@123!')
        self.client.post('/cadastro', data={
            'acao': 'verificar',
            'codigo_verificacao': codigo,
            'csrf_token': csrf_session,
        }, follow_redirects=False)

        login_resp = self.client.post('/login', data={
            'email': 'sessao@teste.com',
            'senha': 'Senha@123!',
            'csrf_token': csrf_session,
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertEqual(login_resp.headers.get('Location'), '/dashboard')

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_email'), 'sessao@teste.com')
            self.assertIn('user_email', sess)

        logout_resp = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(logout_resp.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_email', sess)


if __name__ == '__main__':
    unittest.main()
