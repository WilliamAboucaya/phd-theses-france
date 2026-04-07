import os
import numpy as np
import pandas as pd
from collections import defaultdict

from tqdm.auto import tqdm


def centrality_features_for_participants(path_to_data: str | os.PathLike, topics_suffix: str = "", 
                                         verbose: bool = False):
    if os.path.exists(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet")):
        file_name = f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"
    else:
        file_name = f"processed/theses-soutenues-gender-guessed{topics_suffix}.parquet"

    file_path = os.path.join(path_to_data, file_name)
    df = pd.read_parquet(file_path)
    
    if verbose:
        print(f"Nb of theses: {len(df.index)}")
    
    advisors_prefixes = [f'directeur.{i}.' for i in range(6) if f"directeur.{i}.idref" in df.columns]
    jury_members_prefixes = [f'membre_jury.{i}.' for i in range(12) if f"membre_jury.{i}.idref" in df.columns]
    prefixes = advisors_prefixes + jury_members_prefixes
    for prefix in prefixes:
        # Produce an identifier variable which relies on the most distinctive feature of each person (IdRef, then full name, then surname, then first name)
        df[f"{prefix}idref_or_fullname"] = df.apply(lambda row: row[f"{prefix}idref"] if pd.notna(row[f"{prefix}idref"]) else (str(row[f"{prefix}nom"]) + "_" + str(row[f"{prefix}prenom"]) if (pd.notna(row[f"{prefix}nom"]) or pd.notna(row[f"{prefix}prenom"])) else np.nan), axis='columns')
        
        df[f"{prefix}centrality"] = pd.NA

    df['date_soutenance'] = pd.to_datetime(df['date_soutenance'], errors='coerce')  # Non-convertible values become NaT

    person_cols = [f"{p}idref_or_fullname" for p in prefixes]

    df['__orig_index__'] = df.index
    df_sorted = df.sort_values('date_soutenance', na_position='last').reset_index(drop=True)

    # Precompute per-thesis set of distinct persons (across all prefixes)
    persons_sets = []
    for _, row in df_sorted.iterrows():
        persons_set = set()
        for col in person_cols:
            identifier = row.get(col)
            if pd.notna(identifier):
                identifier = str(identifier).strip()
                if identifier and identifier.lower() not in {'nan', 'none'}:
                    persons_set.add(identifier)
        persons_sets.append(persons_set)

    dates = df_sorted['date_soutenance'].to_numpy()
    n = len(dates)

    left = 0
    last_added = 0
    person_counts = defaultdict(int)

    # Iterate in increasing date order and for each thesis compute the count from previous 4 years
    for i in (tqdm(range(n), total=n) if verbose else range(n)):
        cur_date = dates[i]
        if pd.isna(cur_date):
            for j in range(i, n):
                orig_idx_j = int(df_sorted.at[j, '__orig_index__'])
                for prefix in prefixes:
                    df.at[orig_idx_j, f"{prefix}centrality"] = 0
            break

        while last_added < i and pd.notna(dates[last_added]) and dates[last_added] < cur_date:
            for person in persons_sets[last_added]:
                person_counts[person] += 1
            last_added += 1

        cutoff = cur_date - pd.DateOffset(years=4)
        while left < i and dates[left] <= cutoff:
            for person in persons_sets[left]:
                person_counts[person] -= 1
                if person_counts[person] == 0:
                    del person_counts[person]
            left += 1

        orig_idx = int(df_sorted.at[i, '__orig_index__'])
        for prefix in prefixes:
            pid = df.at[orig_idx, f"{prefix}idref_or_fullname"]
            if pd.isna(pid):
                count = 0
            else:
                pid_s = str(pid).strip()
                count = person_counts.get(pid_s, 0)
            df.at[orig_idx, f"{prefix}centrality"] = int(count)

    df.drop(columns=[f"{prefix}idref_or_fullname" for prefix in prefixes] + ['__orig_index__'], inplace=True)

    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"), index=False)


if __name__ == "__main__":    
    centrality_features_for_participants("./data/", topics_suffix="[management]", verbose=True)
