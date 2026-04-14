"""Generator voor realistische recepttitels en ingrediënten.

Bevat lijsten met bijvoeglijke naamwoorden, receptbasissen en
extra-ingredienten per type en helperfuncties om plausibele recepten te
genereren.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

# Bijvoeglijke naamwoorden die aan titels worden voorafgeplaatst
ADJECTIVES = [
    "Pittig",
    "Romig",
    "Kruidig",
    "Rokerig",
    "Zurig",
    "Citrus",
    "Knoflook",
    "Honingglazuur",
    "Krokant",
    "Langzaam gegaard",
    "Geroosterd",
    "Gegrild",
    "Vers",
    "Fris",
    "Warm",
    "Zijdezacht",
    "Snel",
    "Makkelijk",
    "Eenpans",
    "Veganistisch",
    "Vegetarisch",
    "Glutenvrij",
    "Koolhydraatarm",
    "Comfortfood",
    "Vullend",
    "Licht",
    "Citroen",
    "Ahornsiroop",
    "Gekarameliseerd",
    "Gekruid",
    "Mediterraan",
    "Aziatisch",
    "Romantisch",
    "Familie-favoriet",
    "Barbecue",
    "Herfstig",
    "Lente",
    "Winterwarm",
    "Zomers",
    "Kruidig-zoet",
    "Smaakvol",
    "Authentiek",
    "Gourmet",
    "Budgetvriendelijk",
    "Kinderproof",
]


# Receptbasissen met canonical ingrediëntenlijst en directe categorie (Nederlands)
RECIPE_BASES = [
    (
        "Pasta Carbonara",
        ["spaghetti", "eieren", "parmezaan", "pancetta", "zwarte peper"],
        "Diner",
    ),
    (
        "Tomaat-basilicumsoep",
        ["tomaten", "basilicum", "ui", "knoflook", "groentebouillon"],
        "Voorgerecht",
    ),
    (
        "Kip roerbak",
        ["kipfilet", "sojasaus", "knoflook", "gember", "groente-olie"],
        "Diner",
    ),
    (
        "Kikkererwtencurry",
        ["kikkererwten", "kokosmelk", "kerriepoeder", "ui", "tomaat"],
        "Diner",
    ),
    (
        "Griekse salade",
        ["komkommer", "tomaat", "feta", "olijfolie", "olijven"],
        "Lunch",
    ),
    (
        "Runderstoofpot",
        ["stoofvlees", "wortels", "aardappelen", "ui", "runderbouillon"],
        "Diner",
    ),
    (
        "Groenterisotto",
        ["arborio rijst", "parmezaan", "witte wijn", "champignons", "groentebouillon"],
        "Diner",
    ),
    ("Vistaco's", ["witte vis", "tortilla's", "kool", "limoen", "koriander"], "Diner"),
    (
        "Pizza Margherita",
        ["pizzadeeg", "mozzarella", "tomatensaus", "basilicum", "olijfolie"],
        "Diner",
    ),
    ("Bananenbrood", ["bananen", "bloem", "boter", "suiker", "eieren"], "Ontbijt"),
    (
        "Havermoutpannenkoeken",
        ["havermout", "melk", "ei", "bakpoeder", "vanille"],
        "Ontbijt",
    ),
    (
        "Quinoasalade",
        ["quinoa", "citroen", "olijfolie", "komkommer", "cherrytomaatjes"],
        "Lunch",
    ),
    (
        "Linzensoep",
        ["linzen", "wortel", "selderij", "ui", "groentebouillon"],
        "Voorgerecht",
    ),
    (
        "Garnalen scampi",
        ["garnalen", "knoflook", "boter", "citroen", "peterselie"],
        "Diner",
    ),
    (
        "Rundertaco's",
        ["rundergehakt", "tortilla's", "sla", "cheddar", "salsa"],
        "Diner",
    ),
    (
        "Geroosterde kip",
        ["hele kip", "rozemarijn", "knoflook", "citroen", "olijfolie"],
        "Diner",
    ),
    (
        "Miso ramen",
        ["ramen noedels", "misopasta", "dashi", "lente-ui", "ei"],
        "Diner",
    ),
    (
        "Appelcrumble",
        ["appels", "haver", "boter", "bruine suiker", "kaneel"],
        "Nagerecht",
    ),
    (
        "Tofu roerbak",
        ["tofu", "sojasaus", "knoflook", "broccoli", "sesamolie"],
        "Diner",
    ),
    ("Hummus", ["kikkererwten", "tahini", "citroen", "knoflook", "olijfolie"], "Snack"),
]

# Extra voorbeelden en variaties voor meer combinaties
RECIPE_BASES += [
    (
        "Spinazie-feta frittata",
        ["eieren", "spinazie", "feta", "ui", "olijfolie"],
        "breakfast",
    ),
    (
        "Butternut pompoensoep",
        ["butternut pompoen", "ui", "knoflook", "groentebouillon", "room"],
        "soup",
    ),
    (
        "Pulled pork sandwich",
        ["varkensschouder", "barbecuesaus", "broodjes", "coleslaw", "augurk"],
        "baked",
    ),
    ("Shakshuka", ["eieren", "tomaat", "ui", "paprika", "komijn"], "breakfast"),
    ("Ceviche", ["witte vis", "limoensap", "ui", "koriander", "peper"], "seafood"),
    (
        "Thaise groene curry",
        ["kip", "groene currypasta", "kokosmelk", "basilicum", "aubergine"],
        "curry",
    ),
    (
        "Boeuf Bourguignon",
        ["runderstoofvlees", "rode wijn", "wortel", "ui", "champignons"],
        "stew",
    ),
    (
        "Courgettekoekjes",
        ["courgette", "ei", "bloem", "parmezaan", "knoflook"],
        "snack",
    ),
    (
        "Aubergine Parmigiana",
        ["aubergine", "tomatensaus", "mozzarella", "parmezaan", "basilicum"],
        "dinner",
    ),
    ("Dal van linzen", ["linzen", "uien", "komijn", "kurkuma", "kokosmelk"], "curry"),
    (
        "Paneer Tikka",
        ["paneer", "yoghurt", "tikka masala", "paprika", "limoen"],
        "dinner",
    ),
    ("Sushi bowl", ["sushi rijst", "zalm", "avocado", "komkommer", "sojasaus"], "rice"),
    (
        "BBQ spareribs",
        ["varkensribben", "barbecuesaus", "kool", "mais", "aardappels"],
        "dinner",
    ),
    ("Falafel wrap", ["kikkererwten", "kruiden", "salade", "tahini", "wrap"], "lunch"),
    (
        "Zoete aardappel frietjes",
        ["zoete aardappel", "olijfolie", "paprikapoeder", "zout", "peper"],
        "snack",
    ),
    (
        "Yoghurt parfait",
        ["Griekse yoghurt", "muesli", "bessen", "honing", "noten"],
        "breakfast",
    ),
    (
        "Paddenstoelenstroganoff",
        ["paddenstoelen", "zure room", "ui", "paprikapoeder", "pasta"],
        "pasta",
    ),
    (
        "Caesar salade met kip",
        ["kropsla", "kip", "croutons", "Parmezaan", "Caesar dressing"],
        "lunch",
    ),
    ("Poke bowl", ["rijst", "tonijn", "sojasaus", "zeewier", "edamame"], "rice"),
    (
        "Gebakken zalm",
        ["zalmfilet", "citroen", "dille", "boter", "olijfolie"],
        "seafood",
    ),
    ("Scones", ["bloem", "boter", "melk", "bakpoeder", "suiker"], "baked"),
    ("Crêpes", ["bloem", "melk", "eieren", "boter", "suiker"], "breakfast"),
    (
        "Gnocchi met tomatensaus",
        ["gnocchi", "tomatensaus", "parmezaan", "basilicum", "olijfolie"],
        "pasta",
    ),
    (
        "Polenta met paddenstoelen",
        ["polenta", "paddenstoelen", "Parmezaan", "boter", "tijm"],
        "rice",
    ),
    ("Ratatouille", ["aubergine", "courgette", "tomaat", "paprika", "ui"], "dinner"),
    ("Chili con carne", ["rundergehakt", "bonen", "tomaat", "chili", "ui"], "dinner"),
    (
        "Geroosterde pompoen salade",
        ["pompoen", "rucola", "feta", "walnoten", "vinaigrette"],
        "salad",
    ),
    ("Shiitake miso soep", ["shiitake", "miso", "tofu", "dashi", "lente-ui"], "soup"),
]


# Extra-ingrediënten per type (Nederlandstalig)
EXTRAS = {
    "Diner": [
        "olijfolie",
        "chilivlokken",
        "peterselie",
        "champignons",
        "kappertjes",
        "citroen",
        "sesamolie",
    ],
    "Voorgerecht": [
        "room",
        "croutons",
        "tijm",
        "laurierblad",
        "zure room",
        "geroosterde pompoenpitten",
    ],
    "Lunch": [
        "gemengde sla",
        "avocado",
        "noten",
        "zaden",
        "vinaigrette",
        "croutons",
    ],
    "Ontbijt": [
        "ahornsiroop",
        "bessen",
        "yoghurt",
        "boter",
        "banaan",
        "granola",
    ],
    "Nagerecht": ["slagroom", "vanille", "poedersuiker", "noten", "karamel"],
    "Snack": ["paprika", "olijfolie", "pitabrood", "komkommer", "tomaat", "feta"],
    "Drank": ["citroen", "limoen", "mint", "siroop", "ijsblokjes"],
    "Overig": [
        "olijfolie",
        "kruiden",
        "peper",
        "zout",
        "citroen",
    ],
}

# Allowed Dutch categories for the application (matches form choices)
CATEGORIES = [
    "Voorgerecht",
    "Ontbijt",
    "Lunch",
    "Diner",
    "Nagerecht",
    "Snack",
    "Drank",
    "Overig",
]


def generate_title(use_adjective: bool = True) -> str:
    """Generate a recipe title optionally prefixed with an adjective."""
    base = random.choice(RECIPE_BASES)[0]
    if use_adjective:
        adj = random.choice(ADJECTIVES)
        return f"{adj} {base}"
    return base


def generate_ingredients(num_extra: int = 2, base_hint: str | None = None) -> List[str]:
    """Generate an ingredient list. If base_hint provided, prefer matching base."""
    # Choose a base entry that matches hint if given
    if base_hint:
        candidates = [b for b in RECIPE_BASES if base_hint.lower() in b[0].lower()]
        base = random.choice(candidates) if candidates else random.choice(RECIPE_BASES)
    else:
        base = random.choice(RECIPE_BASES)

    core = list(base[1])
    category = base[2]

    extras = EXTRAS.get(category, [])
    # Add a couple of extras, avoid duplicates
    picks = random.sample(extras, k=min(len(extras), num_extra)) if extras else []

    # Small chance to add a complementary item from other categories
    if random.random() < 0.2:
        other = random.choice(list(EXTRAS.values()))
        if other:
            picks += random.sample(other, k=1)

    # Normalize and deduplicate while preserving order
    items: List[str] = []
    for i in core + picks:
        if i not in items:
            items.append(i)

    return items


def generate_recipe(use_adjective: bool = True, num_extra: int = 2) -> Dict[str, Any]:
    """Return a dict with `title` and `ingredients` for a generated recipe."""
    # pick base so ingredients align with title
    base_entry = random.choice(RECIPE_BASES)
    base_title, base_core, category = base_entry
    title = f"{random.choice(ADJECTIVES)} {base_title}" if use_adjective else base_title
    ingredients = list(base_core)
    extras = EXTRAS.get(category, [])
    picks = random.sample(extras, k=min(len(extras), num_extra)) if extras else []

    # Small chance to make a vegetarian swap if core contains obvious meats
    meat_terms = (
        "pancetta",
        "rundergehakt",
        "kipfilet",
        "varkensschouder",
        "stoofvlees",
    )
    if any(mt in " ".join(ingredients) for mt in meat_terms) and random.random() < 0.15:
        ingredients = [
            "tofu"
            if x in ("pancetta", "rundergehakt", "kipfilet", "varkensschouder")
            else x
            for x in ingredients
        ]

    # ensure uniqueness and sensible ordering
    for p in picks:
        if p not in ingredients:
            ingredients.append(p)

    return {"title": title, "ingredients": ingredients, "category": category}


def generate_recipes(
    n: int = 10, use_adjective: bool = True, num_extra: int = 2
) -> List[Dict[str, Any]]:
    """Generate multiple recipes."""
    return [
        generate_recipe(use_adjective=use_adjective, num_extra=num_extra)
        for _ in range(n)
    ]
