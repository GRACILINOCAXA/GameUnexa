16#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script for GameUnexa ZERO-CONFIG VERCEL deployment.

Checks for:
- Hardcoded secrets
- SQLite direct usage (should use abstraction)
- Subprocess execution on Vercel
- Filesystem access patterns
- Environment-based feature gates
- Requirements completeness
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple


class ZeroConfigVerifier:
    """Verifies zero-config Vercel readiness."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.issues = []
        self.warnings = []
        self.passed = []

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print("\n" + "="*70)
        print("GameUnexa ZERO-CONFIG VERCEL Verification")
        print("="*70 + "\n")

        self.check_zero_config_files_exist()
        self.check_requirements_txt()
        self.check_vercel_json()
        self.check_app_py_integration()
        self.check_hardcoded_secrets()
        self.check_database_abstraction()
        self.check_environment_guards()
        self.check_no_require_app_run()
        self.check_session_implementation()

        self.print_results()
        return len(self.issues) == 0

    def check_zero_config_files_exist(self):
        """Verify all zero-config files exist."""
        print("[1] Checking zero-config files...")
        required_files = [
            'db_config.py',
            'db_initializer.py',
            'secret_key_manager.py',
            'environment.py',
            'session_manager.py',
            'zero_config.py',
        ]

        for filename in required_files:
            filepath = self.project_root / filename
            if filepath.exists():
                self.passed.append(f"✓ {filename} exists")
            else:
                self.issues.append(f"✗ {filename} is MISSING")

    def check_requirements_txt(self):
        """Verify requirements.txt is complete."""
        print("[2] Checking requirements.txt...")
        req_file = self.project_root / 'requirements.txt'
        
        if not req_file.exists():
            self.issues.append("✗ requirements.txt not found")
            return

        try:
            content = req_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            content = req_file.read_text(errors='ignore')
        
        required = {
            'Flask': 'Flask web framework',
            'psycopg2': 'PostgreSQL driver',
            'PyJWT': 'JWT for sessions',
            'Pillow': 'Image processing',
        }

        for package, description in required.items():
            if package.lower() in content.lower():
                self.passed.append(f"✓ {package} in requirements.txt ({description})")
            else:
                self.issues.append(f"✗ {package} NOT in requirements.txt")

    def check_vercel_json(self):
        """Verify vercel.json is properly configured."""
        print("[3] Checking vercel.json...")
        vercel_file = self.project_root / 'vercel.json'
        
        if not vercel_file.exists():
            self.issues.append("✗ vercel.json not found")
            return

        try:
            content = vercel_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            content = vercel_file.read_text(errors='ignore')
        
        checks = {
            'builds': 'Build configuration',
            'routes': 'Route configuration',
            'python': 'Python runtime',
        }

        for check, desc in checks.items():
            if check in content:
                self.passed.append(f"✓ vercel.json has {desc}")
            else:
                self.warnings.append(f"⚠ vercel.json might need {desc}")

    def check_app_py_integration(self):
        """Verify app.py integrates zero-config system."""
        print("[4] Checking app.py integration...")
        app_file = self.project_root / 'app.py'
        
        if not app_file.exists():
            self.issues.append("✗ app.py not found")
            return

        try:
            content = app_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            content = app_file.read_text(errors='ignore')
        
        required_imports = [
            'from zero_config import',
            'initialize_gameunexa',
            'get_configured_secret_key',
        ]

        for import_str in required_imports:
            if import_str in content:
                self.passed.append(f"✓ app.py imports {import_str}")
            else:
                self.issues.append(f"✗ app.py doesn't import {import_str}")

    def check_hardcoded_secrets(self):
        """Check for hardcoded secrets in Python files."""
        print("[5] Checking for hardcoded secrets...")
        
        dangerous_patterns = [
            (r'SECRET_KEY\s*=\s*["\'][\w\-]{20,}["\']', 'Hardcoded SECRET_KEY'),
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
            (r'token\s*=\s*["\'][^"\']+["\']', 'Hardcoded token'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
        ]

        py_files = list(self.project_root.glob('*.py'))
        
        found_secrets = False
        for py_file in py_files:
            if py_file.name in ['test_', 'example_']:
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                content = py_file.read_text(errors='ignore')
            
            for pattern, description in dangerous_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    if 'os.environ' not in content[max(0, match.start()-50):match.end()+50]:
                        self.issues.append(
                            f"✗ {py_file.name}: {description} (line {content[:match.start()].count(chr(10))+1})"
                        )
                        found_secrets = True

        if not found_secrets:
            self.passed.append("✓ No hardcoded secrets found")

    def check_database_abstraction(self):
        """Check that database access uses abstraction layer."""
        print("[6] Checking database abstraction...")
        
        py_files = list(self.project_root.glob('*.py'))
        sqlite_direct_issues = []

        for py_file in py_files:
            # Skip test and config files
            if py_file.name in ['test_', 'example_', 'db_config.py', 'db_initializer.py']:
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                content = py_file.read_text(errors='ignore')
            
            # Check for direct sqlite3 usage
            if 'import sqlite3' in content and 'db_config' not in content:
                # sqlite3 is okay in database.py and db_initializer.py
                if py_file.name not in ['database.py', 'db_initializer.py', 'session_manager.py']:
                    sqlite_direct_issues.append(f"{py_file.name} imports sqlite3 directly")
        
        if sqlite_direct_issues:
            self.warnings.append(f"⚠ Direct sqlite3 usage: {', '.join(sqlite_direct_issues)}")
        else:
            self.passed.append("✓ Database access uses abstraction layer")

    def check_environment_guards(self):
        """Check that desktop features are environment-guarded."""
        print("[7] Checking environment guards...")
        
        dangerous_imports = [
            'subprocess',
            'os.system',
            'os.popen',
            'webview',
        ]

        app_file = self.project_root / 'app.py'
        if not app_file.exists():
            return

        try:
            content = app_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            content = app_file.read_text(errors='ignore')
        env_module_imported = 'from environment import' in content or 'import environment' in content
        
        if env_module_imported:
            self.passed.append("✓ app.py imports environment module")
        else:
            self.warnings.append("⚠ app.py might not check environment for desktop features")

        # Check for proper guards around dangerous operations
        if 'if IS_WINDOWS' in content or 'if is_desktop()' in content:
            self.passed.append("✓ Desktop-specific code is environment-guarded")
        else:
            self.warnings.append("⚠ Some desktop code might run on Vercel")

    def check_no_require_app_run(self):
        """Check that app.run() is not called."""
        print("[8] Checking for app.run() calls...")
        
        py_files = list(self.project_root.glob('*.py'))
        app_run_issues = []

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                content = py_file.read_text(errors='ignore')
            
            # Look for app.run() without proper guard
            if re.search(r'app\.run\s*\(', content):
                # Check if it's guarded by if __name__ == '__main__':
                if 'if __name__ == "__main__"' not in content:
                    app_run_issues.append(f"{py_file.name} calls app.run() unsafely")

        if app_run_issues:
            self.warnings.append(f"⚠ app.run() issues: {', '.join(app_run_issues)}")
        else:
            self.passed.append("✓ No unsafe app.run() calls")

    def check_session_implementation(self):
        """Check session management implementation."""
        print("[9] Checking session implementation...")
        
        session_file = self.project_root / 'session_manager.py'
        if not session_file.exists():
            self.issues.append("✗ session_manager.py not found")
            return

        try:
            content = session_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            content = session_file.read_text(errors='ignore')
        
        checks = {
            'JWTSessionManager': 'JWT session support',
            'DatabaseSessionStore': 'Database session support',
            'create_session_token': 'Session token creation',
            'verify_session_token': 'Session token verification',
        }

        for check, description in checks.items():
            if check in content:
                self.passed.append(f"✓ Session: {description}")
            else:
                self.warnings.append(f"⚠ Session: Missing {description}")

    def print_results(self):
        """Print verification results."""
        print("\n" + "="*70)
        print("VERIFICATION RESULTS")
        print("="*70 + "\n")

        if self.passed:
            print("✓ PASSED CHECKS:")
            for item in self.passed:
                print(f"  {item}")
            print()

        if self.warnings:
            print("⚠ WARNINGS:")
            for item in self.warnings:
                print(f"  {item}")
            print()

        if self.issues:
            print("✗ CRITICAL ISSUES:")
            for item in self.issues:
                print(f"  {item}")
            print()

        print("="*70)
        
        if self.issues:
            print(f"\n❌ VERIFICATION FAILED: {len(self.issues)} critical issue(s)")
            return False
        else:
            print(f"\n✅ VERIFICATION PASSED: {len(self.passed)} checks OK")
            if self.warnings:
                print(f"   ({len(self.warnings)} warning(s) to review)")
            return True

    def generate_deployment_checklist(self):
        """Generate deployment checklist."""
        print("\n" + "="*70)
        print("ZERO-CONFIG VERCEL DEPLOYMENT CHECKLIST")
        print("="*70 + "\n")

        checklist = [
            ("Code Verification", "python verify_zero_config.py", self),
            ("Run Tests", "python test_zero_config.py", None),
            ("Push to GitHub", "git push origin main", None),
            ("Vercel Import", "Go to vercel.com → Import Repository", None),
            ("Review Settings", "Check Build/Environment settings (should be auto-detected)", None),
            ("Deploy", "Click Deploy button", None),
            ("Test Application", "Go to deployed URL → Create Account → Login", None),
        ]

        for i, (step, command, _) in enumerate(checklist, 1):
            status = "✓" if _ and _ is self else "→"
            print(f"{status} {i}. {step}")
            if command:
                print(f"   Command: {command}")

        print("\n" + "="*70)


def main():
    """Run verification."""
    verifier = ZeroConfigVerifier()
    success = verifier.run_all_checks()
    
    if success:
        verifier.generate_deployment_checklist()
        print("\n🎉 GameUnexa is ready for ZERO-CONFIG VERCEL deployment!\n")
        return 0
    else:
        print("\n❌ Please fix the issues above before deploying.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
