"""Module that downloads the `theses.fr` dataset and corrects potential false IdRefs."""

import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import pandas as pd


def download_theses_fr_data(path_to_data: str | os.PathLike[str], verbose=False, only_if_missing=False,
                            idrefs_correction_table: Optional[str | os.PathLike[str]] = None):
    """Downloads the theses data as a JSON file

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    only_if_missing : bool, default False
        Whether the function should keep the local version of the Theses.fr dataset if it exists (`True`)
        or try to re-download it (`False`)
    idrefs_correction_table : str | os.PathLike[str], optional
        If set, path of the table from which the function should correct false IdRefs. The table 
        should be a 2-columns csv file with the following header:
        ```
        idref_wrong,idref_corrected
        ```
        Each following line should then be composed of a false IdRef and the correct one the 
        function should replace it with.

        If not set, no IdRef correction is performed.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    theses_url = "https://www.data.gouv.fr/fr/datasets/r/d4f0a317-4fd7-4850-bfa2-829a2a4a21df"
    theses_filename = "theses-soutenues.json"

    if not (only_if_missing and os.path.exists(os.path.join(path_to_data, "raw/", theses_filename))):

        response = requests.get(theses_url, stream=True, timeout=None)
        file_size = int(response.headers.get('Content-Length', 0))

        response.raise_for_status()
        with open(os.path.join(path_to_data, "raw/", theses_filename), "wb") as f:
            if verbose:
                with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024, desc="Downloading the theses data file") as pbar:
                    for chunk in response.iter_content(chunk_size=16 * 1024):
                        f.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=16 * 1024):
                    f.write(chunk)

        if verbose:
            print("Successfully downloaded!")
    elif verbose:
        print("Theses.fr dataset already downloaded, skipping...")

    add_newest_theses(path_to_data, verbose=verbose)

    if idrefs_correction_table:
        correct_idrefs(path_to_data, idrefs_correction_table, verbose=verbose)


def add_newest_theses(path_to_data: str | os.PathLike[str], verbose=False):
    """Adds new theses to the dataset using Theses.fr API.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    with open(os.path.join(path_to_data, "raw/theses-soutenues.json"), "r", encoding="utf8") as f:
        theses_json = json.load(f)

    for i in range(len(theses_json)):
        theses_json[i]["from_api"] = False
    
    url_new_theses = r"https://theses.fr/api/v1/theses/recherche/?q=dateSoutenance:([2022\-01\-01 TO 2025\-12\-31]) AND status:(soutenue)&nombre=100000&tri=dateAsc"

    response = requests.get(url_new_theses)
    response.raise_for_status()

    added_theses = response.json()["theses"]
    
    already_present_nnts = {thesis.get("nnt", "") for thesis in theses_json}
    added_theses_filtered = [thesis for thesis in added_theses if thesis.get("nnt") not in already_present_nnts]

    url_accessibility = r"https://theses.fr/api/v1/theses/recherche/?q=accessible:oui AND dateSoutenance ([2022\-01\-01 TO 2025\-12\-31])&nombre=100000&tri=dateAsc"

    response = requests.get(url_accessibility)
    response.raise_for_status()

    accessible_theses = response.json()["theses"]

    thesis_accessibility = [thesis['nnt'] for thesis in accessible_theses]

    retry_strategy = Retry(total=10, backoff_factor=30, status_forcelist=[404, 429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.headers.update({"Connection": "keep-alive"})
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    theses_harmonized = []

    for thesis in tqdm(added_theses_filtered, desc="Harmonizing new theses with Theses.fr data format") if verbose else added_theses_filtered:
        response_exhaustive = session.get(f"https://theses.fr/api/v1/theses/these/{thesis['nnt']}")
        try:
            response_exhaustive.raise_for_status()
            thesis_exhaustive = response_exhaustive.json()
        except requests.HTTPError:
            thesis_exhaustive = {}

        topics_reshaped = defaultdict(list)
        for sujet in thesis["sujets"]:
            topics_reshaped[sujet['langue']].append(sujet['libelle'])
        topics_reshaped = dict(topics_reshaped)
        
        thesis_harmonized = {
            "accessible": "oui" if thesis["nnt"] in thesis_accessibility else "non",
            "auteur": {
                "idref": thesis["auteurs"][0]["ppn"],
                "nom": thesis["auteurs"][0]["nom"],
                "prenom": thesis["auteurs"][0]["prenom"]
            },
            'cas': thesis_exhaustive.get("cas", None),
            'code_etab': thesis_exhaustive.get("codeEtab", None),
            "date_soutenance": datetime.strptime(thesis["dateSoutenance"], "%d/%m/%Y").strftime("%Y-%m-%d"),
            "directeurs_these": [{
                "idref": direc["ppn"],
                "nom": direc["nom"],
                "prenom": direc["prenom"]
            } for direc in thesis["directeurs"]],
            "discipline": thesis["discipline"],
            "ecoles_doctorales": [{
                "idref": doc_school["ppn"],
                "nom": doc_school["nom"],
            } for doc_school in thesis["ecolesDoctorale"]],
            'embargo': None,  # Not available using newest API
            "etablissements_soutenance": [{
                "idref": thesis["etabSoutenancePpn"],
                "nom": thesis["etabSoutenanceN"],
            }],
            'langues': thesis_exhaustive.get("langues", None),
            "membres_jury": [{
                "idref": jury["ppn"],
                "nom": jury["nom"],
                "prenom": jury["prenom"]
            } for jury in thesis["examinateurs"]],
            "nnt": thesis["nnt"],
            "oai_set_specs": [],  # Not available using newest API
            "partenaires_recherche": [{
                "idref": partner["ppn"],
                "nom": partner["nom"],
                "type": partner["type"]
            } for partner in thesis["partenairesDeRecherche"]],
            "president_jury": {
                "idref": thesis["president"]["ppn"],
                "nom": thesis["president"]["nom"],
                "prenom": thesis["president"]["prenom"]
            },
            "rapporteurs": [{
                "idref": rapp["ppn"],
                "nom": rapp["nom"],
                "prenom": rapp["prenom"]
            } for rapp in thesis["rapporteurs"]],
            "resumes": thesis_exhaustive.get("resumes", None),
            'source': thesis_exhaustive.get("source", None),
            'status': 'soutenue',
            'sujets': topics_reshaped,
            'sujets_rameau': [rameau["libelle"] for rameau in thesis["sujetsRameau"]],
            'these_sur_travaux': None,  # Not available using newest API
            'titres': thesis_exhaustive.get("titres", None),
            'from_api': True
        }

        theses_harmonized.append(thesis_harmonized)

    theses_with_newer = theses_json + theses_harmonized

    with open(os.path.join(path_to_data, "interim/theses-soutenues-with-newer.json"), "w", encoding="utf8") as f:
        json.dump(theses_with_newer, f, ensure_ascii=False, indent=2)


def correct_idrefs(path_to_data: str | os.PathLike[str],
                   idrefs_correction_table: str | os.PathLike[str], verbose=False):
    """Corrects the false IdRefs based on the manual correction table.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    correct_false_idrefs : str | os.PathLike[str]
        Path of the table from which the function should correct false IdRefs. The 
        table should be a 2-columns csv file with the following header:
        ```
        idref_wrong,idref_corrected
        ```
        Each following line should then be composed of a false IdRef and the correct 
        one the function should replace it with.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    correction_df = pd.read_csv(idrefs_correction_table,
                                dtype={"idref_wrong": str, "idref_corrected": str})

    with open(os.path.join(path_to_data, "interim/theses-soutenues-with-newer.json"), "r", encoding="utf8") as f:
        theses_json = json.load(f)

    for these in (tqdm(theses_json, desc="Correcting false IdRefs") if verbose else theses_json):
        if these["auteur"]["idref"] in correction_df.idref_wrong.values:
            these["auteur"]["idref"] = correction_df.loc[
                correction_df.idref_wrong == these["auteur"]["idref"]
                ].iloc[0].idref_corrected

        if these["directeurs_these"]:
            for direc in these["directeurs_these"]:
                if direc["idref"] in correction_df.idref_wrong.values:
                    direc["idref"] = correction_df.loc[
                        correction_df.idref_wrong == direc["idref"]
                        ].iloc[0].idref_corrected

        if these["membres_jury"]:
            for jury in these["membres_jury"]:
                if jury["idref"] in correction_df.idref_wrong.values:
                    jury["idref"] = correction_df.loc[
                        correction_df.idref_wrong == jury["idref"]
                        ].iloc[0].idref_corrected

        if these["president_jury"] and (these["president_jury"]["idref"] in correction_df.idref_wrong.values):
            these["president_jury"]["idref"] = correction_df.loc[
                correction_df.idref_wrong == these["president_jury"]["idref"]
                ].iloc[0].idref_corrected

        if these["rapporteurs"]:
            for rep in these["rapporteurs"]:
                if rep["idref"] in correction_df.idref_wrong.values:
                    rep["idref"] = correction_df.loc[
                        correction_df.idref_wrong == rep["idref"]
                        ].iloc[0].idref_corrected

    with open(os.path.join(path_to_data, "interim/theses-soutenues-corrected.json"), "w", encoding="utf8") as f:
        json.dump(theses_json, f, ensure_ascii=False)

    if verbose:
        print("Successfully corrected!")


if __name__ == "__main__":
    download_theses_fr_data("./data", verbose=True, only_if_missing=True,
        idrefs_correction_table="./data/processed/keep/idref_corrected_table.csv")
