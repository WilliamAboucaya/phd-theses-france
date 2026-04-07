"""Module transforming the JSON dataset into a flat CSV table."""

from collections import defaultdict
import os
from warnings import simplefilter

import pandas as pd
from tqdm import tqdm

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


def flatten_dataset(path_to_data: str | os.PathLike[str], topics_suffix: str = "", verbose=False):
    """Transforms the JSON dataset into a flat CSV table.

    Parameters
    ----------
    path_to_data : str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    theses_df = pd.read_json(os.path.join(path_to_data, f"interim/theses-soutenues-exhaustive-jury{topics_suffix}.json"))

    max_cols_dict = {
        "direc": theses_df.loc[theses_df.directeurs_these.notna()].directeurs_these.apply(len).max().item(),
        "jury": theses_df.loc[theses_df.membres_jury.notna()].membres_jury.apply(len).max().item(),
        "rep": theses_df.loc[theses_df.rapporteurs.notna()].rapporteurs.apply(len).max().item(),
        "ed": theses_df.loc[theses_df.ecoles_doctorales.notna()].ecoles_doctorales.apply(len).max().item(),
        "partner": theses_df.loc[theses_df.partenaires_recherche.notna()].partenaires_recherche.apply(len).max().item(),
        "topic": theses_df.loc[theses_df.sujets.notna()].sujets.apply(len).max().item(),
        "defplace": theses_df.loc[theses_df.etablissements_soutenance.notna()].etablissements_soutenance.apply(len).max().item(),
        "lang": theses_df.loc[theses_df.langues.notna()].langues.apply(len).max().item(),
        "oai": theses_df.loc[theses_df.oai_set_specs.notna()].oai_set_specs.apply(len).max().item(),
        "summary": theses_df.loc[theses_df.resumes.notna()].resumes.apply(len).max().item(),
        "title": theses_df.loc[theses_df.titres.notna()].titres.apply(len).max().item()
    }

    columns_to_add = ["auteur.idref", "auteur.nom", "auteur.prenom", "auteur.gender", "auteur.birthdate", "auteur.deathdate", "auteur.languages", "auteur.country",
                      *sum([[f"directeur.{i}.idref", f"directeur.{i}.nom", f"directeur.{i}.prenom", f"directeur.{i}.gender", f"directeur.{i}.birthdate", f"directeur.{i}.deathdate", f"directeur.{i}.languages", f"directeur.{i}.country"] for i in range(max_cols_dict["direc"])], []),
                      *sum([[f"membre_jury.{i}.idref", f"membre_jury.{i}.nom", f"membre_jury.{i}.prenom", f"membre_jury.{i}.gender", f"membre_jury.{i}.birthdate", f"membre_jury.{i}.deathdate", f"membre_jury.{i}.languages", f"membre_jury.{i}.country"] for i in range(max_cols_dict["jury"])], []),
                      "president_jury.idref", "president_jury.nom", "president_jury.prenom", "president_jury.gender", "president_jury.birthdate", "president_jury.deathdate", "president_jury.languages", "president_jury.country",
                      *sum([[f"rapporteur.{i}.idref", f"rapporteur.{i}.nom", f"rapporteur.{i}.prenom", f"rapporteur.{i}.gender", f"rapporteur.{i}.birthdate", f"rapporteur.{i}.deathdate", f"rapporteur.{i}.languages", f"rapporteur.{i}.country"] for i in range(max_cols_dict["rep"])], []),
                      *sum([[f"ecole_doctorale.{i}.idref", f"ecole_doctorale.{i}.nom"] for i in range(max_cols_dict["ed"])], []),
                      *sum([[f"partenaire_recherche.{i}.idref", f"partenaire_recherche.{i}.nom", f"partenaire_recherche.{i}.type"] for i in range(max_cols_dict["partner"])], []),
                      *sum([[f"sujets.{i}.langue", f"sujets.{i}"] for i in range(max_cols_dict["topic"])], []),
                      *sum([[f"etablissement_soutenance.{i}.idref", f"etablissement_soutenance.{i}.nom"] for i in range(max_cols_dict["defplace"])], []),
                      *sum([[f"langue.{i}"] for i in range(max_cols_dict["lang"])], []), *sum([[f"oai.{i}"] for i in range(max_cols_dict["oai"])], []),
                      "sujets_rameau",
                      *sum([[f"resume.{i}.langue", f"resume.{i}"] for i in range(max_cols_dict["summary"])], []),
                      *sum([[f"titre.{i}.langue", f"titre.{i}"] for i in range(max_cols_dict["title"])], [])]

    if verbose:
        tqdm.pandas(desc="Flattening the dataset into a CSV table")
        theses_df[columns_to_add] = theses_df.progress_apply(flatten_row, axis="columns", result_type="expand", args=[max_cols_dict])
    else:
        theses_df[columns_to_add] = theses_df.apply(flatten_row, axis="columns", result_type="expand", args=[max_cols_dict])

    theses_df.drop(["auteur", "directeurs_these", "membres_jury", "president_jury", "rapporteurs",
                    "ecoles_doctorales", "partenaires_recherche", "sujets", 
                    "etablissements_soutenance", "langues", "oai_set_specs",
                    "resumes", "titres"], axis="columns", inplace=True)
    
    # Drop all columns which have a single possible value and no NAs (they do not give any info)
    unused_cols = [col for col in theses_df.columns if (theses_df[col].nunique() == 1) and (theses_df[col].notna().all())]
    theses_df.drop(unused_cols, axis="columns", inplace=True)

    date_columns = [col for col in theses_df.columns if (
        col.startswith(("directeur.", "membre_jury.", "rapporteur.", "president", "auteur")) and col.endswith((".birthdate", ".deathdate"))
    )]
    date_format = {col: "ISO8601" for col in date_columns}
    date_format["date_soutenance"] = "%Y-%m-%d"

    for col, fmt in date_format.items():
        theses_df[col] = pd.to_datetime(theses_df[col], format=fmt, errors="coerce")

    theses_df['accessible'] = theses_df['accessible'].map({"oui": True, "non": False})

    theses_df.to_parquet(os.path.join(path_to_data, f"interim/theses-soutenues-flattened{topics_suffix}.parquet"), index=False)


def flatten_row(row: pd.Series, max_cols_dict: dict[str, int]) -> list[str]:
    author = defaultdict(lambda: pd.NA, row["auteur"])
    flattened_list_author = [author["idref"], author["nom"], author["prenom"], author["gender"], 
                             author["birthdate"], author["deathdate"], author["languages"], author["country"]]

    if row["directeurs_these"]:
        flattened_list_direcs = []
        for i in range(max_cols_dict["direc"]):
            if len(row["directeurs_these"]) > i:
                direc = defaultdict(lambda: pd.NA, row["directeurs_these"][i])
                flattened_list_direcs.extend([direc["idref"], direc["nom"], direc["prenom"], direc["gender"],
                                            direc["birthdate"], direc["deathdate"], direc["languages"], direc["country"]])
            else:
                flattened_list_direcs.extend([pd.NA] * 8)
    else:
        flattened_list_direcs = [pd.NA] * 8 * max_cols_dict["direc"]
    
    if row["membres_jury"]:
        flattened_list_jury = []
        for i in range(max_cols_dict["jury"]):
            if len(row["membres_jury"]) > i:
                jury = defaultdict(lambda: pd.NA, row["membres_jury"][i])
                flattened_list_jury.extend([jury["idref"], jury["nom"], jury["prenom"], jury["gender"], 
                                            jury["birthdate"], jury["deathdate"], jury["languages"], jury["country"]])
            else:
                flattened_list_jury.extend([pd.NA] * 8)
    else:
        flattened_list_jury = [pd.NA] * 8 * max_cols_dict["jury"]

    if row["president_jury"]:
        pres = defaultdict(lambda: pd.NA, row["president_jury"])
        flattened_list_president = [pres["idref"], pres["nom"], pres["prenom"], pres["gender"], 
                                    pres["birthdate"], pres["deathdate"], pres["languages"], pres["country"]]
    else:
        flattened_list_president = [pd.NA] * 8

    if row["rapporteurs"]:
        flattened_list_reps = []
        for i in range(max_cols_dict["rep"]):
            if len(row["rapporteurs"]) > i:
                rep = defaultdict(lambda: pd.NA, row["rapporteurs"][i])
                flattened_list_reps.extend([rep["idref"], rep["nom"], rep["prenom"], rep["gender"], 
                                            rep["birthdate"], rep["deathdate"], rep["languages"], rep["country"]])
            else:
                flattened_list_reps.extend([pd.NA] * 8)
    else:
        flattened_list_reps = [pd.NA] * 8 * max_cols_dict["rep"]

    if row["ecoles_doctorales"]:
        flattened_list_ed = []
        for i in range(max_cols_dict["ed"]):
            if len(row["ecoles_doctorales"]) > i:
                ed = defaultdict(lambda: pd.NA, row["ecoles_doctorales"][i])
                flattened_list_ed.extend([ed["idref"], ed["nom"]])
            else:
                flattened_list_ed.extend([pd.NA] * 2)
    else:
        flattened_list_ed = [pd.NA] * 2 * max_cols_dict["ed"]

    if row["partenaires_recherche"]:
        flattened_list_partner = []
        for i in range(max_cols_dict["partner"]):
            if len(row["partenaires_recherche"]) > i:
                partner = defaultdict(lambda: pd.NA, row["partenaires_recherche"][i])
                flattened_list_partner.extend([partner["idref"], partner["nom"], partner["type"]])
            else:
                flattened_list_partner.extend([pd.NA] * 3)
    else:
        flattened_list_partner = [pd.NA] * 3 * max_cols_dict["partner"]

    if row["sujets"]:
        flattened_list_topic = []
        topics = list(row["sujets"].items())
        for i in range(max_cols_dict["topic"]):
            if len(topics) > i:
                topic = topics[i]
                flattened_list_topic.extend([topic[0], "||".join(topic[1])])
            else:
                flattened_list_topic.extend([pd.NA] * 2)
    else:
        flattened_list_topic = [pd.NA] * 2 * max_cols_dict["topic"]

    if row["etablissements_soutenance"]:
        flattened_list_defplace = []
        for i in range(max_cols_dict["defplace"]):
            if len(row["etablissements_soutenance"]) > i:
                defplace = defaultdict(lambda: pd.NA, row["etablissements_soutenance"][i])
                flattened_list_defplace.extend([defplace["idref"], defplace["nom"]])
            else:
                flattened_list_defplace.extend([pd.NA] * 2)
    else:
        flattened_list_defplace = [pd.NA] * 2 * max_cols_dict["defplace"]

    if row["langues"]:
        flattened_list_lang = []
        for i in range(max_cols_dict["lang"]):
            if len(row["langues"]) > i:
                lang = row["langues"][i]
                flattened_list_lang.append(lang)
            else:
                flattened_list_lang.append(pd.NA)
    else:
        flattened_list_lang = [pd.NA] * max_cols_dict["lang"]

    if row["oai_set_specs"]:
        flattened_list_oai = []
        for i in range(max_cols_dict["oai"]):
            if len(row["oai_set_specs"]) > i:
                oai = row["oai_set_specs"][i]
                flattened_list_oai.append(oai)
            else:
                flattened_list_oai.append(pd.NA)
    else:
        flattened_list_oai = [pd.NA] * max_cols_dict["oai"]

    if row["sujets_rameau"]:
        flattened_list_rameau = ["||".join(row["sujets_rameau"])]
    else:
        flattened_list_rameau = [pd.NA]

    if row["resumes"]:
        flattened_list_summary = []
        summaries = list(row["resumes"].items())
        for i in range(max_cols_dict["summary"]):
            if len(summaries) > i:
                summary = summaries[i]
                flattened_list_summary.extend([summary[0], summary[1]])
            else:
                flattened_list_summary.extend([pd.NA] * 2)
    else:
        flattened_list_summary = [pd.NA] * 2 * max_cols_dict["summary"]

    if row["titres"]:
        flattened_list_title = []
        titles = list(row["titres"].items())
        for i in range(max_cols_dict["title"]):
            if len(titles) > i:
                title = titles[i]
                flattened_list_title.extend([title[0], title[1]])
            else:
                flattened_list_title.extend([pd.NA] * 2)
    else:
        flattened_list_title = [pd.NA] * 2 * max_cols_dict["title"]

    flattened_list = flattened_list_author + flattened_list_direcs + flattened_list_jury + \
                     flattened_list_president + flattened_list_reps + flattened_list_ed + \
                     flattened_list_partner + flattened_list_topic + flattened_list_defplace + \
                     flattened_list_lang + flattened_list_oai + flattened_list_rameau + \
                     flattened_list_summary + flattened_list_title

    return flattened_list


if __name__ == "__main__":
    flatten_dataset("./data", topics_suffix="[full_data]", verbose=True)
