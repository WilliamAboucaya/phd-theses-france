import os
from typing import Optional
import re
from warnings import simplefilter

import numpy as np
import pandas as pd
import nomquamgender as nqm
from tqdm.auto import tqdm


simplefilter(action="ignore", category=pd.errors.DtypeWarning)


def improve_gender_completion(path_to_data: str | os.PathLike[str], topics_suffix: str = "", 
                              gender_correction_table: Optional[str | os.PathLike[str]] = None, verbose=False):
    """Add gender data for persons whose gender is unknown by IdRef. First round uses
    first name-based inference and second round uses hand-made annotations for persons
    whose name is ambiguous.

    Parameters
    ----------
    path_to_data : str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    gender_correction_table : str | os.PathLike[str], optional
        Path to the table with gender manually set for persons with ambiguous names. 
        The path is relative to the `path_to_data` argument.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """
    
    file_path = os.path.join(path_to_data, f"interim/theses-soutenues-flattened{topics_suffix}.parquet")
    theses_df = pd.read_parquet(file_path)

    detector = nqm.NBGC(threshold=0.2)

    # STEP 1 – Define relevant role prefixes
    prefixes = ['auteur', 'directeur.0', 'directeur.1', 'directeur.2', 'directeur.3', 'directeur.4', 'directeur.5', 'directeur.6',
                'membre_jury.0', 'membre_jury.1', 'membre_jury.2', 'membre_jury.3', 'membre_jury.4', 'membre_jury.5', 
                'membre_jury.6', 'membre_jury.7', 'membre_jury.8', 'membre_jury.9', 'membre_jury.10', 'membre_jury.11', 
                'president_jury', 'rapporteur.0', 'rapporteur.1', 'rapporteur.2', 'rapporteur.3', "rapporteur.4", "rapporteur.5"]

    # STEP 2 – Collect name records with missing gender
    name_records = []
    midname_initial_regex = re.compile(r"[a-z]\.$")
    for prefix in prefixes:
        prenom_col = f"{prefix}.prenom"
        nom_col = f"{prefix}.nom"
        gender_col = f"{prefix}.gender"
        idref_col = f"{prefix}.idref"

        if prenom_col in theses_df.columns and nom_col in theses_df.columns and gender_col in theses_df.columns:
            missing = theses_df[theses_df[gender_col].isna()]
            for idx, row in missing.iterrows():
                prenom = row.get(prenom_col)
                nom = row.get(nom_col)
                identifier = row.get(idref_col) if (pd.notna(row.get(idref_col)) and row.get(idref_col)) else f"{prenom}_{nom}"
                if pd.notnull(prenom):
                    name_records.append({
                        'row_idx': idx,
                        'prefix': prefix,
                        'identifier': identifier,
                        'prenom': prenom,
                        'nom': nom,
                        'normalized_prenom': midname_initial_regex.sub("", str(prenom).lower().strip().removeprefix("el ")),
                    })

    name_df = pd.DataFrame(name_records)

    if verbose:
        print(f"Number of persons with missing gender: {len(name_df.index)}")

    # STEP 3 – Apply nonquamgender to first names
    name_df['gender_guess'] = detector.classify(name_df['normalized_prenom'])
    name_df['gender_guess'] = name_df['gender_guess'].replace({'gm': 'male', 'gf': 'female', '-': np.nan})

    if verbose:
        print(f"Number of persons with missing gender after gender guessing: {name_df.gender_guess.isna().sum()}")

    name_df['final_gender'] = name_df['gender_guess']

    if gender_correction_table:
        # STEP 4 – Apply manual corrections
        manual_gender_df = pd.read_csv(os.path.join(path_to_data, gender_correction_table), encoding='utf-8')

        # Merge manual genders into name_df
        name_df = name_df.merge(
            manual_gender_df,
            on=['prenom', 'nom', 'identifier'],
            how='left'
        )

        # STEP 5 – Fill in gender from manual file
        mask_manual = name_df['final_gender'].isna() & name_df['gender_manual'].notna()
        name_df.loc[mask_manual, 'final_gender'] = name_df.loc[mask_manual, 'gender_manual']

    # STEP 6 – Update gender in original df using final_gender
    for row in tqdm(name_df.itertuples(), desc="Applying results to dataset", total=len(name_df.index)) if verbose else name_df.itertuples():
        if pd.notna(row.final_gender):
            idx = row.row_idx
            prefix = row.prefix
            gender_col = f"{prefix}.gender"
            theses_df.at[idx, gender_col] = row.final_gender

    if verbose:
        num_unknown_genders = len(name_df.loc[name_df.final_gender.isna()].index)
        print(f"Final number of people with unknown gender: {num_unknown_genders}")

    theses_df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-gender-guessed{topics_suffix}.parquet"), index=False)

    if gender_correction_table:
        # STEP 7 - Add potential new ungendered names to the gender correction table
        ungendered_df = name_df.loc[name_df['final_gender'].isna()][['prenom', 'nom', 'identifier']]
        new_ungendered_df = ungendered_df.merge(
                                manual_gender_df[['prenom', 'nom', 'identifier']],
                                on=['prenom', 'nom', 'identifier'],
                                how='left',
                                indicator=True
                            ).query('_merge == "left_only"').drop(columns='_merge').drop_duplicates()
        
        if len(new_ungendered_df.index):
            if verbose:
                print(f"Adding {len(new_ungendered_df.index)} new entries to the list of ungendered persons")
            manual_gender_df = pd.concat([manual_gender_df, new_ungendered_df], ignore_index=True)
            manual_gender_df.to_csv(os.path.join(path_to_data, gender_correction_table), encoding='utf-8', index=False)


if __name__ == "__main__":
    improve_gender_completion("./data", gender_correction_table="processed/keep/gender/gender_corrected.csv", topics_suffix="[full_data]", verbose=True)
