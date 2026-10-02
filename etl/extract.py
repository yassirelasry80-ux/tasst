"""
extract.py — Extraction des données depuis X3 (Oracle) et AGIRH (SQL Server).
"""

import logging
import pandas as pd
from etl.config import AppConfig
from etl.connections import oracle_connection, sqlserver_connection
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_x3(config: AppConfig) -> pd.DataFrame:
    """
    Extrait les écritures analytiques ODP depuis Sage X3 (Oracle).
    
    Requête :
        SELECT NUM_0, ACC_0, SNS_0, AMTCUR_0, CUR_0, ACCDAT_0
        FROM {entite_name}gaccentryd
        WHERE ACCDAT_0 > :start_date AND TYP_0 = 'ODP' AND LEDTYP_0 = 2
    
    Returns:
        DataFrame avec colonnes : NUM_0, ACC_0, SNS_0, AMTCUR_0, CUR_0, ACCDAT_0
    """
    table_name = f"{config.entite_name}.gaccentryd"
    query = f"""
        SELECT 
            NUM_0,
            ACC_0,
            SNS_0,
            AMTCUR_0,
            CUR_0,
            ACCDAT_0
        FROM {table_name}
        WHERE ACCDAT_0 > :start_date
          AND ACCDAT_0 < :end_date
          AND TYP_0 = 'ODP'
          AND LEDTYP_0 = 2
    """

    start_date = config.start_date

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date[:10], "%d/%m/%Y")

    # Borne supérieure = 1er jour du mois courant (exclure le mois en cours)
    today = datetime.now()
    end_date = today.replace(day=1)

    with oracle_connection(config.x3_oracle) as conn:
        df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date})

    logger.info(
        f"X3 — {len(df)} lignes extraites depuis {table_name} "
        f"(pièces : {df['NUM_0'].nunique()}, comptes : {df['ACC_0'].nunique()})"
    )
    return df


def extract_agirh(config: AppConfig) -> pd.DataFrame:
    from calendar import monthrange

    start_date = config.start_date

    if isinstance(start_date, str):
        start_date = datetime.strptime(
            start_date[:10],
            "%d/%m/%Y"
        )

    # Générer les dates de fin de mois depuis start_date jusqu'au mois dernier (excl. mois courant)
    today = datetime.now()
    premier_jour_mois_courant = today.replace(day=1)
    dates_fin_mois = []
    current = start_date.replace(day=1)
    while current < premier_jour_mois_courant:
        last_day = monthrange(current.year, current.month)[1]
        date_str = current.replace(day=last_day).strftime("%Y%m%d")
        dates_fin_mois.append(date_str)
        # Passer au mois suivant
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    placeholders = ",".join(["?" for _ in dates_fin_mois])
    query = f"""
        SELECT *
        FROM [AGIRH_CMPG].[dbo].[COMPTA_ANALYTIQUE_CMGP_SI]
        WHERE [DT_COMPTA] IN ({placeholders})
          AND [CODE_interne] LIKE '6%'
    """

    logger.info(
        f"AGIRH — Dates fin de mois recherchées ({len(dates_fin_mois)}) : {dates_fin_mois}"
    )

    with sqlserver_connection(config.agirh_sqlserver) as conn:
        df = pd.read_sql(
            query,
            conn,
            params=dates_fin_mois
        )

    logger.info(
        f"AGIRH — {len(df)} lignes extraites "
        f"(comptes : {df['CODE_interne'].nunique()}, "
        f"ETB : {df['ETB'].nunique()}, "
        f"agences : {df['CODE_AGENCE'].nunique()})"
    )

    # Important pour transform.py
    df["DT_COMPTA"] = pd.to_datetime(
        df["DT_COMPTA"],
        errors="coerce"
    )

    return df





def extract_x3_from_excel(filepath: str) -> pd.DataFrame:
    """Extrait les données X3 depuis le fichier Excel de travail (pour tests)."""
    df = pd.read_excel(filepath, sheet_name="source X3")

    # Renommer/nettoyer pour correspondre aux noms Oracle
    cols_needed = ["NUM_0", "ACC_0", "SNS_0", "AMTCUR_0", "CUR_0", "ACCDAT_0"]
    df = df[cols_needed].copy()
    df["ACCDAT_0"] = pd.to_datetime(df["ACCDAT_0"])

    logger.info(f"X3 (Excel) — {len(df)} lignes, pièces : {df['NUM_0'].nunique()}")
    return df


def extract_agirh_from_excel(filepath: str) -> pd.DataFrame:
    """Extrait les données AGIRH depuis le fichier Excel de travail (pour tests)."""
    df = pd.read_excel(filepath, sheet_name="source agirh")

    # S'assurer des types
    df["DT_COMPTA"] = pd.to_datetime(df["DT_COMPTA"])
    df["CODE_interne"] = df["CODE_interne"].astype(int)

    logger.info(
        f"AGIRH (Excel) — {len(df)} lignes, "
        f"comptes : {df['CODE_interne'].nunique()}, "
        f"ETB : {df['ETB'].nunique()}"
    )
    return df
