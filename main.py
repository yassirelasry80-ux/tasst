"""
main.py — Point d'entrée du pipeline de ventilation analytique ODP.

Usage :
    # Mode production (connexions DB avec variables dans .env)
    python main.py

    # Ou spécifier un autre fichier .env
    python main.py --env .env.prod

    # Mode test (depuis fichier Excel)
    python main.py --test --excel "Ventilation ANA ODP.xlsx"
"""

import argparse
import logging
import sys
from datetime import datetime

# ── Configuration du logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"ventilation_analytique_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("main")


def run_production(env_path: str = ".env", entites: list = None):
    """
    Pipeline complet : boucle sur chaque entité configurée.
    Pour chaque entité : Extract (X3 & AGIRH) → Transform → Load (Oracle BI).
    """
    from etl.config import load_config, get_entities_list
    from etl.extract import extract_x3, extract_agirh
    from etl.transform import transform
    from etl.load import load

    if not entites:
        entites = get_entities_list(env_path)

    logger.info("=" * 65)
    logger.info("DÉMARRAGE — Pipeline Ventilation Analytique ODP (Multi-Entités)")
    logger.info(f"Entités à traiter ({len(entites)}) : {', '.join(entites)}")
    logger.info("=" * 65)

    resultats = {}

    for i, entite in enumerate(entites, 1):
        logger.info("-" * 65)
        logger.info(f"[{i}/{len(entites)}] TRAITEMENT DE L'ENTITÉ : {entite}")
        logger.info("-" * 65)

        try:
            # 1. Configuration de l'entité
            config = load_config(env_path, entite)
            logger.info(f"Source X3 : {config.x3_oracle.user}@{config.x3_oracle.host}:{config.x3_oracle.port}/{config.x3_oracle.service_name}")
            logger.info(f"Cible BI  : {config.bi_oracle.user}@{config.bi_oracle.host}:{config.bi_oracle.port}/{config.bi_oracle.service_name}")

            # 2. Extraction
            logger.info(f"[{entite}] -- EXTRACTION --")
            df_x3 = extract_x3(config)
            df_agirh = extract_agirh(config)

            # 3. Transformation
            logger.info(f"[{entite}] -- TRANSFORMATION --")
            df_balance = transform(df_x3, df_agirh)

            # 4. Chargement
            logger.info(f"[{entite}] -- CHARGEMENT --")
            nb_lignes = load(df_balance, config)

            resultats[entite] = {"statut": "OK", "lignes": nb_lignes, "erreur": None}
            logger.info(f"[{entite}] [SUCCES] {nb_lignes} lignes chargées dans bi_{config.entite_name.lower()}.balance_analytique")

        except Exception as e:
            logger.error(f"[{entite}] [ERREUR] Échec du traitement : {e}", exc_info=True)
            resultats[entite] = {"statut": "KO", "lignes": 0, "erreur": str(e)}

    # Rapport récapitulatif global
    print()
    print("+" + "=" * 63 + "+")
    print("|            RÉCAPITULATIF D'EXÉCUTION MULTI-ENTITÉS            |")
    print("+" + "=" * 63 + "+")
    print("|  Entité    | Statut | Lignes chargées | Commentaire           |")
    print("|  ----------+--------+-----------------+---------------------- |")
    for ent, res in resultats.items():
        stat = "[OK]" if res["statut"] == "OK" else "[KO]"
        err_msg = "" if res["statut"] == "OK" else (res["erreur"][:20] + "..." if len(res["erreur"]) > 20 else res["erreur"])
        print(f"|  {ent:<10}| {stat:<7}| {res['lignes']:>15} | {err_msg:<22}|")
    print("+" + "=" * 63 + "+")
    print()


def run_test(excel_path: str, output_csv: str = None):
    """Pipeline de test : Extract (Excel) → Transform → Export CSV."""
    from etl.extract import extract_x3_from_excel, extract_agirh_from_excel
    from etl.transform import transform
    from etl.load import load_to_csv

    logger.info("=" * 60)
    logger.info("DÉMARRAGE — Mode TEST (depuis Excel)")
    logger.info(f"Fichier source : {excel_path}")
    logger.info("=" * 60)

    # 1. Extraction depuis Excel
    logger.info("-- EXTRACTION (Excel) --")
    df_x3 = extract_x3_from_excel(excel_path)
    df_agirh = extract_agirh_from_excel(excel_path)

    # 2. Transformation
    logger.info("-- TRANSFORMATION --")
    df_balance = transform(df_x3, df_agirh)

    # 3. Rapport de validation
    logger.info("-- RAPPORT DE VALIDATION --")
    _print_validation_report(df_x3, df_agirh, df_balance)

    # 4. Export CSV
    if output_csv is None:
        output_csv = "balance_analytique_test.csv"
    logger.info("-- EXPORT CSV --")
    load_to_csv(df_balance, output_csv)

    logger.info("=" * 60)
    logger.info(f"TERMINÉ — {len(df_balance)} lignes exportées vers {output_csv}")
    logger.info("=" * 60)

    return df_balance


def _print_validation_report(df_x3, df_agirh, df_balance):
    """Affiche un rapport de validation détaillé."""
    import pandas as pd

    print()
    print("+" + "="*62 + "+")
    print("|       RAPPORT DE VALIDATION -- BALANCE ANALYTIQUE           |")
    print("+" + "="*62 + "+")

    # Resume global
    n_detail = (df_balance["TYPE_LIGNE"] == "DETAIL").sum()
    n_ecart = (df_balance["TYPE_LIGNE"] == "COMMUN_ECART").sum()
    n_nonvent = (df_balance["TYPE_LIGNE"] == "COMMUN_NON_VENTILE").sum()

    print(f"|  Lignes X3 (pere)           : {len(df_x3):>6}                       |")
    print(f"|  Lignes AGIRH (fils)        : {len(df_agirh):>6}                       |")
    print("|" + "-"*62 + "|")
    print(f"|  Lignes DETAIL generees     : {n_detail:>6}                       |")
    print(f"|  Lignes COMMUN_ECART        : {n_ecart:>6}                       |")
    print(f"|  Lignes COMMUN_NON_VENTILE  : {n_nonvent:>6}                       |")
    print(f"|  TOTAL lignes balance       : {len(df_balance):>6}                       |")

    # Detail par compte
    print("+" + "="*62 + "+")
    print("|  DETAIL PAR COMPTE                                         |")
    print("+" + "="*62 + "+")
    print("|  Compte   | X3 (Pere)     | Sum Balance | Ecart     | OK?  |")
    print("|  ---------+---------------+-------------+-----------+----- |")

    x3_totals = df_x3.groupby("ACC_0")["AMTCUR_0"].sum()
    bal_totals = df_balance.groupby("COMPTE")["MONTANT"].sum()

    for acc in sorted(x3_totals.index):
        x3_val = x3_totals[acc]
        bal_val = bal_totals.get(acc, 0)
        diff = round(x3_val - bal_val, 2)
        ok = "[OK]" if abs(diff) < 0.01 else "[KO]"
        print(f"|  {acc:<9}| {x3_val:>13,.2f} | {bal_val:>11,.2f} | {diff:>9,.2f} | {ok} |")

    total_x3 = x3_totals.sum()
    total_bal = bal_totals.sum()
    total_diff = round(total_x3 - total_bal, 2)
    total_ok = "[OK]" if abs(total_diff) < 0.01 else "[KO]"

    print("|  ---------+---------------+-------------+-----------+----- |")
    print(f"|  TOTAL    | {total_x3:>13,.2f} | {total_bal:>11,.2f} | {total_diff:>9,.2f} | {total_ok} |")
    print("+" + "="*62 + "+")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de ventilation analytique ODP"
    )
    parser.add_argument(
        "--entites", "-e", default=None,
        help="Entité(s) à traiter, séparées par virgules (ex: CMGP,SICDA). Défaut : toutes les entités de ENTITES dans le .env"
    )
    parser.add_argument(
        "--env", default=".env",
        help="Chemin vers le fichier .env (défaut : .env)"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Mode test : lecture depuis Excel, export CSV"
    )
    parser.add_argument(
        "--excel", default="Ventilation ANA ODP.xlsx",
        help="Chemin vers le fichier Excel source (mode test)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Chemin du fichier CSV de sortie (mode test)"
    )

    args = parser.parse_args()

    try:
        if args.test:
            run_test(args.excel, args.output)
        else:
            entites_list = [e.strip().upper() for e in args.entites.split(",") if e.strip()] if args.entites else None
            run_production(args.env, entites_list)
    except Exception as e:
        logger.error(f"ERREUR FATALE : {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
