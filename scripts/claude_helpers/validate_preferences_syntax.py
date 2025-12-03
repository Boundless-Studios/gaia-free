"""
Syntax validation for preferences models

This script validates that the model file has correct Python syntax
without requiring SQLAlchemy installation.
"""

import ast
import sys
from pathlib import Path

def validate_file_syntax(filepath):
    """Validate that a Python file has correct syntax"""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        ast.parse(code)
        print(f"✓ {filepath.name} has valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"✗ {filepath.name} has syntax error: {e}")
        return False

def check_model_structure(filepath):
    """Check that the file contains expected model classes"""
    with open(filepath, 'r') as f:
        code = f.read()

    tree = ast.parse(code)

    # Find all class definitions
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    expected_classes = ['DMPreferences', 'PlayerPreferences', 'CampaignSettings']

    for expected in expected_classes:
        if expected in classes:
            print(f"✓ Found class: {expected}")
        else:
            print(f"✗ Missing class: {expected}")
            return False

    return True

def main():
    """Run validation"""
    print("Validating preferences models syntax...\n")

    # Path to the models file
    models_file = Path(__file__).parent.parent.parent / 'db' / 'src' / 'models' / 'preferences.py'

    if not models_file.exists():
        print(f"✗ Models file not found: {models_file}")
        return 1

    print(f"Checking file: {models_file}\n")

    # Validate syntax
    if not validate_file_syntax(models_file):
        return 1

    # Check structure
    print("\nChecking model classes:")
    if not check_model_structure(models_file):
        return 1

    # Check migration file
    migration_file = Path(__file__).parent.parent.parent / 'db' / 'migrations' / '18-create-preferences-and-campaign-settings.sql'

    if migration_file.exists():
        print(f"\n✓ Migration file exists: {migration_file.name}")
        # Check if migration file has the expected tables
        with open(migration_file, 'r') as f:
            migration_content = f.read()

        expected_tables = ['dm_preferences', 'player_preferences', 'campaign_settings']
        for table in expected_tables:
            if f'CREATE TABLE IF NOT EXISTS game.{table}' in migration_content:
                print(f"✓ Migration creates table: {table}")
            else:
                print(f"✗ Migration missing table: {table}")
                return 1
    else:
        print(f"\n✗ Migration file not found: {migration_file}")
        return 1

    print("\n" + "=" * 50)
    print("✓ All validation checks passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
