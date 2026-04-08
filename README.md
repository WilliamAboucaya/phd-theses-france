[![python](https://img.shields.io/badge/python-≥3.12-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)

# French Ph. D. Theses Dataset (1985–2025)

We provide the code to reproduce the dataset of French Ph. D. theses available [here]().

## Overview

This dataset provides a comprehensive, structured collection of doctoral theses defended in France between 1985 and 2025. Each record corresponds to a single defended PhD thesis and includes detailed information on the thesis itself, the individuals involved (author, supervisors, jury members), and associated institutions.

---

## Motivation

The dataset was created to support quantitative and computational analyses of doctoral training and academic networks in France. While existing platforms provide rich metadata, they are often fragmented, incomplete, or difficult to exploit at scale. This dataset addresses these limitations by:

- Aggregating multiple authoritative sources
- Correcting inconsistencies in identifiers and metadata
- Enriching records with derived and external features

---

## Setup

To install the project and its dependencies, we rely on [UV](https://docs.astral.sh/uv/getting-started/installation/). The command to run is therefore:

```bash
uv venv & uv sync
```

---

## Reproducing the datasets

The datasets can be reproduced automatically by launching the script [`code/datasets/theses_fr/theses_fr.py`](code/datasets/theses_fr/theses_fr.py). The resulting dataset will be available in the [`data/processed`](data/processed) folder.

You can also add the optional features (needed for certain analyses) using the scripts in the [`code/features`](code/features) folder.

---

## Data Sources

The dataset is derived from the following primary sources:

- **Thèses.fr**: Main source of thesis metadata (titles, abstracts, participants, institutions)
- **IdRef**: Authority database for disambiguated person and institution identifiers
- **Thèses En Ligne (TEL)**: Open-access repository for thesis manuscripts and additional metadata
- **SUDOC**: National academic library catalogue providing bibliographic records and identifiers (PPN)

---

## Temporal Coverage

- **Theses defended**: 1985–2025 (NB: Coverage for recent years may be incomplete due to reporting delays in source systems.)
- **Data collection date**: March 31, 2026

---

## Dataset Structure

- **Unit of observation**: One row per thesis
- **Main categories of variables**:
  - Thesis identifiers & status
  - Author information
  - Supervisor information
  - Jury composition
  - Institutional affiliations
  - Content & topics

The dataset includes both raw metadata and derived features.

A complete description of the features is available in the [feature codebook]()

---

## Data Enhancements

Several transformations were applied to improve data quality:

- Correction of invalid or inconsistent IdRef identifiers
- Enrichment of person records using authority data
- Gender inference based on first names (automated + manual review)
- Feature engineering for temporal and relational analysis
- Integration of external identifiers (TEL, SUDOC)

---

## Missing Data and Limitations

- Jury information is often missing for older theses due to historical data collection practices
- Doctoral school information is almost non-existent before 2006 due to institutional evolution
- Gender data is incomplete and partially inferred
- Recent years may be underrepresented due to reporting delays

Users should account for these factors, especially in longitudinal analyses.

---

## Potential Use Cases

- Analysis of academic networks (supervision, jury participation)
- Study of doctoral education and career trajectories
- Gender and diversity analyses in academia
- Institutional collaboration and structure
- Evolution of research fields and disciplines
- Natural language processing on thesis content

The dataset is designed to be interoperable and extensible:

- Persistent identifiers enable linkage with external datasets
- Compatible with bibliometric, network analysis, and NLP workflows
- Can be enriched with publication data, rankings, or full-text corpora

---

## Ethical Considerations

- Gender inference may introduce classification errors
- Data represents academic individuals and should be used responsibly

---

## Reproducibility

- Data collected from publicly available sources
- Code to reproduce the dataset is publicly available on [GitHub]()
- Data snapshot reflects the state of sources as of March 31, 2026. Future updates may improve completeness, especially for recent years.

---

## Citation

If you use this dataset, please cite the associated paper:

> Aboucaya, William and Jasim, Dastan. *Doctoral Theses in France (1985–2025): A Linked Dataset of PhDs, Academic Networks, and Institutions*, 2026.


---

## Contact

For questions, feedback, or contributions, please [send an issue to the GitHub repository]().