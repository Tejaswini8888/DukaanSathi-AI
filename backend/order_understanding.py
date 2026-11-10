
import re
import unicodedata

# ==========================================
# PRODUCT NAMES AND SPEECH VARIATIONS
# ==========================================

PRODUCT_ALIASES = {
    "rice": [
        "rice", "raice", "రైస్", "రైసు", "బియ్యం", "బియ్యము"
    ],
    "sugar": [
        "sugar", "షుగర్", "చక్కెర"
    ],
    "sunflower oil": [
        "sunflower oil", "sun flower oil", "sunflour oil",
        "సన్ ఫ్లవర్ ఆయిల్", "సన్ఫ్లవర్ ఆయిల్",
        "సన్‌ఫ్లవర్ ఆయిల్"
    ],
    "milk": [
        "milk", "మిల్క్", "పాలు"
    ],
    "wheat flour": [
        "wheat flour", "wheat powder", "గోధుమ పిండి",
        "గోధుమపిండి"
    ],
    "toor dal": [
        "toor dal", "toor dhal", "తూర్ దాల్",
        "కందిపప్పు"
    ],
    "tea powder": [
        "tea powder", "tea", "టీ పొడి", "టీ పౌడర్"
    ],
    "salt": [
        "salt", "సాల్ట్", "ఉప్పు"
    ],
    "groundnut oil": [
        "groundnut oil", "ground nut oil",
        "వేరుశెనగ నూనె", "గ్రౌండ్నట్ ఆయిల్"
    ]
}

PRODUCT_DISPLAY_NAMES = {
    "rice": "Rice",
    "sugar": "Sugar",
    "sunflower oil": "Sunflower Oil",
    "milk": "Milk",
    "wheat flour": "Wheat Flour",
    "toor dal": "Toor Dal",
    "tea powder": "Tea Powder",
    "salt": "Salt",
    "groundnut oil": "Groundnut Oil"
}

# ==========================================
# UNIT ALIASES
# ==========================================

UNIT_ALIASES = {
    "kg": [
        "kg", "kgs", "kilo", "kilos",
        "kilogram", "kilograms",
        "కిలో", "కిలోలు", "కిలోల", "కిలోగ్రాములు"
    ],
    "litre": [
        "litre", "litres", "liter", "liters",
        "l", "లీటర్", "లీటర్లు", "లీటర్ల"
    ],
    "packet": [
        "packet", "packets", "ప్యాకెట్", "ప్యాకెట్లు"
    ],
    "piece": [
        "piece", "pieces", "పీస్", "పీసులు"
    ]
}

# ==========================================
# NUMBER WORDS
# ==========================================

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9,
    "ten": 10,

    "వన్": 1, "టూ": 2, "త్రీ": 3,
    "ఫోర్": 4, "ఫైవ్": 5, "సిక్స్": 6,
    "సెవెన్": 7, "ఎయిట్": 8,
    "నైన్": 9, "టెన్": 10,

    "ఒక": 1, "ఒకటి": 1,
    "రెండు": 2, "మూడు": 3,
    "నాలుగు": 4, "ఐదు": 5,
    "ఆరు": 6, "ఏడు": 7,
    "ఎనిమిది": 8, "తొమ్మిది": 9,
    "పది": 10
}

# ==========================================
# CUSTOMER NAMES
# ==========================================

TELUGU_NAMES = {
    "రవి": "Ravi",
    "రమేష్": "Ramesh",
    "సురేష్": "Suresh",
    "రాజు": "Raju",
    "రాహుల్": "Rahul",
    "ప్రియా": "Priya",
    "సాయి": "Sai",
    "కిరణ్": "Kiran",
    "లక్ష్మి": "Lakshmi",
    "రమ్య": "Ramya",
    "శ్రీను": "Srinu"
}

# ==========================================
# TEXT NORMALIZATION
# ==========================================

def normalize_text(text):
    text = unicodedata.normalize("NFC", str(text).lower().strip())

    text = text.replace("\u200c", "").replace("\u200d", "")
    text = text.replace("\u200b", "").replace("‌", "")

    text = re.sub(r"[.,!?;:]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================
# CUSTOMER EXTRACTION
# ==========================================

def extract_customer(transcript):

    text = normalize_text(transcript)

    patterns = [
        r"\bcustomer name is\s+([a-z]+)\b",
        r"\bname is\s+([a-z]+)\b",
        r"\b([a-z]+)\s+(?:ki|kee|k)\b",
        r"\b([a-z]+)\s+(?:needs|wants|requires)\b",
        r"\b([a-z]+)\s+(?:for|to)\b",
        r"([ఀ-౿]+)\s*కి"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            name = match.group(1).strip()

            if name in TELUGU_NAMES:
                return TELUGU_NAMES[name]

            if re.fullmatch(r"[a-z]+", name):
                return name.capitalize()

            return name

    return None


# ==========================================
# NUMBER EXTRACTION
# ==========================================

def extract_number(value):

    value = normalize_text(value)

    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)

    return float(NUMBER_WORDS.get(value, 0))


# ==========================================
# PRODUCT AND QUANTITY EXTRACTION
# ==========================================

def extract_items(transcript):

    text = normalize_text(transcript)
    extracted_items = []

    number_pattern = "|".join(
        re.escape(word)
        for word in sorted(NUMBER_WORDS, key=len, reverse=True)
    )

    number_pattern = rf"(?:\d+(?:\.\d+)?|{number_pattern})"

    all_units = [
        alias
        for aliases in UNIT_ALIASES.values()
        for alias in aliases
    ]

    unit_pattern = "|".join(
        re.escape(unit)
        for unit in sorted(all_units, key=len, reverse=True)
    )

    for product, aliases in PRODUCT_ALIASES.items():

        for alias in sorted(aliases, key=len, reverse=True):

            normalized_alias = normalize_text(alias)
            product_position = text.find(normalized_alias)

            if product_position == -1:
                continue

            preceding_text = text[:product_position].strip()

            pattern = (
                rf"({number_pattern})\s+"
                rf"({unit_pattern})"
                rf"(?:\s+of)?\s*$"
            )

            match = re.search(
                pattern,
                preceding_text,
                re.IGNORECASE
            )

            if not match:
                continue

            quantity = extract_number(match.group(1))

            if quantity <= 0:
                continue

            spoken_unit = match.group(2).lower()

            canonical_unit = None

            for canonical, unit_aliases in UNIT_ALIASES.items():

                if spoken_unit in [
                    normalize_text(x) for x in unit_aliases
                ]:
                    canonical_unit = canonical
                    break

            if not canonical_unit:
                continue

            extracted_items.append({
                "product": PRODUCT_DISPLAY_NAMES[product],
                "quantity": quantity,
                "unit": canonical_unit
            })

            break

    return extracted_items


# ==========================================
# MAIN ORDER UNDERSTANDING FUNCTION
# ==========================================

def understand_order(transcripts):

    if isinstance(transcripts, dict):
        combined_text = " ".join(
            str(value)
            for value in transcripts.values()
            if value
        )
    else:
        combined_text = str(transcripts)

    customer_name = extract_customer(combined_text)
    items = extract_items(combined_text)

    if not customer_name:
        return {
            "success": False,
            "message": "Customer name could not be identified",
            "customer_name": None,
            "items": []
        }

    if not items:
        return {
            "success": False,
            "message": "Products or quantities could not be identified",
            "customer_name": customer_name,
            "items": []
        }

    return {
        "success": True,
        "message": "Order understood successfully",
        "customer_name": customer_name,
        "items": items
    }
