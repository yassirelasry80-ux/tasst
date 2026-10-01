"""
extract.py — Extraction des données depuis X3 (Oracle) et AGIRH (SQL Server).
"""

import logging
import pandas as pd
from etl.config import AppConfig
from etl.connections import oracle_connection, sqlserver_connection

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
    table_name = f"{config.entite_name}gaccentryd"
    query = f"""
        SELECT 
            NUM_0,
            ACC_0,
            SNS_0,
            AMTCUR_0,
            CUR_0,
            ACCDAT_0
        FROM {table_name}
        WHERE ACCDAT_0 > TO_DATE(:start_date, 'YYYY-MM-DD')
          AND TYP_0 = 'ODP'
          AND LEDTYP_0 = 2
    """

    with oracle_connection(config.x3_oracle) as conn:
        df = pd.read_sql(query, conn, params={"start_date": config.start_date})

    logger.info(
        f"X3 — {len(df)} lignes extraites depuis {table_name} "
        f"(pièces : {df['NUM_0'].nunique()}, comptes : {df['ACC_0'].nunique()})"
    )
    return df


def extract_agirh(config: AppConfig) -> pd.DataFrame:
    """
    Extrait le détail analytique de paie depuis AGIRH (SQL Server).
    
    ⚠️  Requête à intégrer ultérieurement.
         Filtres attendus : date comptable, journal, société.
         Colonnes attendues : CODE_interne, ETB, SU, CODE_AGENCE, AGENCE,
                              TYPE_ORGANISATION, INTITULE_TO, mt, debit, credit,
                              DT_COMPTA, ste, journal, rubrique
    
    Returns:
        DataFrame avec les colonnes AGIRH.
    """
    # ──────────────────────────────────────────────────────────
    # TODO : Remplacer par la requête AGIRH définitive
    # Filtres prévus : date comptable, journal (PAIE), société
    # ──────────────────────────────────────────────────────────
    query = """
        -- PLACEHOLDER : requête AGIRH à intégrer ultérieurement
        -- SELECT 
        --     CODE_interne, ETB, SU, CODE_AGENCE, AGENCE,
        --     TYPE_ORGANISATION, INTITULE_TO,
        --     mt, debit, credit,
        --     DT_COMPTA, ste, journal, rubrique
        -- FROM ???
        -- WHERE DT_COMPTA > @start_date
        --   AND journal = 'PAIE'
        --   AND ste = @entite_name
        SELECT 1  -- placeholder, lèvera une erreur si exécuté tel quel
    """
    raise NotImplementedError(
        "La requête AGIRH n'est pas encore définie. "
        "Veuillez compléter la fonction extract_agirh() dans etl/extract.py."
    )

    # Code qui sera exécuté une fois la requête définie :
    # with sqlserver_connection(config.agirh_sqlserver) as conn:
    #     df = pd.read_sql(query, conn, params={"start_date": config.start_date})
    #
    # logger.info(
    #     f"AGIRH — {len(df)} lignes extraites "
    #     f"(comptes : {df['CODE_interne'].nunique()}, "
    #     f"ETB : {df['ETB'].nunique()}, "
    #     f"agences : {df['CODE_AGENCE'].nunique()})"
    # )
    # return df


# ─── Fonctions de test (lecture depuis Excel) ────────────────

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
