import re
import unicodedata

NON_ALPHANUMERIC_PATTERN = re.compile(r"[^A-Za-z0-9]+")
NUMBER_WITH_REPETITION_PATTERN = re.compile(r"^(\d+)(BIS|TER|QUATER|B|T|Q)$")
STREET_WORDS = {
    "ALL": "ALLEE",
    "AV": "AVENUE",
    "AVE": "AVENUE",
    "BD": "BOULEVARD",
    "BLD": "BOULEVARD",
    "BOUL": "BOULEVARD",
    "CHE": "CHEMIN",
    "CHEM": "CHEMIN",
    "CHS": "CHAUSSEE",
    "CRS": "COURS",
    "FBG": "FAUBOURG",
    "HAM": "HAMEAU",
    "IMP": "IMPASSE",
    "LOT": "LOTISSEMENT",
    "MTE": "MONTEE",
    "PAS": "PASSAGE",
    "PL": "PLACE",
    "PLN": "PLAINE",
    "PROM": "PROMENADE",
    "QU": "QUAI",
    "R": "RUE",
    "RES": "RESIDENCE",
    "RPT": "ROND POINT",
    "RTE": "ROUTE",
    "SQ": "SQUARE",
    "ST": "SAINT",
    "STE": "SAINTE",
    "TRA": "TRAVERSE",
    "VLA": "VILLA",
}
REPETITION_WORDS = {"B": "BIS", "T": "TER", "Q": "QUATER"}
POSTAL_ONLY_WORDS = {"CEDEX", "BP", "CS", "TSA"}
COUNTRY_WORD = "FRANCE"
LEGAL_FORM_WORDS = {
    "SA",
    "SAS",
    "SASU",
    "SARL",
    "SARLU",
    "EURL",
    "SNC",
    "SCI",
    "SCP",
    "SCM",
    "SCOP",
    "SELARL",
    "SELAS",
    "GIE",
    "LTD",
    "LIMITED",
    "PLC",
    "LLC",
    "INC",
    "CORP",
    "GMBH",
    "AG",
    "BV",
    "NV",
    "SRL",
    "SPA",
    "SL",
}
LEGAL_FORM_PHRASES = (
    ("SOCIETE", "PAR", "ACTIONS", "SIMPLIFIEE"),
    ("SOCIETE", "A", "RESPONSABILITE", "LIMITEE"),
    ("SOCIETE", "ANONYME"),
    ("SOCIETE", "CIVILE", "IMMOBILIERE"),
)


def normalise_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(NON_ALPHANUMERIC_PATTERN.sub(" ", without_accents).upper().split())


def person_name_key(name: str) -> str:
    return normalise_text(name)


def without_phrase(words: list[str], phrase: tuple[str, ...]) -> list[str]:
    length = len(phrase)
    for start in range(len(words) - length + 1):
        if tuple(words[start : start + length]) == phrase:
            return words[:start] + words[start + length :]
    return words


def company_name_key(name: str) -> str:
    words = normalise_text(name.replace("&", " ET ")).split()
    for phrase in LEGAL_FORM_PHRASES:
        words = without_phrase(words, phrase)
    meaningful_words = [word for word in words if word not in LEGAL_FORM_WORDS]
    return " ".join(meaningful_words or words)


def address_words(words: list[str]) -> list[str]:
    key_words: list[str] = []
    skip_postal_number = False
    for position, word in enumerate(words):
        if skip_postal_number and word.isdigit():
            skip_postal_number = False
            continue
        skip_postal_number = word in POSTAL_ONLY_WORDS
        if skip_postal_number:
            continue
        repetition = NUMBER_WITH_REPETITION_PATTERN.match(word)
        if repetition is not None:
            key_words.extend([repetition[1], REPETITION_WORDS.get(repetition[2], repetition[2])])
            continue
        follows_number = position > 0 and words[position - 1].isdigit()
        if follows_number and word in REPETITION_WORDS:
            key_words.append(REPETITION_WORDS[word])
            continue
        key_words.extend(STREET_WORDS.get(word, word).split())
    return key_words


def address_key(address: str) -> str:
    words = address_words(normalise_text(address).split())
    if len(words) > 1 and words[-1] == COUNTRY_WORD:
        words = words[:-1]
    return " ".join(words)
