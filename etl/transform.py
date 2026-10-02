"""
transform.py — Logique métier de ventilation analytique.

Règles :
    R1 — Équilibre : Σ(MONTANT) par (NUM_PIECE, COMPTE) = montant père X3
    R2 — Jointure : X3 LEFT JOIN AGIRH sur ACC_0 = CODE_interne (par mois)
    R3 — Écart → COMMUN_ECART avec AXE_* = '00000000'
    R4 — Non ventilé → COMMUN_NON_VENTILE avec AXE_* = '00000000'
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

COMMUN = "00000000"
TOLERANCE_ECART = 0.005  # Tolérance arrondi en MAD


def transform(df_x3: pd.DataFrame, df_agirh: pd.DataFrame) -> pd.DataFrame:
    """
    Traitement principal : X3 LEFT JOIN AGIRH, mois par mois.
    
    Args:
        df_x3: Données père (Sage X3). Colonnes : NUM_0, ACC_0, SNS_0, AMTCUR_0, CUR_0, ACCDAT_0
        df_agirh: Données fils (AGIRH). Colonnes : CODE_interne, ETB, SU, CODE_AGENCE, AGENCE,
                  TYPE_ORGANISATION, INTITULE_TO, mt, DT_COMPTA, ste, ...
    
    Returns:
        DataFrame prêt à insérer dans balance_analytique.
    """
    # ── Préparer les périodes mensuelles ──
    df_x3 = df_x3.copy()
    df_agirh = df_agirh.copy()
    df_x3["_mois"] = df_x3["ACCDAT_0"].dt.to_period("M")
    df_agirh["_mois"] = df_agirh["DT_COMPTA"].dt.to_period("M")

    mois_x3 = sorted(df_x3["_mois"].unique())
    logger.info(f"Mois à traiter : {[str(m) for m in mois_x3]}")

    all_results: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    # ── Itération mois par mois ──
    for mois in mois_x3:
        x3_mois = df_x3[df_x3["_mois"] == mois]
        agirh_mois = df_agirh[df_agirh["_mois"] == mois]

        logger.info(
            f"Mois {mois} : X3={len(x3_mois)} lignes, "
            f"AGIRH={len(agirh_mois)} lignes"
        )

        # Vérifier unicité de la pièce ODP pour ce mois
        pieces = x3_mois["NUM_0"].unique()
        if len(pieces) > 1:
            logger.warning(
                f"Mois {mois} : {len(pieces)} pièces ODP détectées ({pieces}). "
                f"Traitement pièce par pièce."
            )

        for num_piece in pieces:
            results_piece = _process_piece(
                num_piece=num_piece,
                x3_piece=x3_mois[x3_mois["NUM_0"] == num_piece],
                agirh_mois=agirh_mois,
                anomalies=anomalies,
            )
            all_results.extend(results_piece)

        # ── Détecter les orphelins AGIRH (fils sans père) ──
        comptes_x3 = set(x3_mois["ACC_0"].unique())
        comptes_agirh = set(agirh_mois["CODE_interne"].unique())
        orphelins = comptes_agirh - comptes_x3
        if orphelins:
            logger.warning(
                f"Mois {mois} : {len(orphelins)} compte(s) AGIRH orphelin(s) "
                f"(sans père X3) : {orphelins}"
            )
            for acc in orphelins:
                anomalies.append({
                    "mois": str(mois),
                    "compte": acc,
                    "type": "ORPHELIN_AGIRH",
                    "detail": "Compte présent dans AGIRH mais absent dans X3",
                })

    # ── Log des anomalies ──
    if anomalies:
        logger.warning(f"Total anomalies détectées : {len(anomalies)}")
        for a in anomalies:
            logger.warning(f"  ANOMALIE [{a['type']}] mois={a['mois']} compte={a['compte']} : {a['detail']}")

    # ── Construire le DataFrame résultat ──
    df_result = pd.DataFrame(all_results)

    if df_result.empty:
        logger.warning("Aucune ligne générée.")
        return _empty_result()

    # Vérification finale de l'équilibre
    _verify_equilibre(df_x3, df_result)

    logger.info(
        f"Transformation terminée : {len(df_result)} lignes générées "
        f"(DETAIL: {(df_result['TYPE_LIGNE'] == 'DETAIL').sum()}, "
        f"COMMUN_ECART: {(df_result['TYPE_LIGNE'] == 'COMMUN_ECART').sum()}, "
        f"COMMUN_NON_VENTILE: {(df_result['TYPE_LIGNE'] == 'COMMUN_NON_VENTILE').sum()})"
    )
    return df_result


def _process_piece(
    num_piece: str,
    x3_piece: pd.DataFrame,
    agirh_mois: pd.DataFrame,
    anomalies: list,
) -> List[Dict[str, Any]]:
    """
    Traite une pièce ODP : X3 LEFT JOIN AGIRH par compte.
    
    Returns:
        Liste de dicts représentant les lignes de balance_analytique.
    """
    results = []

    # Agréger X3 par compte (au cas où plusieurs lignes par compte)
    x3_agg = (
        x3_piece
        .groupby("ACC_0", as_index=False)
        .agg(
            AMTCUR_0=("AMTCUR_0", "sum"),
            SNS_0=("SNS_0", "first"),
            ACCDAT_0=("ACCDAT_0", "first"),
        )
    )

    for _, x3_row in x3_agg.iterrows():
        acc = int(x3_row["ACC_0"])
        montant_pere = x3_row["AMTCUR_0"]
        sens = int(x3_row["SNS_0"])
        date_comptable = x3_row["ACCDAT_0"]

        # ── LEFT JOIN : chercher les fils AGIRH ──
        fils = agirh_mois[agirh_mois["CODE_interne"] == acc]

        if fils.empty:
            # ── CAS 2 : Père sans fils → COMMUN_NON_VENTILE ──
            results.append(_make_row(
                num_piece=num_piece,
                compte=acc,
                sens=sens,
                axe_centre=COMMUN,
                axe_entite=COMMUN,
                axe_bline=COMMUN,
                axe_site=COMMUN,
                montant=round(montant_pere, 2),
                date_comptable=date_comptable,
                source="AGIRH",
                type_ligne="COMMUN_NON_VENTILE",
            ))
            logger.debug(
                f"  Compte {acc} : NON VENTILÉ → COMMUN ({montant_pere:.2f})"
            )
        else:
            # ── CAS 1/3 : Père avec fils → DETAIL + éventuel ECART ──
            total_agirh = 0.0

            for _, ag_row in fils.iterrows():
                mt = ag_row["mt"]
                total_agirh += mt

                results.append(_make_row(
                    num_piece=num_piece,
                    compte=acc,
                    sens=sens,
                    axe_centre=str(ag_row.get("ETB", COMMUN)),
                    axe_entite=str(ag_row.get("ste", "")),
                    axe_bline=COMMUN,
                    axe_site=str(ag_row.get("CODE_AGENCE", COMMUN)),
                    montant=round(mt, 2),
                    date_comptable=date_comptable,
                    source="AGIRH",
                    type_ligne="DETAIL",
                ))

            # ── Calcul de l'écart ──
            ecart = round(montant_pere - total_agirh, 2)

            if abs(ecart) >= TOLERANCE_ECART:
                # CAS 1 : écart → ligne COMMUN_ECART
                results.append(_make_row(
                    num_piece=num_piece,
                    compte=acc,
                    sens=sens,
                    axe_centre=COMMUN,
                    axe_entite=str(fils.iloc[0].get("ste", "")),
                    axe_bline=COMMUN,
                    axe_site=COMMUN,
                    montant=ecart,
                    date_comptable=date_comptable,
                    source="AGIRH",
                    type_ligne="COMMUN_ECART",
                ))
                logger.info(
                    f"  Compte {acc} : ecart = {ecart:+.2f} "
                    f"(X3={montant_pere:.2f}, AGIRH={total_agirh:.2f}) -> COMMUN_ECART"
                )
            else:
                logger.debug(
                    f"  Compte {acc} : équilibré "
                    f"(X3={montant_pere:.2f}, AGIRH={total_agirh:.2f})"
                )

    return results


def _make_row(
    num_piece: str,
    compte: int,
    sens: int,
    axe_centre: str,
    axe_entite: str,
    axe_bline: str,
    axe_site: str,
    montant: float,
    date_comptable,
    source: str,
    type_ligne: str,
) -> Dict[str, Any]:
    """Construit un dict représentant une ligne de balance_analytique."""
    return {
        "NUM_PIECE": num_piece,
        "COMPTE": compte,
        "SENS": sens,
        "AXE_CENTRE": axe_centre,
        "AXE_ENTITE": axe_entite,
        "AXE_BLINE": axe_bline,
        "AXE_SITE": axe_site,
        "MONTANT": montant,
        "TIERS_CODE": None,
        "ARTICLE_CODE": None,
        "DATE_COMPTABLE": date_comptable,
        "SOURCE": source,
        "TYPE_LIGNE": type_ligne,
    }


def _verify_equilibre(df_x3: pd.DataFrame, df_result: pd.DataFrame) -> None:
    """
    Vérification post-traitement : pour chaque (NUM_PIECE, COMPTE),
    la somme des MONTANT dans le résultat doit égaler le AMTCUR_0 de X3.
    """
    # Somme X3 par (NUM_0, ACC_0)
    x3_totals = (
        df_x3
        .groupby(["NUM_0", "ACC_0"], as_index=False)["AMTCUR_0"]
        .sum()
    )

    # Somme résultat par (NUM_PIECE, COMPTE)
    res_totals = (
        df_result
        .groupby(["NUM_PIECE", "COMPTE"], as_index=False)["MONTANT"]
        .sum()
    )
    

    # Harmoniser les types pour la jointure (str)
    x3_totals["ACC_0"] = x3_totals["ACC_0"].astype(str).str.strip()
    res_totals["COMPTE"] = res_totals["COMPTE"].astype(str).str.strip()

    # Rapprocher
    merged = pd.merge(
        x3_totals,
        res_totals,
        left_on=["NUM_0", "ACC_0"],
        right_on=["NUM_PIECE", "COMPTE"],
        how="left",
    )
    merged["DIFF"] = (merged["AMTCUR_0"] - merged["MONTANT"]).round(2)

    desequilibres = merged[merged["DIFF"].abs() >= TOLERANCE_ECART]
    if not desequilibres.empty:
        logger.error(
            f"DESEQUILIBRE DETECTE sur {len(desequilibres)} compte(s) :"
        )
        for _, row in desequilibres.iterrows():
            logger.error(
                f"  NUM_PIECE={row['NUM_0']}, COMPTE={row['ACC_0']}, "
                f"X3={row['AMTCUR_0']:.2f}, BALANCE={row['MONTANT']:.2f}, "
                f"DIFF={row['DIFF']:.2f}"
            )
    else:
        logger.info("[OK] Verification d'equilibre reussie -- tous les comptes sont equilibres.")


def _empty_result() -> pd.DataFrame:
    """Retourne un DataFrame vide avec le schéma attendu."""
    return pd.DataFrame(columns=[
        "NUM_PIECE", "COMPTE", "SENS", "AXE_CENTRE", "AXE_ENTITE",
        "AXE_BLINE", "AXE_SITE", "MONTANT", "TIERS_CODE", "ARTICLE_CODE",
        "DATE_COMPTABLE", "SOURCE", "TYPE_LIGNE",
    ])
