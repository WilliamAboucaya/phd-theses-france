"""Module that downloads the `theses.fr` dataset and corrects potential false IdRefs."""

import gzip
import os
import shutil

import requests
from tqdm import tqdm


def download_lexvo_data(path_to_data: str | os.PathLike[str], verbose=False, only_if_missing=False):
    """Downloads the theses data as a JSON file

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    only_if_missing : bool, default False
        Whether the function should keep the local version of the Theses.fr dataset if it exists (`True`)
        or try to re-download it (`False`)
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    lexvo_url = "http://lexvo.org/resources/lexvo_latest.rdf.gz"
    lexvo_archive = "lexvo.rdf.gz"
    lexvo_filename = "lexvo.rdf"

    if not (only_if_missing and os.path.exists(os.path.join(path_to_data, "raw/", lexvo_filename))):

        response = requests.get(lexvo_url, stream=True, timeout=None)
        file_size = int(response.headers.get('Content-Length', 0))

        response.raise_for_status()
        with open(os.path.join(path_to_data, "raw/", lexvo_archive), "wb") as f:
            if verbose:
                with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024, desc="Downloading the Lexvo data file") as pbar:
                    for chunk in response.iter_content(chunk_size=16 * 1024):
                        f.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=16 * 1024):
                    f.write(chunk)

        # After downloading the Lexvo archive, un-zip it and delete the archive
        with gzip.open(os.path.join(path_to_data, "raw/", lexvo_archive), 'rb') as f_in:
            with open(os.path.join(path_to_data, "raw/", lexvo_filename), 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(os.path.join(path_to_data, "raw/", lexvo_archive))

        if verbose:
            print("Successfully downloaded!")
    elif verbose:
        print("Lexvo graph already downloaded, skipping...")


if __name__ == "__main__":
    download_lexvo_data("./data", verbose=True)
