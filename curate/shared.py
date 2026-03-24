"""
shared.py — CardioOracle curation pipeline shared utilities.
DB connection, drug/endpoint taxonomy, classification helpers.
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()


def get_aact_connection():
    """Return a psycopg2 connection to the AACT database.

    Reads AACT_USER and AACT_PASSWORD from the environment (.env file).
    Raises ValueError if credentials are missing.
    """
    import psycopg2

    user = os.environ.get("AACT_USER")
    password = os.environ.get("AACT_PASSWORD")

    if not user or not password:
        raise ValueError(
            "AACT_USER and AACT_PASSWORD must be set in the environment or .env file. "
            "Never hard-code credentials."
        )

    conn = psycopg2.connect(
        host="aact-db.ctti-clinicaltrials.org",
        port=5432,
        dbname="aact",
        user=user,
        password=password,
        connect_timeout=30,
        sslmode="require",
    )
    return conn


# ---------------------------------------------------------------------------
# Drug class taxonomy
# ---------------------------------------------------------------------------

DRUG_CLASS_MAP = {
    "sglt2i": {
        "label": "SGLT2 inhibitor",
        "drugs": [
            "empagliflozin",
            "dapagliflozin",
            "canagliflozin",
            "ertugliflozin",
            "sotagliflozin",
            "ipragliflozin",
            "tofogliflozin",
            "luseogliflozin",
        ],
    },
    "mra": {
        "label": "Mineralocorticoid receptor antagonist (steroidal)",
        "drugs": [
            "spironolactone",
            "eplerenone",
        ],
    },
    "ns_mra": {
        "label": "Non-steroidal MRA",
        "drugs": [
            "finerenone",
            "esaxerenone",
            "apararenone",
            "ocedurenone",
        ],
    },
    "arni": {
        "label": "Angiotensin receptor-neprilysin inhibitor",
        "drugs": [
            "sacubitril",
            "entresto",
            "sacubitril/valsartan",
        ],
    },
    "arb": {
        "label": "Angiotensin II receptor blocker",
        "drugs": [
            "valsartan",
            "losartan",
            "candesartan",
            "irbesartan",
            "telmisartan",
            "olmesartan",
            "azilsartan",
        ],
    },
    "acei": {
        "label": "ACE inhibitor",
        "drugs": [
            "enalapril",
            "ramipril",
            "lisinopril",
            "perindopril",
            "captopril",
            "quinapril",
            "benazepril",
            "fosinopril",
        ],
    },
    "bb": {
        "label": "Beta-blocker",
        "drugs": [
            "carvedilol",
            "bisoprolol",
            "metoprolol",
            "nebivolol",
            "atenolol",
        ],
    },
    "glp1ra": {
        "label": "GLP-1 receptor agonist",
        "drugs": [
            "semaglutide",
            "liraglutide",
            "dulaglutide",
            "exenatide",
            "albiglutide",
            "lixisenatide",
            "tirzepatide",
        ],
    },
    "pcsk9i": {
        "label": "PCSK9 inhibitor",
        "drugs": [
            "evolocumab",
            "alirocumab",
            "inclisiran",
        ],
    },
    "statin": {
        "label": "Statin",
        "drugs": [
            "atorvastatin",
            "rosuvastatin",
            "simvastatin",
            "pravastatin",
            "lovastatin",
            "fluvastatin",
            "pitavastatin",
        ],
    },
    "anticoag": {
        "label": "Anticoagulant",
        "drugs": [
            "apixaban",
            "rivaroxaban",
            "edoxaban",
            "dabigatran",
            "warfarin",
        ],
    },
    "antiplat": {
        "label": "Antiplatelet",
        "drugs": [
            "ticagrelor",
            "prasugrel",
            "clopidogrel",
            "aspirin",
            "cangrelor",
        ],
    },
    "other": {
        "label": "Other / Unknown",
        "drugs": [],
    },
}

# Regex to strip dosage text before drug matching
_DOSAGE_RE = re.compile(r"\d+\s*(mg|mcg|ml|iu|units?)\b", re.IGNORECASE)


def classify_drug(intervention_name: str) -> str:
    """Return the drug class ID for the given intervention name.

    Normalises the name to lowercase, strips dosage text, then checks each
    class (skipping 'other') for a substring match against the drug list.

    Returns 'other' if no match is found.
    """
    if not intervention_name:
        return "other"

    normalised = intervention_name.lower()
    normalised = _DOSAGE_RE.sub("", normalised).strip()

    for class_id, class_info in DRUG_CLASS_MAP.items():
        if class_id == "other":
            continue
        for drug in class_info["drugs"]:
            if drug in normalised:
                return class_id

    return "other"


# ---------------------------------------------------------------------------
# Endpoint type taxonomy (priority-ordered list of tuples)
# ---------------------------------------------------------------------------

ENDPOINT_TYPE_MAP = [
    ("mace", ["mace", "major adverse cardiovascular", "composite cardiovascular"]),
    (
        "hf_hosp",
        [
            "heart failure hospitalization",
            "hf hospitalization",
            "worsening heart failure",
            "hf hospitalisation",
        ],
    ),
    (
        "cv_death",
        [
            "cardiovascular death",
            "cardiac death",
            "cv death",
            "cardiovascular mortality",
        ],
    ),
    (
        "acm",
        [
            "all-cause mortality",
            "all cause mortality",
            "overall survival",
            "death from any cause",
        ],
    ),
    (
        "renal",
        [
            "egfr",
            "kidney",
            "renal",
            "dialysis",
            "eskd",
            "doubling of creatinine",
            "sustained decrease",
        ],
    ),
    (
        "surrogate",
        [
            "blood pressure",
            "ldl",
            "hba1c",
            "nt-probnp",
            "ejection fraction",
            "6-minute walk",
            "biomarker",
        ],
    ),
]


def classify_endpoint(measure_text: str) -> str:
    """Return the endpoint type ID for the given outcome measure text.

    Iterates ENDPOINT_TYPE_MAP in priority order and returns the first match.
    Returns 'other' if no match is found.
    """
    if not measure_text:
        return "other"

    lower = measure_text.lower()

    for endpoint_id, keywords in ENDPOINT_TYPE_MAP:
        for keyword in keywords:
            if keyword in lower:
                return endpoint_id

    return "other"
