"""Module running the full download and data preparation process for the theses_fr dataset"""

import os
import argparse
from typing import Optional

import pandas as pd

from utils import download_theses_fr_data, download_lexvo_data, download_idref_data, \
                  produce_idref_datatable, produce_idref_enriched_dataset, \
                  produce_exhaustive_jury_dataset, flatten_dataset, improve_gender_completion


def generate_theses_fr(path_to_data, research_topics: Optional[list[str]] = None, verbose=False,
                       idrefs_correction_table: Optional[str | os.PathLike[str]] = None,
                       gender_correction_table: Optional[str | os.PathLike[str]] = None,
                       only_missing_files=False, max_workers: int = 20, topics_suffix: str = ""):
    """Runs the full download and data preparation process for the theses_fr dataset

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    idrefs_correction_table : str | os.PathLike[str], optional
        If set, path of the table from which the function should correct false IdRefs. The table 
        should be a 2-columns csv file with the following header:
        ```
        idref_wrong,idref_corrected
        ```
        Each following line should then be composed of a false IdRef and the correct one the 
        function should replace it with.

        If not set, no IdRef correction is performed.
    gender_correction_table : str | os.PathLike[str], optional
        Path to the table with gender manually set for persons with ambiguous names.
    research_topics : list[str], optional
        Research topics to keep for the IdRef search part of the function. If `None`, keeps 
        all the research topics.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    only_missing_files : bool, default False
        Whether the function should keep the local versions of the IdRef files already 
        downloaded (`True`) or try to re-download them (`False`)
    max_workers : int, default 20
        Maximum number of worker threads for the IdRef download process. Warning: Setting the 
        value too high can lead to throttling issues.
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    """
    download_theses_fr_data(path_to_data, idrefs_correction_table=idrefs_correction_table, 
                            only_if_missing=only_missing_files, verbose=verbose)
    download_lexvo_data(path_to_data, only_if_missing=only_missing_files, verbose=verbose)
    download_idref_data(path_to_data, research_topics=research_topics, verbose=verbose,
                        only_missing_files=only_missing_files, max_workers=max_workers)
    produce_idref_datatable(path_to_data, research_topics=research_topics, topics_suffix=topics_suffix, verbose=verbose)
    produce_idref_enriched_dataset(path_to_data, research_topics=research_topics, topics_suffix=topics_suffix, verbose=verbose)
    produce_exhaustive_jury_dataset(path_to_data, topics_suffix=topics_suffix, verbose=verbose)
    flatten_dataset(path_to_data, topics_suffix=topics_suffix, verbose=verbose)
    improve_gender_completion(path_to_data, gender_correction_table=gender_correction_table, 
                              topics_suffix=topics_suffix, verbose=verbose)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path_to_data", type=str, default="./data/",
                        help="Path to the folder containing the data (using DSLP architecture)")
    parser.add_argument("--topics", nargs="+", default=[],
                        help="Names of the thesis topics to filter in. "
                        "Must correspond to a file name in the data/processed/keep/topics folder.")
    parser.add_argument("--max_workers", type=int, default=20,
                        help="Maximum number of worker threads for the IdRef download process. "
                        "Warning: Setting the value too high can lead to throttling issues.")
    args = parser.parse_args()

    path_to_data_: str = args.path_to_data
    topics: list[str] = args.topics
    max_workers: int = args.max_workers

    topics_suffix = f"[{','.join(topics) if topics else 'full_data'}]"

    if topics:
        topic_names_to_keep = set()
        for topic in topics:
            topic_df = pd.read_csv(os.path.join(path_to_data_, f"processed/keep/topics/{topic}.csv"))
            topic_names = topic_df.loc[topic_df["take"] == 1].discipline.to_list()
            topic_names_to_keep.update(topic_names)

        topic_names_to_keep = list(topic_names_to_keep)
    else:
        topic_names_to_keep = None

    generate_theses_fr(path_to_data_, research_topics=topic_names_to_keep, only_missing_files=True, verbose=True, 
                       idrefs_correction_table=os.path.join(path_to_data_, "processed/keep/idref_corrected_table.csv"),
                       gender_correction_table="processed/keep/gender/gender_corrected.csv", max_workers=max_workers,
                       topics_suffix=topics_suffix)
