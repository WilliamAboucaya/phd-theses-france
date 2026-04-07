import os
import re
import pandas as pd


def count_features(path_to_data: str | os.PathLike, topics_suffix: str = "", verbose: bool = False):
    if os.path.exists(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet")):
        file_name = f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"
    else:
        file_name = f"processed/theses-soutenues-gender-guessed{topics_suffix}.parquet"

    file_path = os.path.join(path_to_data, file_name)
    df = pd.read_parquet(file_path)
    
    if verbose:
        print(f"Nb of theses: {len(df.index)}")

    columns_to_convert = ['accessible', 'cas', 'code_etab', 'langue.0', 'langue.1', 'langue.2']

    # Convert each column to category
    for col in columns_to_convert:
        if col in df.columns:  # Ensure the column exists in the DataFrame
            df[col] = df[col].astype('category')

    df['num_languages'] = df[[f'langue.{i}' for i in range(4) if f'langue.{i}' in df.columns]].notna().sum(axis=1)
    
    columns_for_existence = {
        "directeur": [[f"directeur.{i}.idref", f"directeur.{i}.nom", f"directeur.{i}.prenom"] for i in range(6) if f"directeur.{i}.idref" in df.columns],
        "membre_jury": [[f"membre_jury.{i}.idref", f"membre_jury.{i}.nom", f"membre_jury.{i}.prenom"] for i in range(12) if f"membre_jury.{i}.idref" in df.columns],
        "partenaire_recherche": [[f"partenaire_recherche.{i}.idref", f"partenaire_recherche.{i}.nom"] for i in range(7) if f"partenaire_recherche.{i}.idref" in df.columns],
        "rapporteur": [[f"rapporteur.{i}.idref", f"rapporteur.{i}.nom", f"rapporteur.{i}.prenom"] for i in range(5) if f"rapporteur.{i}.idref" in df.columns]
    }

    for entity_type, entities in columns_for_existence.items():
        for i, columns in enumerate(entities):
            df[f"{entity_type}.{i}.exists"] = df[columns].notna().any(axis="columns")

    patterns_to_count = {
        r"directeur.\d+\.exists": "num_directeurs",
        r"membre_jury\.\d+\.exists": "num_membres_jury",
        r"partenaire_recherche\.\d+\.exists": "num_partenaires_recherche",
        r"rapporteur\.\d+\.exists": "num_rapporteurs"
    }

    # Iterate through patterns and count the columns matching each pattern
    for pattern, new_var in patterns_to_count.items():
        # Find columns matching the specific pattern using regex
        matching_cols = [col for col in df.columns if re.match(pattern, col)]
        
        # Count non-missing values (indicating the presence of a value) across matching columns
        df[new_var] = df[matching_cols].astype(int).sum(axis="columns")
        df.drop(matching_cols, axis="columns", inplace=True)

    df.to_parquet(os.path.join(path_to_data, f"processed/theses-soutenues-enhanced{topics_suffix}.parquet"), index=False)


if __name__ == "__main__":    
    count_features("./data/", topics_suffix="[full_data]", verbose=True)