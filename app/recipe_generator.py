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
        "Hoofdgerecht",
    ),
    (
        "Tomaat-basilicumsoep",
        ["tomaten", "basilicum", "ui", "knoflook", "groentebouillon"],
        "Voorgerecht",
    ),
    (
        "Kip roerbak",
        ["kipfilet", "sojasaus", "knoflook", "gember", "groente-olie"],
        "Hoofdgerecht",
    ),
    (
        "Kikkererwtencurry",
        ["kikkererwten", "kokosmelk", "kerriepoeder", "ui", "tomaat"],
        "Hoofdgerecht",
    ),
    (
        "Griekse salade",
        ["komkommer", "tomaat", "feta", "olijfolie", "olijven"],
        "Lunch",
    ),
    (
        "Runderstoofpot",
        ["stoofvlees", "wortels", "aardappelen", "ui", "runderbouillon"],
        "Hoofdgerecht",
    ),
    (
        "Groenterisotto",
        ["arborio rijst", "parmezaan", "witte wijn", "champignons", "groentebouillon"],
        "Hoofdgerecht",
    ),
    (
        "Vistaco's",
        ["witte vis", "tortilla's", "kool", "limoen", "koriander"],
        "Hoofdgerecht",
    ),
    (
        "Pizza Margherita",
        ["pizzadeeg", "mozzarella", "tomatensaus", "basilicum", "olijfolie"],
        "Hoofdgerecht",
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
        "Hoofdgerecht",
    ),
    (
        "Rundertaco's",
        ["rundergehakt", "tortilla's", "sla", "cheddar", "salsa"],
        "Hoofdgerecht",
    ),
    (
        "Geroosterde kip",
        ["hele kip", "rozemarijn", "knoflook", "citroen", "olijfolie"],
        "Hoofdgerecht",
    ),
    (
        "Miso ramen",
        ["ramen noedels", "misopasta", "dashi", "lente-ui", "ei"],
        "Hoofdgerecht",
    ),
    (
        "Appelcrumble",
        ["appels", "haver", "boter", "bruine suiker", "kaneel"],
        "Nagerecht",
    ),
    (
        "Tofu roerbak",
        ["tofu", "sojasaus", "knoflook", "broccoli", "sesamolie"],
        "Hoofdgerecht",
    ),
    ("Hummus", ["kikkererwten", "tahini", "citroen", "knoflook", "olijfolie"], "Snack"),
]

# Extra voorbeelden en variaties voor meer combinaties
RECIPE_BASES += [
    (
        "Spinazie-feta frittata",
        ["eieren", "spinazie", "feta", "ui", "olijfolie"],
        "Ontbijt",
    ),
    (
        "Butternut pompoensoep",
        ["butternut pompoen", "ui", "knoflook", "groentebouillon", "room"],
        "Soep",
    ),
    (
        "Pulled pork sandwich",
        ["varkensschouder", "barbecuesaus", "broodjes", "coleslaw", "augurk"],
        "Hoofdgerecht",
    ),
    ("Shakshuka", ["eieren", "tomaat", "ui", "paprika", "komijn"], "Ontbijt"),
    ("Ceviche", ["witte vis", "limoensap", "ui", "koriander", "peper"], "Hoofdgerecht"),
    (
        "Thaise groene curry",
        ["kip", "groene currypasta", "kokosmelk", "basilicum", "aubergine"],
        "Hoofdgerecht",
    ),
    (
        "Boeuf Bourguignon",
        ["runderstoofvlees", "rode wijn", "wortel", "ui", "champignons"],
        "Hoofdgerecht",
    ),
    (
        "Courgettekoekjes",
        ["courgette", "ei", "bloem", "parmezaan", "knoflook"],
        "Snack",
    ),
    (
        "Aubergine Parmigiana",
        ["aubergine", "tomatensaus", "mozzarella", "parmezaan", "basilicum"],
        "Hoofdgerecht",
    ),
    (
        "Dal van linzen",
        ["linzen", "uien", "komijn", "kurkuma", "kokosmelk"],
        "Hoofdgerecht",
    ),
    (
        "Paneer Tikka",
        ["paneer", "yoghurt", "tikka masala", "paprika", "limoen"],
        "Hoofdgerecht",
    ),
    (
        "Sushi bowl",
        ["sushi rijst", "zalm", "avocado", "komkommer", "sojasaus"],
        "Hoofdgerecht",
    ),
    (
        "BBQ spareribs",
        ["varkensribben", "barbecuesaus", "kool", "mais", "aardappels"],
        "Hoofdgerecht",
    ),
    ("Falafel wrap", ["kikkererwten", "kruiden", "salade", "tahini", "wrap"], "Lunch"),
    (
        "Zoete aardappel frietjes",
        ["zoete aardappel", "olijfolie", "paprikapoeder", "zout", "peper"],
        "Snack",
    ),
    (
        "Yoghurt parfait",
        ["Griekse yoghurt", "muesli", "bessen", "honing", "noten"],
        "Ontbijt",
    ),
    (
        "Paddenstoelenstroganoff",
        ["paddenstoelen", "zure room", "ui", "paprikapoeder", "pasta"],
        "Hoofdgerecht",
    ),
    (
        "Caesar salade met kip",
        ["kropsla", "kip", "croutons", "Parmezaan", "Caesar dressing"],
        "Lunch",
    ),
    (
        "Poke bowl",
        ["rijst", "tonijn", "sojasaus", "zeewier", "edamame"],
        "Hoofdgerecht",
    ),
    (
        "Gebakken zalm",
        ["zalmfilet", "citroen", "dille", "boter", "olijfolie"],
        "Hoofdgerecht",
    ),
    ("Scones", ["bloem", "boter", "melk", "bakpoeder", "suiker"], "Hoofdgerecht"),
    ("Crêpes", ["bloem", "melk", "eieren", "boter", "suiker"], "Ontbijt"),
    (
        "Gnocchi met tomatensaus",
        ["gnocchi", "tomatensaus", "parmezaan", "basilicum", "olijfolie"],
        "Hoofdgerecht",
    ),
    (
        "Polenta met paddenstoelen",
        ["polenta", "paddenstoelen", "Parmezaan", "boter", "tijm"],
        "Hoofdgerecht",
    ),
    (
        "Ratatouille",
        ["aubergine", "courgette", "tomaat", "paprika", "ui"],
        "Hoofdgerecht",
    ),
    (
        "Chili con carne",
        ["rundergehakt", "bonen", "tomaat", "chili", "ui"],
        "Hoofdgerecht",
    ),
    (
        "Geroosterde pompoen salade",
        ["pompoen", "rucola", "feta", "walnoten", "vinaigrette"],
        "Voorgerecht",
    ),
    ("Shiitake miso soep", ["shiitake", "miso", "tofu", "dashi", "lente-ui"], "Soep"),
]


# Extra-ingrediënten per type (Nederlandstalig)
EXTRAS = {
    "Hoofdgerecht": [
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
    "Hoofdgerecht",
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
