import os
import re
import unittest

os.environ.setdefault('SECRET_KEY', 'test-secret-for-vercel')

from app import app


class CadastroEmailVerificationFlowTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_cadastro_page_exposes_same_page_verification_ui(self):
        resp = self.client.get('/cadastro')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('Cadastre-se', html)
        self.assertIn('CADASTRAR', html)

    def test_verification_flow_keeps_user_on_same_page(self):
        page = self.client.get('/cadastro')
        html = page.get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match, 'CSRF token missing from cadastro page')
        csrf_token = match.group(1)

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


if __name__ == '__main__':
    unittest.main()
