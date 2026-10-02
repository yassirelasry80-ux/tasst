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
import warnings
from datetime import datetime

# ── Supprimer le warning Pandas sur SQLAlchemy ──
warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

# ── Configuration du logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
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

    args = parser.parse_args()

    try:
        entites_list = [e.strip().upper() for e in args.entites.split(",") if e.strip()] if args.entites else None
        run_production(args.env, entites_list)
    except Exception as e:
        logger.error(f"ERREUR FATALE : {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
