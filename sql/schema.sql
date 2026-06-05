-- OMOP CDM v5.4 — tables used by this thesis
-- Run once against the omop database before ETL

CREATE SCHEMA IF NOT EXISTS cdm;

-- Clinical tables

CREATE TABLE IF NOT EXISTS cdm.person (
    person_id                   INTEGER     NOT NULL,
    gender_concept_id           INTEGER     NOT NULL,
    year_of_birth               INTEGER     NOT NULL,
    month_of_birth              INTEGER,
    day_of_birth                INTEGER,
    birth_datetime              TIMESTAMP,
    race_concept_id             INTEGER     NOT NULL,
    ethnicity_concept_id        INTEGER     NOT NULL,
    location_id                 INTEGER,
    provider_id                 INTEGER,
    care_site_id                INTEGER,
    person_source_value         VARCHAR(50),
    gender_source_value         VARCHAR(50),
    gender_source_concept_id    INTEGER,
    race_source_value           VARCHAR(50),
    race_source_concept_id      INTEGER,
    ethnicity_source_value      VARCHAR(50),
    ethnicity_source_concept_id INTEGER,
    PRIMARY KEY (person_id)
);

CREATE TABLE IF NOT EXISTS cdm.visit_occurrence (
    visit_occurrence_id           INTEGER   NOT NULL,
    person_id                     INTEGER   NOT NULL,
    visit_concept_id              INTEGER   NOT NULL,
    visit_start_date              DATE      NOT NULL,
    visit_start_datetime          TIMESTAMP,
    visit_end_date                DATE      NOT NULL,
    visit_end_datetime            TIMESTAMP,
    visit_type_concept_id         INTEGER   NOT NULL,
    provider_id                   INTEGER,
    care_site_id                  INTEGER,
    visit_source_value            VARCHAR(50),
    visit_source_concept_id       INTEGER,
    admitted_from_concept_id      INTEGER,
    admitted_from_source_value    VARCHAR(50),
    discharge_to_concept_id       INTEGER,
    discharge_to_source_value     VARCHAR(50),
    preceding_visit_occurrence_id INTEGER,
    PRIMARY KEY (visit_occurrence_id)
);

CREATE TABLE IF NOT EXISTS cdm.condition_occurrence (
    condition_occurrence_id       INTEGER   NOT NULL,
    person_id                     INTEGER   NOT NULL,
    condition_concept_id          INTEGER   NOT NULL,
    condition_start_date          DATE      NOT NULL,
    condition_start_datetime      TIMESTAMP,
    condition_end_date            DATE,
    condition_end_datetime        TIMESTAMP,
    condition_type_concept_id     INTEGER   NOT NULL,
    condition_status_concept_id   INTEGER,
    stop_reason                   VARCHAR(20),
    provider_id                   INTEGER,
    visit_occurrence_id           INTEGER,
    visit_detail_id               INTEGER,
    condition_source_value        VARCHAR(50),
    condition_source_concept_id   INTEGER,
    condition_status_source_value VARCHAR(50),
    PRIMARY KEY (condition_occurrence_id)
);

CREATE TABLE IF NOT EXISTS cdm.drug_exposure (
    drug_exposure_id              INTEGER   NOT NULL,
    person_id                     INTEGER   NOT NULL,
    drug_concept_id               INTEGER   NOT NULL,
    drug_exposure_start_date      DATE      NOT NULL,
    drug_exposure_start_datetime  TIMESTAMP,
    drug_exposure_end_date        DATE,
    drug_exposure_end_datetime    TIMESTAMP,
    verbatim_end_date             DATE,
    drug_type_concept_id          INTEGER   NOT NULL,
    stop_reason                   VARCHAR(20),
    refills                       INTEGER,
    quantity                      NUMERIC,
    days_supply                   INTEGER,
    sig                           TEXT,
    route_concept_id              INTEGER,
    lot_number                    VARCHAR(50),
    provider_id                   INTEGER,
    visit_occurrence_id           INTEGER,
    visit_detail_id               INTEGER,
    drug_source_value             VARCHAR(50),
    drug_source_concept_id        INTEGER,
    route_source_value            VARCHAR(50),
    dose_unit_source_value        VARCHAR(50),
    PRIMARY KEY (drug_exposure_id)
);

CREATE TABLE IF NOT EXISTS cdm.measurement (
    measurement_id                INTEGER   NOT NULL,
    person_id                     INTEGER   NOT NULL,
    measurement_concept_id        INTEGER   NOT NULL,
    measurement_date              DATE      NOT NULL,
    measurement_datetime          TIMESTAMP,
    measurement_time              VARCHAR(10),
    measurement_type_concept_id   INTEGER   NOT NULL,
    operator_concept_id           INTEGER,
    value_as_number               NUMERIC,
    value_as_concept_id           INTEGER,
    unit_concept_id               INTEGER,
    range_low                     NUMERIC,
    range_high                    NUMERIC,
    provider_id                   INTEGER,
    visit_occurrence_id           INTEGER,
    visit_detail_id               INTEGER,
    measurement_source_value      VARCHAR(50),
    measurement_source_concept_id INTEGER,
    unit_source_value             VARCHAR(50),
    unit_source_concept_id        INTEGER,
    value_source_value            VARCHAR(50),
    PRIMARY KEY (measurement_id)
);

-- Vocabulary tables

CREATE TABLE IF NOT EXISTS cdm.concept (
    concept_id       INTEGER      NOT NULL,
    concept_name     VARCHAR(255) NOT NULL,
    domain_id        VARCHAR(20)  NOT NULL,
    vocabulary_id    VARCHAR(20)  NOT NULL,
    concept_class_id VARCHAR(20)  NOT NULL,
    standard_concept VARCHAR(1),
    concept_code     VARCHAR(50)  NOT NULL,
    valid_start_date DATE         NOT NULL,
    valid_end_date   DATE         NOT NULL,
    invalid_reason   VARCHAR(1),
    PRIMARY KEY (concept_id)
);

CREATE TABLE IF NOT EXISTS cdm.concept_relationship (
    concept_id_1     INTEGER     NOT NULL,
    concept_id_2     INTEGER     NOT NULL,
    relationship_id  VARCHAR(20) NOT NULL,
    valid_start_date DATE        NOT NULL,
    valid_end_date   DATE        NOT NULL,
    invalid_reason   VARCHAR(1),
    PRIMARY KEY (concept_id_1, concept_id_2, relationship_id)
);

CREATE TABLE IF NOT EXISTS cdm.concept_ancestor (
    ancestor_concept_id      INTEGER NOT NULL,
    descendant_concept_id    INTEGER NOT NULL,
    min_levels_of_separation INTEGER NOT NULL,
    max_levels_of_separation INTEGER NOT NULL,
    PRIMARY KEY (ancestor_concept_id, descendant_concept_id)
);

-- Indexes for common query patterns

CREATE INDEX IF NOT EXISTS idx_condition_person    ON cdm.condition_occurrence (person_id);
CREATE INDEX IF NOT EXISTS idx_condition_concept   ON cdm.condition_occurrence (condition_concept_id);
CREATE INDEX IF NOT EXISTS idx_drug_person         ON cdm.drug_exposure (person_id);
CREATE INDEX IF NOT EXISTS idx_drug_concept        ON cdm.drug_exposure (drug_concept_id);
CREATE INDEX IF NOT EXISTS idx_measurement_person  ON cdm.measurement (person_id);
CREATE INDEX IF NOT EXISTS idx_concept_name        ON cdm.concept USING gin(to_tsvector('english', concept_name));
CREATE INDEX IF NOT EXISTS idx_ancestor_descendant ON cdm.concept_ancestor (descendant_concept_id);
