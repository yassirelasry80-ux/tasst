"""
load.py — Chargement dans la table cible bi_{entite_name}.balance_analytique (Oracle BI).
Mode : Full Reload (TRUNCATE + INSERT).
"""

import logging
import pandas as pd
from etl.config import AppConfig
from etl.connections import oracle_connection

logger = logging.getLogger(__name__)

# Mapping colonnes DataFrame → colonnes Oracle
COLUMNS_ORDER = [
    "NUM_PIECE", "COMPTE", "SENS", "AXE_CENTRE", "AXE_ENTITE",
    "AXE_BLINE", "AXE_SITE", "MONTANT", "TIERS_CODE", "ARTICLE_CODE",
    "DATE_COMPTABLE", "SOURCE", "TYPE_LIGNE",
]

BATCH_SIZE = 500


def load(df: pd.DataFrame, config: AppConfig) -> int:
    """
    Charge le DataFrame dans balance_analytique en mode Full Reload.
    
    1. TRUNCATE de la table
    2. INSERT par batch
    3. COMMIT
    
    Args:
        df: DataFrame issu de transform().
        config: Configuration de l'application.
    
    Returns:
        Nombre de lignes insérées.
    """
    schema = f"bi_{config.entite_name.lower()}"
    table = f"{schema}.balance_analytique"

    # Préparer les données
    df_load = df[COLUMNS_ORDER].copy()
    df_load["DATE_COMPTABLE"] = pd.to_datetime(df_load["DATE_COMPTABLE"])

    # Remplacer NaN par None pour Oracle
    df_load = df_load.where(pd.notnull(df_load), None)

    with oracle_connection(config.bi_oracle) as conn:
        cursor = conn.cursor()

        # ── TRUNCATE ──
        logger.info(f"TRUNCATE TABLE {table}")
        cursor.execute(f"TRUNCATE TABLE {table}")

        # ── INSERT ──
        insert_sql = f"""
            INSERT INTO {table} (
                NUM_PIECE, COMPTE, SENS, AXE_CENTRE, AXE_ENTITE,
                AXE_BLINE, AXE_SITE, MONTANT, TIERS_CODE, ARTICLE_CODE,
                DATE_COMPTABLE, SOURCE, TYPE_LIGNE, DATE_INSERTION
            ) VALUES (
                :1, :2, :3, :4, :5,
                :6, :7, :8, :9, :10,
                :11, :12, :13, SYSTIMESTAMP
            )
        """

        # Préparer les tuples pour executemany
        rows = df_load.values.tolist()
        total_inserted = 0

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            cursor.executemany(insert_sql, batch)
            total_inserted += len(batch)
            logger.debug(f"  Batch inséré : {total_inserted}/{len(rows)}")

        conn.commit()
        logger.info(f"[OK] {total_inserted} lignes insérées dans {table}")

        cursor.close()

    return total_inserted
