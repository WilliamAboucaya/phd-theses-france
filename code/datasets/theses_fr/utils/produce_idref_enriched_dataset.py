"""Module generating an enriched version of the dataset as a JSON file with the same hierarchy as 
the initial one but with new features gathered from IdRef resources."""

import json
import os
from typing import Optional

from tqdm import tqdm
import pandas as pd


def _enrich_person_from_idref(person: dict, idref_data: dict, verbose: bool = False) -> None:
    """Enrich a single person object with IdRef data in-place.
    
    Parameters
    ----------
    person : dict
        Person object to enrich (author, director, jury member, etc.)
    idref_data : dict
        Dictionary mapping idref IDs to their data rows
    verbose : bool, default False
        Whether to print when data is not found
    """
    idref_id = person["idref"]
    if idref_id not in idref_data:
        if verbose and idref_id:
            print(f"No data for IdRef {idref_id}, skipping...")
        return
    
    data = idref_data[idref_id]
    person["gender"] = data["gender"]
    person["birthdate"] = data["birthdate"]
    person["deathdate"] = data["deathdate"]
    person["languages"] = data["languages"]
    person["country"] = data["country"]
    
    if data["givenname"] and data["familyname"]:
        person["prenom"] = data["givenname"]
        person["nom"] = data["familyname"]


def produce_idref_enriched_dataset(path_to_data: str | os.PathLike[str], topics_suffix: str = "", 
                                   research_topics: Optional[list[str]] = None, verbose=False):
    """Generate an enriched version of the dataset as a JSON file with the same hierarchy as the 
    initial one but with new features gathered from IdRef resources.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    research_topics : list[str], optional
        Research topics to keep. If `None`, keeps all the research topics.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    idref_df = pd.read_csv(os.path.join(path_to_data, f"interim/idref_datatable{topics_suffix}.csv"), dtype=str)

    idref_data = idref_df.set_index("idref").to_dict("index")

    with open(os.path.join(path_to_data, "interim/theses-soutenues-corrected.json"), "r", encoding="utf8") as f:
        theses_json = json.load(f)

    enriched_dataset = []

    for these in (tqdm(theses_json, desc="Enriching dataset from IdRefs") if verbose else theses_json):
        if research_topics and (these["discipline"] not in research_topics):
            continue
        
        # Enrich author
        _enrich_person_from_idref(these["auteur"], idref_data, verbose)
        
        # Enrich directors
        if these["directeurs_these"]:
            for direc in these["directeurs_these"]:
                _enrich_person_from_idref(direc, idref_data, verbose)
        
        # Enrich jury members
        if these["membres_jury"]:
            for jury in these["membres_jury"]:
                _enrich_person_from_idref(jury, idref_data, verbose)
        
        # Enrich jury president
        if these["president_jury"]:
            _enrich_person_from_idref(these["president_jury"], idref_data, verbose)
        
        # Enrich rapporteurs
        if these["rapporteurs"]:
            for rep in these["rapporteurs"]:
                _enrich_person_from_idref(rep, idref_data, verbose)

        enriched_dataset.append(these)

    with open(os.path.join(path_to_data, f"interim/theses-soutenues-with-idref{topics_suffix}.json"), "w", encoding="utf8") as f:
        json.dump(enriched_dataset, f, ensure_ascii=False)

    if verbose:
        print("Successfully generated enriched dataset!")


if __name__ == "__main__":
    produce_idref_enriched_dataset("./data", verbose=True,
                                   research_topics=["Sciences économiques", "Sciences de gestion", "Sciences de Gestion", "Gestion", "Économie", "Analyse et politique économiques", "Sciences economiques", "Economie"])
