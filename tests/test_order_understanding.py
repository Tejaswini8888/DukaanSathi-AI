
from backend.order_understanding import understand_order

transcripts = {
    "en-IN": "ramesh k two kilos rice one litre sunflower oil bill chaahiye",
    "te-IN": "రమేష్కి టూ కిలోస్ రైసు వన్ లీటర్ సన్ ఫ్లోర్ ఆయిల్ బిల్ చెయ్యి"
}

result = understand_order(transcripts)

print(result)
