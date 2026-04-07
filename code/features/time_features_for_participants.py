import os
import numpy as np
import pandas as pd

from tqdm.auto import tqdm


def time_features_for_participants(path_to_data: str | os.PathLike, topics_suffix: str = "", verbose: bool = False):
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

    df['year'] = df['date_soutenance'].dt.year

    df["auteur.idref_or_fullname"] = df.apply(lambda row: row["auteur.idref"] if pd.notna(row["auteur.idref"]) else (str(row["auteur.nom"]) + "_" + str(row["auteur.prenom"]) if (pd.notna(row["auteur.nom"]) or pd.notna(row["auteur.prenom"])) else np.nan), axis='columns')

    def _parse_birth_series(s: pd.Series) -> pd.Series:
        result = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            parsed = pd.to_datetime(s, format=fmt, errors='coerce')
            result = result.fillna(parsed)

        if result.isna().any():
            years = s.astype(str).str.extract(r"(\d{4})")[0]
            fallback_dates = years.where(years.notna(), pd.NA).apply(lambda y: f"{y}-01-01" if pd.notna(y) else pd.NA)
            fallback = pd.to_datetime(fallback_dates, format="%Y-%m-%d", errors='coerce')
            result = result.fillna(fallback)

        return result

    auteur_birth = _parse_birth_series(df["auteur.birthdate"])
    auteur_year_diff = (df.date_soutenance.dt.year - auteur_birth.dt.year).astype('Int64')
    auteur_not_had_birthday = ((df.date_soutenance.dt.month < auteur_birth.dt.month) | ((df.date_soutenance.dt.month == auteur_birth.dt.month) & (df.date_soutenance.dt.day < auteur_birth.dt.day))).astype('Int64')
    df["auteur.age"] = (auteur_year_diff - auteur_not_had_birthday).astype('Int64')
    for prefix in prefixes:
        df[f"{prefix}idref_or_fullname"] = df.apply(lambda row: row[f"{prefix}idref"] if pd.notna(row[f"{prefix}idref"]) else (str(row[f"{prefix}nom"]) + "_" + str(row[f"{prefix}prenom"]) if (pd.notna(row[f"{prefix}nom"]) or pd.notna(row[f"{prefix}prenom"])) else np.nan), axis='columns')

        # Compute precise age in years (account for whether birthday already occurred)
        member_birth = _parse_birth_series(df[f"{prefix}birthdate"])
        year_diff = (df.date_soutenance.dt.year - member_birth.dt.year).astype('Int64')
        not_had_birthday = ((df.date_soutenance.dt.month < member_birth.dt.month) | ((df.date_soutenance.dt.month == member_birth.dt.month) & (df.date_soutenance.dt.day < member_birth.dt.day))).astype('Int64')
        df[f"{prefix}age"] = (year_diff - not_had_birthday).astype('Int64')
        df[f"{prefix}yrs_since_phd"] = pd.NA
        df[f"{prefix}yrs_since_first_jury"] = pd.NA

    unique_ids = pd.concat([df[f"{prefix}idref_or_fullname"] for prefix in prefixes]).unique().tolist()

    dates_for_unique_ids = {
        unique_id: {
            "defense_year": df.loc[df["auteur.idref_or_fullname"] == unique_id].iloc[0].year if not df.loc[df["auteur.idref_or_fullname"] == unique_id].empty else None,
            "first_jury_year": df.loc[(df[[f"{prefix}idref_or_fullname" for prefix in prefixes]] == unique_id).any(axis='columns')].year.min()
        } for unique_id in (tqdm(unique_ids, desc="Finding dates for each jury member") if verbose else unique_ids)
    }

    for idx, row in (tqdm(df.iterrows(), total=len(df.index)) if verbose else df.iterrows()):
        for prefix in prefixes:
            member_defense_year = dates_for_unique_ids[row[f"{prefix}idref_or_fullname"]]["defense_year"]
            member_first_jury_year = dates_for_unique_ids[row[f"{prefix}idref_or_fullname"]]["first_jury_year"]
            if member_defense_year:
                df.loc[idx, f"{prefix}yrs_since_phd"] = row.year - member_defense_year
            if member_first_jury_year:
                df.loc[idx, f"{prefix}yrs_since_first_jury"] = row.year - member_first_jury_year

    for prefix in prefixes:
        df[f"{prefix}yrs_since_phd"] = df[f"{prefix}yrs_since_phd"].astype("Int64")
        df[f"{prefix}yrs_since_first_jury"] = df[f"{prefix}yrs_since_first_jury"].astype("Int64")
    
    df.drop(columns=[f"{prefix}idref_or_fullname" for prefix in ["auteur."] + prefixes], inplace=True)
    if topics_suffix == "[full_data]":
        df.drop(columns=["year"], inplace=True)

    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"), index=False)


if __name__ == "__main__":    
    time_features_for_participants("./data/", topics_suffix="[full_data]", verbose=True)
