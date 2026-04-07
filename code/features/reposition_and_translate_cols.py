import os
import re

import pandas as pd


def reposition_and_translate_cols(path_to_data: str | os.PathLike[str], topics_suffix: str = "", verbose=False):
    """Positions the columns in a more semantically coherent order, .

    Parameters
    ----------
    path_to_data : str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    if os.path.exists(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet")):
        file_name = f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"
    else:
        file_name = f"processed/theses-soutenues-gender-guessed{topics_suffix}.parquet"

    file_path = os.path.join(path_to_data, file_name)
    df = pd.read_parquet(file_path)
    
    if verbose:
        print(f"Nb of theses: {len(df.index)}")

    df = _reposition_cols(df, verbose=verbose)
    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"), index=False)

    df = _translate_cols(df, verbose=verbose)
    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced_english{topics_suffix}.parquet"), index=False)


def _reposition_cols(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    if verbose:
        print("Columns reordering...")

    cols = df.columns.tolist()

    metric_fields = {
        "centrality",
        "age",
        "yrs_since_phd",
        "yrs_since_first_jury",
        "exists"
    }

    pattern_indexed = re.compile(r'^(?P<role>[^.]+)\.(?P<idx>\d+)\.(?P<field>.+)$')
    pattern_simple = re.compile(r'^(?P<role>[^.]+)\.(?P<field>.+)$')

    # Identify metric columns
    metric_cols = []
    base_cols = []

    for col in cols:
        m = pattern_indexed.match(col)
        if m and m.group("field") in metric_fields:
            metric_cols.append(col)
            continue

        m = pattern_simple.match(col)
        if m and m.group("field") in metric_fields:
            metric_cols.append(col)
            continue

        base_cols.append(col)

    # Insert metrics after their group
    new_cols = base_cols.copy()

    for metric in metric_cols:
        m = pattern_indexed.match(metric)
        if m:
            role = m.group("role")
            idx = m.group("idx")
            prefix = f"{role}.{idx}."
            # find last column of that group
            positions = [i for i, c in enumerate(new_cols) if c.startswith(prefix)]
            if positions:
                insert_pos = max(positions) + 1
            else:
                insert_pos = len(new_cols)

        else:
            m = pattern_simple.match(metric)
            role = m.group("role")
            prefix = f"{role}."
            positions = [i for i, c in enumerate(new_cols) if c.startswith(prefix)]
            if positions:
                insert_pos = max(positions) + 1
            else:
                insert_pos = len(new_cols)

        new_cols.insert(insert_pos, metric)

    df = df[new_cols]

    return df


def _translate_cols(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    if verbose:
        print("Columns translation...")
    
    base_translations = {
        "date_soutenance": "defense_date",
        "these_sur_travaux": "phd_by_publication",
        "sujets_rameau": "rameau_topics",
        "num_directeurs": "num_supervisors",
        "num_membres_jury": "num_jury_members",
        "num_partenaires_recherche": "num_research_partners"
    }

    prefixes_monoperson_fr = ["auteur", "president_jury"]
    prefixes_monoperson_en = ["author", "jury_president"]

    prefixes_multipersons_fr = ["directeur",  "membre_jury"]
    prefixes_multipersons_en = ["supervisor", "jury_member"]

    suffixes_persons_fr = ["idref", "prenom",    "nom",      "gender", "birthdate", "deathdate", "languages", "country", "centrality", "age", "yrs_since_phd", "yrs_since_first_jury"]
    suffixes_persons_en = ["idref", "firstname", "lastname", "gender", "birthdate", "deathdate", "languages", "country", "centrality", "age", "yrs_since_phd", "yrs_since_first_jury"]

    monoperson_translations = {
        f"{prefix_fr}.{suffix_fr}": f"{prefix_en}.{suffix_en}"
        for prefix_fr, prefix_en in zip(prefixes_monoperson_fr, prefixes_monoperson_en)
        for suffix_fr, suffix_en in zip(suffixes_persons_fr, suffixes_persons_en)
    }
    multipersons_translations = {
        f"{prefix_fr}.{i}.{suffix_fr}": f"{prefix_en}.{i}.{suffix_en}"
        for prefix_fr, prefix_en in zip(prefixes_multipersons_fr, prefixes_multipersons_en)
        for suffix_fr, suffix_en in zip(suffixes_persons_fr, suffixes_persons_en)
        for i in range(12)
    }

    prefixes_multientity_fr = ["ecole_doctorale", "partenaire_recherche", "etablissement_soutenance"]
    prefixes_multientity_en = ["doctoral_school", "research_partner",     "defense_institution"]
    suffixes_multientity_fr = ["idref", "nom",  "type"]
    suffixes_multientity_en = ["idref", "name", "type"]
    multientity_translations = {
        f"{prefix_fr}.{i}.{suffix_fr}": f"{prefix_en}.{i}.{suffix_en}"
        for prefix_fr, prefix_en in zip(prefixes_multientity_fr, prefixes_multientity_en)
        for suffix_fr, suffix_en in zip(suffixes_multientity_fr, suffixes_multientity_en)
        for i in range(10)
    }

    langs_fr = [f"langue.{i}" for i in range(4)]
    langs_en = [f"language.{i}" for i in range(4)]
    langs_translations = {
        lang_fr: lang_en for lang_fr, lang_en in zip(langs_fr, langs_en)
    }

    prefixes_docinfo_fr = ["sujets", "resume",   "titre"]
    prefixes_docinfo_en = ["topics", "abstract", "title"]
    suffixes_docinfo_fr = ["", ".langue"]
    suffixes_docinfo_en = ["", ".language"]
    docinfo_translations = {
        f"{prefix_fr}.{i}{suffix_fr}": f"{prefix_en}.{i}{suffix_en}"
        for prefix_fr, prefix_en in zip(prefixes_docinfo_fr, prefixes_docinfo_en)
        for suffix_fr, suffix_en in zip(suffixes_docinfo_fr, suffixes_docinfo_en)
        for i in range(10)
    }
    
    translations = base_translations | monoperson_translations | multipersons_translations | multientity_translations | langs_translations | docinfo_translations

    df.rename(translations, axis="columns", inplace=True)

    return df


if __name__ == "__main__":
    reposition_and_translate_cols("./data/", topics_suffix="[full_data]", verbose=True)