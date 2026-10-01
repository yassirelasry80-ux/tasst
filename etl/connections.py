"""
connections.py — Gestionnaires de connexions aux bases de données.

Oracle (X3 + BI) : oracledb (Mode Thick requis pour Oracle 11g/11c)
SQL Server (AGIRH) : pyodbc
"""

import logging
import threading
from contextlib import contextmanager
import oracledb
from etl.config import DbConfig

logger = logging.getLogger(__name__)

# ── Initialisation Thread-Safe du Client Oracle (Mode Thick) ──
_oracle_init_lock = threading.Lock()
_oracle_client_initialized = False


def _init_oracle_client():
    """Initialise le client Oracle (mode Thick) de manière thread-safe."""
    global _oracle_client_initialized
    with _oracle_init_lock:
        if _oracle_client_initialized:
            return
        try:
            oracledb.init_oracle_client()
            logger.info("Client Oracle (mode Thick) initialisé avec succès.")
        except oracledb.ProgrammingError:
            pass  # Déjà initialisé par un autre thread
        except Exception as e:
            logger.warning(f"Initialisation du client Oracle impossible (mode Thin activé) : {e}")
        finally:
            _oracle_client_initialized = True


@contextmanager
def oracle_connection(cfg: DbConfig):
    """
    Context manager pour une connexion Oracle en mode Thick.
    
    Usage:
        with oracle_connection(config.x3_oracle) as conn:
            df = pd.read_sql(query, conn)
    """
    # S'assurer que le mode Thick est initialisé pour Oracle 11g/11c
    _init_oracle_client()

    dsn = oracledb.makedsn(cfg.host, cfg.port, service_name=cfg.service_name)
    conn = None
    try:
        conn = oracledb.connect(user=cfg.user, password=cfg.password, dsn=dsn)
        logger.info(f"Connexion Oracle établie : {cfg.host}/{cfg.service_name}")
        yield conn
    except oracledb.Error as e:
        logger.error(f"Erreur de connexion Oracle ({cfg.host}): {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info(f"Connexion Oracle fermée : {cfg.host}/{cfg.service_name}")


@contextmanager
def sqlserver_connection(cfg: DbConfig):
    """
    Context manager pour une connexion SQL Server.
    
    Usage:
        with sqlserver_connection(config.agirh_sqlserver) as conn:
            df = pd.read_sql(query, conn)
    """
    import pyodbc

    conn_str = (
        f"DRIVER={{{cfg.driver}}};"
        f"SERVER={cfg.host},{cfg.port};"
        f"DATABASE={cfg.database};"
        f"UID={cfg.user};"
        f"PWD={cfg.password};"
        f"TrustServerCertificate=yes;"
    )
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        logger.info(f"Connexion SQL Server établie : {cfg.host}/{cfg.database}")
        yield conn
    except pyodbc.Error as e:
        logger.error(f"Erreur de connexion SQL Server ({cfg.host}): {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info(f"Connexion SQL Server fermée : {cfg.host}/{cfg.database}")
