#!/usr/bin/env python3
"""
Script de sauvegarde de la base de données
Chiffre et sauvegarde les données sensibles
"""

import os
import subprocess
from datetime import datetime
from cryptography.fernet import Fernet

def backup_database():
    """Sauvegarde chiffrée de la base de données"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.sql"

    # Commande mysqldump (adapter selon config)
    db_config = {
        'host': os.environ.get('DB_HOST', 'db'),
        'user': os.environ.get('DB_USER', 'academique'),
        'password': os.environ.get('DB_PASSWORD', 'academique'),
        'database': 'academique'
    }

    cmd = [
        'mysqldump',
        f"--host={db_config['host']}",
        f"--user={db_config['user']}",
        f"--password={db_config['password']}",
        db_config['database']
    ]

    try:
        with open(backup_file, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)

        # Chiffrer le fichier de sauvegarde
        key = os.environ.get('FERNET_KEY')
        if key:
            fernet = Fernet(key.encode())
            with open(backup_file, 'rb') as f:
                data = f.read()
            encrypted = fernet.encrypt(data)
            with open(f"{backup_file}.enc", 'wb') as f:
                f.write(encrypted)
            os.remove(backup_file)  # Supprimer le fichier non chiffré
            backup_file = f"{backup_file}.enc"

        print(f"Sauvegarde créée: {backup_file}")
        return True

    except Exception as e:
        print(f"Erreur sauvegarde: {e}")
        return False

if __name__ == "__main__":
    backup_database()