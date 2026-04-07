"""Module fetching data from the IdRef files downloaded and stores them in a CSV table."""

from pprint import pprint
from collections import defaultdict
import os
import csv
from typing import Optional

import pandas as pd
import rdflib
from tqdm import tqdm


def produce_idref_datatable(path_to_data: str | os.PathLike[str], topics_suffix: str = "", 
                            research_topics: Optional[list[str]] = None, verbose=False):
    """Fetches data from the IdRef files downloaded and stores them in a CSV table.

    Parameters
    ----------
    path_to_data: str | os.PathLike[str]
        Path to the `data` folder (assuming a DSLP-like architecture).
    topics_suffix: str, default ""
        A string positioned at the end of the produced files names to help identify the topics handled.
    research_topics : list[str], optional
        Research topics to keep for the IdRef search part of the function. If `None`, keeps 
        all the research topics.
    verbose : bool, default False
        Whether the function should print progress indicators (`True`) or not (`False`)
    """

    if verbose:
        print("Parsing Lexvo graph...")
    path_to_idref_graphs = os.path.join(path_to_data, "raw/idrefs/")
    lang_g = rdflib.Graph()
    lang_g.parse(os.path.join(path_to_data, "raw/lexvo.rdf"))
    SKOS = rdflib.Namespace("http://www.w3.org/2008/05/skos#")

    language_URI_to_name = {}
    country_URI_to_name = {}

    if verbose:
            print("Fetching IdRefs from theses.fr dataset...")
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

    with open(os.path.join(path_to_data, f"interim/idref_datatable{topics_suffix}.csv"), "w", encoding="utf8") as f:
        fieldnames = ["idref", "givenname", "familyname", "gender", "birthdate", "deathdate", "languages", "country"]
        datatable = csv.DictWriter(f, fieldnames=fieldnames)
        datatable.writeheader()

        false_uris_log = defaultdict(int)

        for idref in (tqdm(idrefs, desc="Identifying description from IdRefs") if verbose else os.listdir(path_to_idref_graphs)):
            g = rdflib.Graph()
            try:
                g.parse(path_to_idref_graphs + str(idref) + ".rdf")
            except FileNotFoundError:
                if verbose:
                    print(f"File {str(idref) + '.rdf'} was not found, skipping.")
                continue

            query_results = g.query(GET_DATA_FROM_PERSON_q.format(idref=idref)).bindings
            gender = str(query_results[0]["gender"])
            givenname = str(query_results[0]["givenname"]).strip()
            familyname = str(query_results[0]["familyname"]).strip()
            birthdate = query_results[0]["birthdate"]
            deathdate = query_results[0]["deathdate"]
            language_URIs = [str(query_result["language"]) for query_result in query_results]
            country_URI = query_results[0]["country"].replace("http:", "https:", 1)

            if birthdate == "19XX":
                birthdate = ""
            if deathdate == "19XX":
                deathdate = ""

            # Quick fix to avoid the query from yielding the IdRef file path in cases where the
            # dbpedia-owl:citizenship predicate points to an empty string.
            if country_URI.startswith("file://"):
                country_URI = ""

            languages = []
            for language_URI in language_URIs:
                if language_URI:
                    try:
                        if language_URI not in language_URI_to_name:
                            language_URI_to_name[language_URI] = get_language_from_uri(language_URI, lang_g, SKOS)
                        languages.append(language_URI_to_name[language_URI])
                    except IndexError:
                        false_uris_log[language_URI] += 1

            if country_URI:
                if country_URI not in country_URI_to_name:
                    country_URI_to_name[country_URI] = get_country_from_uri(country_URI)
                country = country_URI_to_name[country_URI]
            else:
                country = ""

            datatable.writerow({
                "idref": idref,
                "gender": gender,
                "givenname": givenname,
                "familyname": familyname,
                "birthdate": birthdate,
                "deathdate": deathdate,
                "languages": ",".join(languages),
                "country": country
            })
    if verbose:
        print("Data table complete!")
        print("False language URIs:")
        pprint(sorted(((v,k) for k,v in (false_uris_log).items()), key=lambda x: x[0], reverse=True))


def get_language_from_uri(uri: str, lang_g: rdflib.Graph, ns: rdflib.Namespace) -> str:
    query_result = list(lang_g.objects(rdflib.URIRef(uri), ns.prefLabel))[0]
    language = str(query_result)

    return language


def get_country_from_uri(uri: str) -> str:
    rdf_url = uri + "about.rdf"

    country_g = rdflib.Graph()
    country_g.parse(rdf_url)

    query_result = country_g.query(GET_COUNTRY_NAME_FROM_URI_q.format(countryURI=uri)).bindings[0]
    country = query_result["countryName"]

    return country


GET_DATA_FROM_PERSON_q = """
SELECT DISTINCT (COALESCE(?Gender, "") AS ?gender) 
                (COALESCE(?Givenname, "") AS ?givenname)
                (COALESCE(?Familyname, "") AS ?familyname)
                (COALESCE(?Birthdate, "") AS ?birthdate) 
                (COALESCE(?Deathdate, "") AS ?deathdate) 
                (COALESCE(?Language, "") AS ?language) 
                (COALESCE(?CountryId, "") AS ?country) WHERE {{
    OPTIONAL {{ <http://www.idref.fr/{idref}/id> foaf:gender ?Gender }} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/id> foaf:givenName ?Givenname }} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/id> foaf:familyName ?Familyname }} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/birth> bio:date ?BirthdateNum .
                BIND(STR(?BirthdateNum) as ?Birthdate)}} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/death> bio:date ?DeathdateNum .
                BIND(STR(?DeathdateNum) as ?Deathdate) }} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/id> dcterms:language ?Language }} .
    OPTIONAL {{ <http://www.idref.fr/{idref}/id> dbpedia-owl:citizenship ?CountryId }} .
}}
"""

GET_COUNTRY_NAME_FROM_URI_q = """
PREFIX gn: <http://www.geonames.org/ontology#>

SELECT DISTINCT ?countryName WHERE {{
    <{countryURI}> gn:name ?countryName
}}
"""

if __name__ == "__main__":
    produce_idref_datatable("./data", research_topics=["Sciences économiques", "Sciences de gestion", "Sciences de Gestion", "Gestion", "Économie", "Analyse et politique économiques", "Sciences economiques", "Economie"], verbose=True)
