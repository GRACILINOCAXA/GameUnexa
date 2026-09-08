# PostgreSQL persistente no GameUnexa

O GameUnexa usa PostgreSQL como armazenamento canônico da autenticação quando está rodando na Vercel.

## 1. Criar o banco

Crie um banco PostgreSQL em um provedor compatível, por exemplo:

- Supabase
- Neon
- Railway PostgreSQL

Copie a connection string PostgreSQL fornecida pelo provedor.

## 2. Variáveis da Vercel

No projeto da Vercel, em **Settings → Environment Variables**, configure:

```text
DATABASE_URL=postgresql://USUARIO:SENHA@HOST:5432/BANCO?sslmode=require
SECRET_KEY=uma-chave-aleatoria-grande
```

Configure as variáveis para **Production** e **Preview** se os dois ambientes forem usados.

Não coloque essas credenciais no GitHub.

## 3. Inicialização

Não é necessário executar SQL manualmente para o fluxo de autenticação. Quando `DATABASE_URL` estiver configurada, o GameUnexa cria automaticamente:

- `gameunexa_usuarios`
- `gameunexa_pending_registrations`
- índices necessários

O arquivo `postgresql_schema.sql` também contém o schema caso você queira inspecionar ou aplicar manualmente.

## 4. Fluxo de cadastro

```text
/cadastro
   ↓
normaliza e-mail
   ↓
hash da senha
   ↓
gameunexa_pending_registrations
   ↓
código de verificação
   ↓
confirmação
   ↓
gameunexa_usuarios
   ↓
/login
   ↓
busca direta no PostgreSQL
   ↓
verificação do hash
   ↓
sessão Flask
```

O código e o hash da senha não dependem de `USUARIOS_DB` nem de `/tmp`.

## 5. Importante sobre o restante da aplicação

O projeto mantém SQLite local para compatibilidade com funcionalidades desktop e partes legadas da aplicação. Na Vercel, o PostgreSQL é a fonte persistente e canônica da autenticação.

Para tornar também biblioteca, posts, mensagens, amizades, reviews e demais dados 100% persistentes entre instâncias serverless, essas tabelas precisam ser migradas para PostgreSQL em uma segunda etapa.
