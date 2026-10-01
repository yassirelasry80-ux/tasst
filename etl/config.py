"""
config.py — Chargement direct de la configuration multi-entités depuis le fichier .env.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class DbConfig:
    """Configuration d'une connexion base de données."""
    host: str
    port: int
    user: str
    password: str
    service_name: str = ""   # Oracle
    database: str = ""       # SQL Server
    driver: str = ""         # SQL Server ODBC driver


@dataclass
class AppConfig:
    """Configuration globale de l'application pour une entité donnée."""
    entite_name: str
    start_date: str
    x3_oracle: DbConfig
    agirh_sqlserver: DbConfig
    bi_oracle: DbConfig


def get_entities_list(env_path: str = ".env") -> List[str]:
    """
    Récupère la liste des entités à traiter en boucle.
    Lit ENTITES (séparées par virgules, ex: CMGP,SICDA,PHILEA,CAS,PROCESS).
    """
    env_file = Path(env_path)
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)

    raw = os.getenv("ENTITES")
    if raw:
        entities = [e.strip().upper() for e in raw.split(",") if e.strip()]
        if entities:
            return entities

    single = os.getenv("ENTITE_NAME")
    if single:
        return [single.strip().upper()]

    return ["CMGP"]


def load_config(env_path: str = ".env", entite_name: str = None) -> AppConfig:
    """
    Charge la configuration directement depuis le fichier .env selon l'entité choisie.
    
    Args:
        env_path: Chemin vers le fichier .env (défaut : '.env').
        entite_name: Nom de l'entité (ex: CMGP, SICDA, PHILEA, CAS, PROCESS).
                     Si non spécifié, prend la première entité de ENTITES ou ENTITE_NAME.
    
    Returns:
        AppConfig: Configuration complète de l'application pour cette entité.
    """
    env_file = Path(env_path)
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)

    if not entite_name:
        entities = get_entities_list(env_path)
        entite_name = entities[0] if entities else "CMGP"

    entite_name = entite_name.strip()
    prefix = entite_name.upper()

    start_date = os.getenv("START_DATE", "01/01/2026").strip()

    # Source Oracle X3 spécifique à la filiale
    x3_oracle = DbConfig(
        host=os.getenv(f"{prefix}_DB_SOURCE_HOST", os.getenv("X3_ORACLE_HOST", "")),
        port=int(os.getenv(f"{prefix}_DB_SOURCE_PORT", os.getenv("X3_ORACLE_PORT", "1521"))),
        service_name=os.getenv(f"{prefix}_DB_SOURCE_SERVICE", os.getenv("X3_ORACLE_SERVICE", "ERPV6")),
        user=os.getenv(f"{prefix}_DB_SOURCE_USER", os.getenv("X3_ORACLE_USER", "")),
        password=os.getenv(f"{prefix}_DB_SOURCE_PASSWORD", os.getenv("X3_ORACLE_PASSWORD", "")),
    )

    # Cible Oracle BI spécifique à la filiale
    bi_oracle = DbConfig(
        host=os.getenv(f"{prefix}_DB_TARGET_HOST", os.getenv("BI_ORACLE_HOST", "")),
        port=int(os.getenv(f"{prefix}_DB_TARGET_PORT", os.getenv("BI_ORACLE_PORT", "1521"))),
        service_name=os.getenv(f"{prefix}_DB_TARGET_SERVICE", os.getenv("BI_ORACLE_SERVICE", "ERPV6")),
        user=os.getenv(f"{prefix}_DB_TARGET_USER", os.getenv("BI_ORACLE_USER", "")),
        password=os.getenv(f"{prefix}_DB_TARGET_PASSWORD", os.getenv("BI_ORACLE_PASSWORD", "")),
    )

    # Source Fils SQL Server AGIRH (partagée)
    agirh_sqlserver = DbConfig(
        host=os.getenv("AGIRH_SQLSERVER_HOST", ""),
        port=int(os.getenv("AGIRH_SQLSERVER_PORT", "1433")),
        database=os.getenv("AGIRH_SQLSERVER_DB", ""),
        user=os.getenv("AGIRH_SQLSERVER_USER", ""),
        password=os.getenv("AGIRH_SQLSERVER_PASSWORD", ""),
        driver=os.getenv("AGIRH_SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
    )

    return AppConfig(
        entite_name=entite_name,
        start_date=start_date,
        x3_oracle=x3_oracle,
        agirh_sqlserver=agirh_sqlserver,
        bi_oracle=bi_oracle,
    )
