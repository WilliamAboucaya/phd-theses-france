import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests
import pandas as pd
from tqdm import tqdm


def identifier_features(path_to_data: str | os.PathLike[str], topics_suffix: str = "", verbose=False):
    """Generate an enriched version of the dataset with additional thesis identifiers from "Thèses en ligne" and SUDOC.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
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

    if os.path.exists(os.path.join(path_to_data, f"interim/identifiers-scraped.csv")):
        identifiers_df = pd.read_csv(os.path.join(path_to_data, "interim/identifiers-scraped.csv"), dtype=str)
    else:
        identifiers_df = pd.DataFrame(columns=["nnt", "tel", "ppn"], dtype=str)

    num_skipped_tel_theses = 0
    num_skipped_ppn_theses = 0

    retry_strategy = Retry(total=10, backoff_factor=30, status_forcelist=[404, 429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)

    tel_session = requests.Session()
    tel_session.headers.update({"Connection": "keep-alive"})
    tel_session.mount("https://", adapter)
    tel_session.mount("http://", adapter)

    sudoc_session = requests.Session()
    sudoc_session.headers.update({"Connection": "keep-alive"})
    sudoc_session.mount("https://", adapter)
    sudoc_session.mount("http://", adapter)

    identifiers_dict = identifiers_df.set_index("nnt").to_dict("index")

    for row in (tqdm(df.itertuples(), desc="Adding TEL and PPN identifiers", total=len(df.index)) if verbose else df.itertuples()):
        if pd.isna(row.nnt):
            continue
        if row.nnt in identifiers_dict:
            identifiers_row = identifiers_dict[row.nnt]
            if pd.isna(identifiers_row["tel"]):
                num_skipped_tel_theses += 1
            if pd.isna(identifiers_row["ppn"]):
                num_skipped_ppn_theses += 1
            continue
        # Retrieve TEL identifier from NNT
        sparql_response = tel_session.get("http://sparql.archives-ouvertes.fr/sparql",
                                          params={
                                              "query": GET_TEL_FROM_NNT_q.format(nnt=row.nnt),
                                              "format": "application/sparql-results+json"
                                          })
        sparql_response.raise_for_status()
        try:
            tel = sparql_response.json()["results"]["bindings"][0]["tel"]["value"]
        except IndexError:
            tel = ""
            num_skipped_tel_theses += 1

        sudoc_response = sudoc_session.get(f"https://www.sudoc.fr/services/nnt2ppn/{row.nnt}&format=text/json")
        sudoc_response.raise_for_status()
        try:
            results = sudoc_response.json()["sudoc"]["results"]
            if type(results) == dict:
                ppn = results["result"]["ppn"]
            elif type(results) == list:
                ppn = next(
                    (result['result']['ppn'] for result in results if result['result']['typerecord'] == 'v'),  # If we have multiple versions of the PPN for a single NNT identifier, we first try to take the one with the record type "v" as record type "m" refers to the microfiche edition of the thesis, which is derived from the original document.
                    next((result['result']['ppn'] for result in results), "")
                )
            elif results == None:
                ppn = ""
                num_skipped_ppn_theses += 1
            else:
                raise ValueError(f"Response does not follow expected data structure:\n {results}")
        except KeyError:
            num_skipped_ppn_theses += 1
        
        identifiers_df = pd.concat([identifiers_df, pd.DataFrame({"nnt": [row.nnt], "tel": [tel], "ppn": [ppn]})], ignore_index=True)
        if row.Index % 100 == 99:
            identifiers_df.to_csv(os.path.join(path_to_data, f"interim/identifiers-scraped.csv"), encoding="utf8", index=False)

    if verbose:
        print(f"Number of theses without a TEL identifier: {num_skipped_tel_theses}")
        print(f"Number of theses without a PPN identifier: {num_skipped_ppn_theses}")

    df = df.merge(right=identifiers_df, on="nnt", how="left")
    
    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"), index=False)
    identifiers_df.to_csv(os.path.join(path_to_data, f"interim/identifiers-scraped.csv"), encoding="utf8", index=False)


GET_TEL_FROM_NNT_q = """
PREFIX purl: <http://purl.org/dc/terms/>

SELECT ?tel WHERE {{
  ?thesis purl:identifier "{nnt}" .
  ?thesis purl:identifier ?tel .
  FILTER STRSTARTS(?tel, "tel-" )
}}
"""


if __name__ == "__main__":
    identifier_features("./data", topics_suffix="[full_data]", verbose=True)