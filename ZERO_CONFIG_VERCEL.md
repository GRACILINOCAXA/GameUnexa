# GameUnexa ZERO-CONFIG VERCEL Deployment

This document describes how GameUnexa has been transformed into a zero-configuration Vercel deployment.

## Overview

GameUnexa can now be deployed to Vercel **WITHOUT ANY MANUAL CONFIGURATION**.

### Deployment Flow

```
GitHub Repository
    ↓
Vercel Dashboard (Import Repository)
    ↓
Click "Deploy"
    ↓
Application Starts
    ↓
Zero-Config System:
  1. Detects environment (Vercel)
  2. Auto-detects database (PostgreSQL or SQLite)
  3. Generates/loads SECRET_KEY
  4. Initializes database schema
  5. Ready to accept traffic
    ↓
GameUnexa Running (Create Account → Login → Dashboard)
```

## What Happens Automatically

### 1. Database Detection (`db_config.py`)

The system automatically detects available databases in this order:

1. **PostgreSQL via Environment Variables**
   - Checks `DATABASE_URL`
   - Checks `POSTGRES_URL`
   - Checks `POSTGRES_URL_NON_POOLING`
   - Checks individual env vars: `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

2. **SQLite Fallback**
   - On Vercel: Uses `/tmp/gameunexa.db` (ephemeral)
   - On Windows: Uses `%LOCALAPPDATA%/GameUnexa/data/gameunexa.db`
   - On Linux: Uses `~/.gameunexa/data/gameunexa.db`

### 2. SECRET_KEY Management (`secret_key_manager.py`)

The application automatically manages SECRET_KEY:

- Checks environment variable `SECRET_KEY`
- Generates a cryptographically secure key if needed
- Persists key on local systems (Windows/Linux)
- Ensures session consistency even after restarts
- Sessions don't break due to key changes

### 3. Database Initialization (`db_initializer.py`)

Automatic schema initialization:

- Creates all tables using `CREATE TABLE IF NOT EXISTS`
- Works for both PostgreSQL and SQLite
- Idempotent (safe to run multiple times)
- No manual SQL required
- No schema migration issues
- Preserves existing data

### 4. Environment Detection (`environment.py`)

Separates features by environment:

- **Desktop (Windows/Linux)**
  - Can access local file system
  - Can execute local programs (Hydra, Steam, etc.)
  - Can run background jobs
  
- **Web (Vercel)**
  - Database-driven features only
  - No local file system access
  - No subprocess execution
  - No background processes

### 5. Startup Orchestration (`zero_config.py`)

Unified initialization system:

- Detects environment
- Configures database
- Sets up SECRET_KEY
- Creates database schema
- Prints startup summary

## What You DON'T Need to Do

- ✅ **Don't create PostgreSQL database manually**
- ✅ **Don't copy DATABASE_URL to Vercel**
- ✅ **Don't execute SQL manually**
- ✅ **Don't configure environment variables manually**
- ✅ **Don't set ROOT_DIRECTORY**
- ✅ **Don't configure build commands**
- ✅ **Don't configure install commands**
- ✅ **Don't configure output directory**
- ✅ **Don't modify vercel.json**
- ✅ **Don't run database migrations manually**
- ✅ **Don't redeploy after setup**

## Features That Work

### Database-Driven Features (Work Everywhere)

- User registration and login
- Friend system
- Messaging
- Posts and comments
- User profiles
- Notifications
- Reviews and ratings
- Support tickets
- Session persistence

### Desktop-Only Features (Disabled on Vercel)

- Local game scanning (Hydra launcher)
- Local executable launching
- Background game library sync
- Local file operations

These features gracefully degrade on Vercel:
- System detects it's running on Vercel
- Disables desktop-only code paths
- Application continues to work normally
- Users can still:
  - Create accounts
  - Login
  - Use social features
  - Access reviews and ratings
  - Manage friends and messages

## Configuration

### On Vercel

The system auto-detects all configuration. You can optionally provide:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
SECRET_KEY=your-secret-key (optional, will be auto-generated)
```

But these are **OPTIONAL**. The system works without them.

### Locally (Windows/Linux)

Everything is automatic:

- Database: Uses local SQLite or connects to PostgreSQL if URL is provided
- SECRET_KEY: Generated and persisted automatically
- Schema: Created automatically on first run

## Testing

Run zero-config tests:

```bash
python -m pytest test_zero_config.py -v
```

Tests verify:
- Database auto-detection
- SECRET_KEY generation
- Database initialization
- Environment detection
- Session persistence
- Zero-config initialization

## File Structure

New files created:

```
GameUnexa/
├── db_config.py              # Database auto-detection
├── db_initializer.py         # Automatic schema initialization
├── secret_key_manager.py     # SECRET_KEY auto-generation
├── session_manager.py        # Serverless session management
├── environment.py            # Environment detection
├── zero_config.py            # Main orchestration
├── test_zero_config.py       # Comprehensive tests
├── vercel.json              # Updated for zero-config
├── requirements.txt         # Updated dependencies
└── (all other files remain unchanged)
```

## Database Support

### PostgreSQL (Recommended for Vercel)

- Auto-detected from environment
- Supports connection pooling
- Can be provided as single URL or individual env vars
- Recommended: Use Neon, Supabase, or AWS RDS

### SQLite (Local Development)

- Used as fallback when PostgreSQL not available
- Persisted on Windows/Linux
- Ephemeral on Vercel (but fully functional during requests)
- Perfect for testing

## Session Management

Sessions are now serverless-compatible:

1. **JWT-Based Sessions** (Default)
   - Sessions stored in signed cookies
   - Survive across different Vercel function instances
   - No central session store needed
   - Work with both PostgreSQL and SQLite

2. **Database-Backed Sessions** (Optional on PostgreSQL)
   - Extra security for sensitive applications
   - Requires PostgreSQL

Sessions automatically handle:
- User registration
- Email confirmation
- Login/logout
- Persistent auth tokens
- Multi-instance consistency

## Troubleshooting

### "Database connection failed"

**On Vercel:**
- The system will try PostgreSQL, then fallback to SQLite
- Check that DATABASE_URL is correct if deployed
- Application can start with SQLite if needed

**Locally:**
- Ensure write permissions to AppData/home directory
- Check disk space

### "SECRET_KEY issues"

**On Vercel:**
- System generates stable key automatically
- Sessions work without manual configuration

**Locally:**
- Key is persisted to disk
- Delete `.gameunexa_secret` to regenerate

### Sessions not persisting

**Solution:**
- System uses JWT tokens by default (works everywhere)
- On PostgreSQL, sessions can be stored in database
- Sessions automatically survive across function instances

## Deployment Checklist

- [ ] Push to GitHub
- [ ] Go to vercel.com
- [ ] Import repository
- [ ] Review default settings (should all be correct)
- [ ] Click "Deploy"
- [ ] Wait for deployment to complete (~2 min)
- [ ] Visit your GameUnexa URL
- [ ] Create an account
- [ ] Login
- [ ] Enjoy GameUnexa!

**That's it. No configuration needed.**

## Features Preserved

All existing GameUnexa features are preserved:

- 2D game library interface
- 3D library view
- Dashboard
- Friend system
- Messaging
- Posts and social features
- User profiles
- Review system
- Support section
- Admin panel
- Game metadata
- Cover art system
- Statistics and achievements

Desktop-specific features are available on Windows:
- Hydra launcher integration
- Local game scanning
- Automatic library management
- Background syncing

## Performance

Zero-config deployment maintains performance:

- Database queries optimized for Vercel's 30-second timeout
- No unnecessary operations during startup
- Schema creation is fast and efficient
- Sessions are lightweight
- Everything cached appropriately

## Security

Zero-config deployment maintains security standards:

- Secrets never hardcoded
- SECRET_KEY is cryptographically secure
- Database connections use TLS
- Sessions are signed and verified
- CSRF protection enabled
- XSS protection enabled
- SQL injection prevention via parameterized queries

## Support

For issues with zero-config deployment:

1. Check deployment logs on Vercel dashboard
2. Check function logs (Deployments → Runtime logs)
3. Test locally first (everything is identical)
4. Review this documentation
5. Check test results: `python test_zero_config.py`

---

**GameUnexa is now ready for ZERO-CONFIG VERCEL deployment.**
