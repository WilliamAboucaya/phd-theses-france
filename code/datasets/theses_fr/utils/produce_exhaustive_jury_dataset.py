"""Module adding the jury president and the reporters to the list of jury members for exhaustivity purposes."""

import json
import os

from tqdm import tqdm


def produce_exhaustive_jury_dataset(path_to_data: str | os.PathLike[str], topics_suffix: str = "", verbose=False):
    """Adds the jury president and the reporters to the list of jury members for exhaustivity purposes.

    Parameters
    ----------
    path_to_data : str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    with open(os.path.join(path_to_data, f"interim/theses-soutenues-with-idref{topics_suffix}.json"), "r", encoding="utf8") as f:
        theses_json = json.load(f)

    enriched_dataset = []

    number_added_jury_members = 0

    for these in (tqdm(theses_json, desc="Adding president and reporters to juries") if verbose else theses_json):
        if not these["membres_jury"]:
            these["membres_jury"] = []
        jury_identifiers = [jury["idref"] if jury["idref"] else f"{jury.get('prenom', '')} {jury.get('nom', '')}" for jury in these["membres_jury"]]

        if these["president_jury"]:
            pres = these["president_jury"]
            pres_identifier = pres["idref"] if pres["idref"] else f"{pres.get('prenom', '')} {pres.get('nom', '')}"

            if pres_identifier not in jury_identifiers:
                these["membres_jury"].append(pres)
                jury_identifiers.append(pres["idref"])
                number_added_jury_members += 1

        if these["rapporteurs"]:
            for rep in these["rapporteurs"]:
                rep_identifier = rep["idref"] if rep["idref"] else f"{rep.get('prenom', '')} {rep.get('nom', '')}"

                if rep_identifier not in jury_identifiers:
                    these["membres_jury"].append(rep)
                    jury_identifiers.append(rep["idref"])
                    number_added_jury_members += 1

        enriched_dataset.append(these)

    with open(os.path.join(path_to_data, f"interim/theses-soutenues-exhaustive-jury{topics_suffix}.json"), "w", encoding="utf8") as f:
        json.dump(enriched_dataset, f, ensure_ascii=False)

    if verbose:
        print(f"Successfuly generated dataset with all jury members! {number_added_jury_members} jury members added.")


if __name__ == "__main__":
    produce_exhaustive_jury_dataset("./data", verbose=True)