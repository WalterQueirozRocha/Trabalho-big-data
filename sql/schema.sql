DROP VIEW IF EXISTS vw_reconciliacao_fontes, vw_diferenca_grupo;
DROP TABLE IF EXISTS fato_atendimento_grupo, fato_atendimento_csv, processo_tratado,
    dim_grande_area, dim_linha_fomento, dim_modalidade, dim_regiao;

CREATE TABLE dim_grande_area   (id SMALLSERIAL PRIMARY KEY, nome VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE dim_linha_fomento (id SMALLSERIAL PRIMARY KEY, nome VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE dim_modalidade    (id SMALLSERIAL PRIMARY KEY, nome VARCHAR(80)  UNIQUE NOT NULL);
CREATE TABLE dim_regiao        (id SMALLSERIAL PRIMARY KEY, nome VARCHAR(20)  UNIQUE NOT NULL);

CREATE TABLE fato_atendimento_grupo (
    ano_chamada      SMALLINT      NOT NULL,
    sexo             VARCHAR(20)   NOT NULL,
    raca_cor         VARCHAR(30)   NOT NULL,
    grande_area_id   SMALLINT      REFERENCES dim_grande_area,
    linha_fomento_id SMALLINT      REFERENCES dim_linha_fomento,
    modalidade_id    SMALLINT      REFERENCES dim_modalidade,
    regiao_id        SMALLINT      REFERENCES dim_regiao,
    qtd_demandada    INTEGER       NOT NULL CHECK (qtd_demandada > 0),
    qtd_atendida     INTEGER       NOT NULL CHECK (qtd_atendida >= 0),
    valor_demandado  NUMERIC(16,2),
    valor_atendido   NUMERIC(16,2),
    taxa_atendimento NUMERIC(7,4)  GENERATED ALWAYS AS (qtd_atendida::numeric / qtd_demandada) STORED
);

CREATE TABLE fato_atendimento_csv (
    ano_chamada      SMALLINT      NOT NULL,
    grande_area_id   SMALLINT      REFERENCES dim_grande_area,
    linha_fomento_id SMALLINT      REFERENCES dim_linha_fomento,
    modalidade_id    SMALLINT      REFERENCES dim_modalidade,
    regiao_id        SMALLINT      REFERENCES dim_regiao,
    qtd_demandada    INTEGER       NOT NULL CHECK (qtd_demandada > 0),
    qtd_atendida     INTEGER       NOT NULL CHECK (qtd_atendida >= 0),
    valor_demandado  NUMERIC(16,2),
    valor_atendido   NUMERIC(16,2)
);

CREATE TABLE processo_tratado (
    nu_processo       VARCHAR(20)   PRIMARY KEY,
    ano_chamada       SMALLINT      NOT NULL,
    grande_area_id    SMALLINT      REFERENCES dim_grande_area,
    linha_fomento_id  SMALLINT      REFERENCES dim_linha_fomento,
    modalidade_id     SMALLINT      REFERENCES dim_modalidade,
    regiao_id         SMALLINT      REFERENCES dim_regiao,
    sigla_uf          CHAR(2),
    cidade            VARCHAR(80),
    sigla_instituicao VARCHAR(30),
    instituicao       VARCHAR(200),
    pais              VARCHAR(60),
    atendido          BOOLEAN       NOT NULL,
    valor_demandado   NUMERIC(16,2),
    valor_atendido    NUMERIC(16,2)
);

CREATE VIEW vw_diferenca_grupo AS
WITH grupo AS (
    SELECT ano_chamada, grande_area_id, sexo, raca_cor,
           SUM(qtd_demandada) AS qtd_demandada,
           SUM(qtd_atendida)  AS qtd_atendida,
           (SUM(qtd_atendida)::numeric / SUM(qtd_demandada))::numeric(7,4) AS taxa_atendimento
    FROM fato_atendimento_grupo
    GROUP BY ano_chamada, grande_area_id, sexo, raca_cor
)
SELECT g.ano_chamada, a.nome AS grande_area, g.sexo, g.raca_cor,
       g.qtd_demandada, g.qtd_atendida, g.taxa_atendimento,
       (g.taxa_atendimento - r.taxa_atendimento)::numeric(7,4) AS diferenca_grupo
FROM grupo g
JOIN dim_grande_area a ON a.id = g.grande_area_id
LEFT JOIN grupo r ON r.ano_chamada = g.ano_chamada AND r.grande_area_id = g.grande_area_id
                 AND r.sexo = 'Masculino' AND r.raca_cor = 'Branca';

CREATE VIEW vw_reconciliacao_fontes AS
WITH painel AS (
    SELECT ano_chamada, grande_area_id, linha_fomento_id,
           SUM(qtd_demandada) AS qtd_demandada, SUM(qtd_atendida) AS qtd_atendida, SUM(valor_demandado) AS valor_demandado
    FROM fato_atendimento_grupo
    GROUP BY ano_chamada, grande_area_id, linha_fomento_id
), csv AS (
    SELECT ano_chamada, grande_area_id, linha_fomento_id,
           SUM(qtd_demandada) AS qtd_demandada, SUM(qtd_atendida) AS qtd_atendida, SUM(valor_demandado) AS valor_demandado
    FROM fato_atendimento_csv
    GROUP BY ano_chamada, grande_area_id, linha_fomento_id
)
SELECT ano_chamada, a.nome AS grande_area, l.nome AS linha_fomento,
       p.qtd_demandada AS qtd_demandada_painel, c.qtd_demandada AS qtd_demandada_csv,
       COALESCE(p.qtd_demandada, 0) - COALESCE(c.qtd_demandada, 0) AS diferenca_qtd_demandada,
       p.qtd_atendida AS qtd_atendida_painel, c.qtd_atendida AS qtd_atendida_csv,
       p.valor_demandado AS valor_demandado_painel, c.valor_demandado AS valor_demandado_csv
FROM painel p
FULL JOIN csv c USING (ano_chamada, grande_area_id, linha_fomento_id)
JOIN dim_grande_area a ON a.id = grande_area_id
JOIN dim_linha_fomento l ON l.id = linha_fomento_id;
