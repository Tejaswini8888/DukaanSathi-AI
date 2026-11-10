
import re

# ==========================================
# PRODUCT NAMES AND COMMON SPEECH VARIATIONS
# ==========================================

PRODUCT_ALIASES = {
    "rice": ["rice", "raice", "రైస్", "రైసు"],
    "sugar": ["sugar", "షుగర్"],
    "sunflower oil": [
        "sunflower oil",
        "sun flower oil",
        "sunflour oil",
        "సన్ ఫ్లవర్ ఆయిల్",
        "సన్ఫ్లవర్ ఆయిల్",
        "సన్‌ఫ్లవర్ ఆయిల్"
    ],
    "milk": ["milk", "మిల్క్", "పాలు"],
    "groundnut oil": [
        "groundnut oil",
        "ground nut oil",
        "వేరుశెనగ నూనె"
    ]
}

# ==========================================
# SUPPORTED QUANTITY UNITS
# ==========================================

UNIT_ALIASES = {
    "kg": ["kg", "kilo", "kilos", "kilogram", "kilograms", "కిలో", "కిలోస్"],
    "litre": ["litre", "litres", "liter", "liters", "లీటర్", "లీటర్లు"],
    "packet": ["packet", "packets", "ప్యాకెట్", "ప్యాకెట్లు"],
    "piece": ["piece", "pieces", "పీస్", "పీసులు"]
}

# ==========================================
# NUMBER WORDS
# ==========================================

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,

    # Telugu speech-recognition variations
    "వన్": 1,
    "టూ": 2,
    "త్రీ": 3,
    "ఫోర్": 4,
    "ఫైవ్": 5,
    "సిక్స్": 6,
    "సెవెన్": 7,
    "ఎయిట్": 8,
    "నైన్": 9,
    "టెన్": 10
}

# Common Telugu names converted to English
TELUGU_NAMES = {
    "రవి": "Ravi",
    "రమేష్": "Ramesh",
    "సురేష్": "Suresh",
    "రాజు": "Raju",
    "రాహుల్": "Rahul",
    "ప్రియా": "Priya",
    "సాయి": "Sai",
    "కిరణ్": "Kiran"
}

# ==========================================
# TEXT NORMALIZATION
# ==========================================

def normalize_text(text):
    """Convert text into searchable lowercase format."""

    text = str(text).lower().strip()
    text = text.replace("‌", "")
    text = re.sub(r"[.,!?;:]", " ", text)

    return re.sub(r"\s+", " ", text).strip()


# ==========================================
# CUSTOMER NAME EXTRACTION
# ==========================================

def extract_customer(transcript):
    """Extract customer name from English or Telugu speech."""

    text = normalize_text(transcript)

    patterns = [
        # English: Ravi ki, Ravi for
        r"\b([a-zA-Z]+)\s*(?:ki|kee|k)\b",
        r"\b([a-zA-Z]+)\s+(?:for|to)\b",

        # English: customer name is Ravi
        r"\bcustomer name is\s+([a-zA-Z]+)\b",
        r"\bname is\s+([a-zA-Z]+)\b",

        # Telugu: రవికి or రవి కి
        r"([ఀ-౿]+?)\s*కి(?:\s|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            name = match.group(1).strip()

            if name in TELUGU_NAMES:
                return TELUGU_NAMES[name]

            if re.fullmatch(r"[a-zA-Z]+", name):
                return name.capitalize()

            return name

    return None


# ==========================================
# NUMBER EXTRACTION
# ==========================================

def extract_number(value):
    """Convert digits and spoken number words to numbers."""

    value = normalize_text(value)

    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)

    return float(NUMBER_WORDS.get(value, 0))


# ==========================================
# PRODUCT AND QUANTITY EXTRACTION
# ==========================================


def extract_items(transcript):
    """Extract products, quantities and units from English and Telugu speech."""

    text = normalize_text(transcript)
    extracted_items = []

    product_display_names = {
        "rice": "Rice",
        "sugar": "Sugar",
        "sunflower oil": "Sunflower Oil",
        "milk": "Milk",
        "groundnut oil": "Groundnut Oil"
    }

    # Build flexible patterns from the supported aliases
    number_pattern = "|".join(
        re.escape(word)
        for word in sorted(NUMBER_WORDS.keys(), key=len, reverse=True)
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

            # Find product in the transcript
            product_position = text.find(normalized_alias)

            if product_position == -1:
                continue

            # Check quantity and unit immediately before product
            preceding_text = text[:product_position]

            pattern = (
                rf"({number_pattern})\s+"
                rf"({unit_pattern})\s*$"
            )

            match = re.search(pattern, preceding_text, re.IGNORECASE)

            if not match:
                continue

            quantity = extract_number(match.group(1))

            if quantity <= 0:
                continue

            spoken_unit = match.group(2).lower()

            # Identify canonical unit
            unit = None

            for canonical, unit_aliases in UNIT_ALIASES.items():
                if spoken_unit in [x.lower() for x in unit_aliases]:
                    unit = canonical
                    break

            if not unit:
                continue

            extracted_items.append({
                "product": product_display_names[product],
                "quantity": quantity,
                "unit": unit
            })

            break

    return extracted_items



# ==========================================
# MAIN ORDER UNDERSTANDING FUNCTION
# ==========================================

def understand_order(transcripts):
    """
    Accept Gnani multilingual transcripts
    and extract customer and product details.
    """

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
