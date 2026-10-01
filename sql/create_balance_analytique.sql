-- ============================================================
-- DDL : Table BALANCE_ANALYTIQUE
-- Schema : bi_{entite_name}
-- Mode   : Full Reload (TRUNCATE + INSERT)
-- ============================================================

CREATE TABLE balance_analytique (
    -- Colonnes Fonctionnelles
    NUM_PIECE       VARCHAR2(30)    NOT NULL,
    COMPTE          NUMBER(8)       NOT NULL,
    SENS            NUMBER(1)       NOT NULL,
    AXE_CENTRE      VARCHAR2(20),
    AXE_ENTITE      VARCHAR2(10),
    AXE_BLINE       VARCHAR2(30),
    AXE_SITE        VARCHAR2(10),
    MONTANT         NUMBER(15,2)    NOT NULL,
    TIERS_CODE      VARCHAR2(20),
    ARTICLE_CODE    VARCHAR2(20),
    DATE_COMPTABLE  DATE            NOT NULL,

    -- Colonnes Techniques
    SOURCE          VARCHAR2(20)    NOT NULL,
    TYPE_LIGNE      VARCHAR2(25)    NOT NULL,
    DATE_INSERTION  TIMESTAMP       DEFAULT SYSTIMESTAMP
);

-- Index sur les clés de recherche fréquentes
CREATE INDEX idx_bal_num_piece    ON balance_analytique (NUM_PIECE);
CREATE INDEX idx_bal_compte       ON balance_analytique (COMPTE);
CREATE INDEX idx_bal_date         ON balance_analytique (DATE_COMPTABLE);
CREATE INDEX idx_bal_source       ON balance_analytique (SOURCE);
CREATE INDEX idx_bal_type_ligne   ON balance_analytique (TYPE_LIGNE);

COMMENT ON TABLE balance_analytique IS 'Balance analytique multi-source — Ventilation des OD de paie et autres sources';
COMMENT ON COLUMN balance_analytique.NUM_PIECE      IS 'Référence de la pièce comptable X3 (ex: ODG2601SIG00262)';
COMMENT ON COLUMN balance_analytique.COMPTE         IS 'Numéro de compte comptable (ex: 61711001)';
COMMENT ON COLUMN balance_analytique.SENS           IS 'Sens comptable : 1=Débit, -1=Crédit';
COMMENT ON COLUMN balance_analytique.AXE_CENTRE     IS 'Code centre de coût / ETB (00000000 si COMMUN)';
COMMENT ON COLUMN balance_analytique.AXE_ENTITE     IS 'Code entité / société';
COMMENT ON COLUMN balance_analytique.AXE_BLINE      IS 'Business Line / BU (00000000 si COMMUN)';
COMMENT ON COLUMN balance_analytique.AXE_SITE       IS 'Code site / agence (00000000 si COMMUN)';
COMMENT ON COLUMN balance_analytique.MONTANT        IS 'Montant en devise locale (MAD)';
COMMENT ON COLUMN balance_analytique.SOURCE         IS 'Système source : AGIRH, COMMERCI02, etc.';
COMMENT ON COLUMN balance_analytique.TYPE_LIGNE     IS 'DETAIL, COMMUN_ECART, COMMUN_NON_VENTILE';
COMMENT ON COLUMN balance_analytique.DATE_INSERTION IS 'Horodatage d''insertion de la ligne';
