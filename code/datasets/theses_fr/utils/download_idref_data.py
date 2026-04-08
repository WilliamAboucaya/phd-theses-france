"""Module downloading IdRef data from people mentioned in the theses.fr data file, specifically 
for the chosen research topics."""

from pathlib import Path
from pprint import pprint
from typing import Optional
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tqdm import tqdm


def _download_single_idref(idref: str, path_to_data: str | os.PathLike[str], session: requests.Session):
    """Download a single IdRef RDF file."""
    url = f"https://www.idref.fr/{idref}.rdf"
    out_path = os.path.join(path_to_data, f"raw/idrefs/{idref}.rdf")

    try:
        response = session.get(url, stream=True, timeout=20)
        response.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=16 * 1024):
                f.write(chunk)

        return idref, None

    except requests.HTTPError:
        if response.status_code in [403, 404]:
            return idref, response.status_code
        response.raise_for_status()
    except requests.exceptions.TooManyRedirects:
        return idref, "Redirected"


def download_idref_data(path_to_data: str | os.PathLike[str], only_missing_files=False,
                        research_topics: Optional[list[str]] = None, max_workers: int = 20, verbose=False):
    """Downloads IdRef data from people mentioned in the theses.fr data file, specifically 
    for the chosen research topics.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    only_missing_files : bool, default False
        Whether the function should keep the local versions of the IdRef files already 
        downloaded (`True`) or try to re-download them (`False`)
    research_topics : list[str], optional
        Research topics to keep for the IdRef search part of the function. If `None`, keeps 
        all the research topics.
    max_workers : int, default 20
        Maximum number of worker threads for the download process. Warning: Setting the 
        value too high can lead to throttling issues.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """

    theses_df = pd.read_json(os.path.join(path_to_data, "interim/theses-soutenues-corrected.json"))

    if research_topics:
        theses_df = theses_df.loc[theses_df.discipline.isin(research_topics)]

    for field in ["directeurs_these", "membres_jury", "rapporteurs"]:
        theses_df[field] = theses_df[field].apply(lambda d: d if isinstance(d, list) else [])

    def extract_idrefs(list_of_persons):
        return [person["idref"] for person in list_of_persons]
    
    idrefs_authors = set(theses_df.auteur.apply(lambda author: author["idref"]).to_list())
    idrefs_supervisors = {idref for lst in theses_df.directeurs_these.apply(extract_idrefs) for idref in lst}
    idrefs_jury_members = {idref for lst in theses_df.membres_jury.apply(extract_idrefs) for idref in lst}
    idrefs_jury_presidents = set(theses_df.president_jury.apply(lambda president: president["idref"] if president else None).to_list())
    idrefs_jury_presidents.discard(None)
    idrefs_reporters = {idref for lst in theses_df.rapporteurs.apply(extract_idrefs) for idref in lst}

    idrefs = (idrefs_authors | idrefs_supervisors | idrefs_jury_members | idrefs_jury_presidents | idrefs_reporters)

    Path(os.path.join(path_to_data, "raw/idrefs")).mkdir(parents=True, exist_ok=True)

    false_idrefs = {}

    idrefs_to_download = (
        [idref for idref in idrefs if not os.path.exists(os.path.join(path_to_data, f"raw/idrefs/{idref}.rdf"))]
        if only_missing_files else
        list(idrefs)
    )

    session = requests.Session()
    session.headers.update({"Connection": "keep-alive"})

    if verbose:
        print("Starting the download process")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_download_single_idref, idref, path_to_data, session): idref
            for idref in idrefs_to_download
        }

        iterator = tqdm(as_completed(futures), total=len(futures), desc="IdRef downloads") if verbose else as_completed(futures)

        for fut in iterator:
            idref, error = fut.result()
            if error:
                if idref in false_idrefs:
                    false_idrefs[idref] += 1
                else:
                    false_idrefs[idref] = 1

    if verbose:
        print("Successfully downloaded!")
        print("False IdRefs:")

        pprint(sorted(((v,k) for k,v in false_idrefs.items()), key=lambda x: x[0], reverse=True))


if __name__ == "__main__":
    # Performs the download for all the research topics related to economics and management with
    # 100+ occurrences
    download_idref_data("./data", verbose=True, only_missing_files=True, max_workers=20)
