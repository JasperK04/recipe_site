"""Realistic recipe title and ingredient generator.

Provides lists of adjectives, recipe bases and ingredient pools and
helper functions to generate plausible-sounding recipes.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

# Adjectives to prefix titles
ADJECTIVES = [
    "Spicy",
    "Creamy",
    "Herbed",
    "Smoky",
    "Tangy",
    "Citrus",
    "Garlic",
    "Honey-Glazed",
    "Crispy",
    "Slow-Cooked",
    "Roasted",
    "Grilled",
    "Fresh",
    "Zesty",
    "Warm",
    "Velvety",
    "Quick",
    "Easy",
    "One-Pot",
    "Vegan",
    "Vegetarian",
    "Gluten-Free",
    "Low-Carb",
    "Comfort",
    "Hearty",
    "Light",
    "Lemon",
    "Maple",
    "Caramelized",
    "Spiced",
    "Mediterranean",
    "Asian-Style",
]


# Recipe bases with a small canonical ingredient list and a type tag
RECIPE_BASES = [
    (
        "Pasta Carbonara",
        ["spaghetti", "eggs", "parmesan", "pancetta", "black pepper"],
        "pasta",
    ),
    (
        "Tomato Basil Soup",
        ["tomatoes", "basil", "onion", "garlic", "vegetable stock"],
        "soup",
    ),
    (
        "Chicken Stir-Fry",
        ["chicken breast", "soy sauce", "garlic", "ginger", "vegetable oil"],
        "stirfry",
    ),
    (
        "Chickpea Curry",
        ["chickpeas", "coconut milk", "curry powder", "onion", "tomato"],
        "curry",
    ),
    ("Greek Salad", ["cucumber", "tomato", "feta", "olive oil", "olives"], "salad"),
    (
        "Beef Stew",
        ["stewing beef", "carrots", "potatoes", "onion", "beef stock"],
        "stew",
    ),
    (
        "Vegetable Risotto",
        ["arborio rice", "parmesan", "white wine", "mushrooms", "vegetable stock"],
        "rice",
    ),
    ("Fish Tacos", ["white fish", "tortillas", "cabbage", "lime", "cilantro"], "taco"),
    (
        "Margherita Pizza",
        ["pizza dough", "mozzarella", "tomato sauce", "basil", "olive oil"],
        "pizza",
    ),
    ("Banana Bread", ["bananas", "flour", "butter", "sugar", "eggs"], "baked"),
    ("Oat Pancakes", ["oats", "milk", "egg", "baking powder", "vanilla"], "breakfast"),
    (
        "Quinoa Salad",
        ["quinoa", "lemon", "olive oil", "cucumber", "cherry tomatoes"],
        "salad",
    ),
    (
        "Lentil Soup",
        ["lentils", "carrot", "celery", "onion", "vegetable stock"],
        "soup",
    ),
    ("Shrimp Scampi", ["shrimp", "garlic", "butter", "lemon", "parsley"], "seafood"),
    ("Beef Tacos", ["ground beef", "tortillas", "lettuce", "cheddar", "salsa"], "taco"),
    (
        "Roast Chicken",
        ["whole chicken", "rosemary", "garlic", "lemon", "olive oil"],
        "roast",
    ),
    (
        "Miso Ramen",
        ["ramen noodles", "miso paste", "dashi", "scallions", "egg"],
        "noodle",
    ),
    (
        "Apple Crumble",
        ["apples", "oats", "butter", "brown sugar", "cinnamon"],
        "dessert",
    ),
    (
        "Tofu Stir-Fry",
        ["tofu", "soy sauce", "garlic", "broccoli", "sesame oil"],
        "stirfry",
    ),
    ("Hummus", ["chickpeas", "tahini", "lemon", "garlic", "olive oil"], "dip"),
]


# Additional pools keyed by type
EXTRAS = {
    "pasta": ["olive oil", "chili flakes", "parsley", "lemon zest", "mushrooms"],
    "soup": ["cream", "croutons", "thyme", "bay leaf", "sour cream"],
    "stirfry": ["bell pepper", "spring onion", "sesame seeds", "chili", "peanuts"],
    "curry": ["garam masala", "cilantro", "chili", "potato", "spinach"],
    "salad": ["mixed greens", "avocado", "nuts", "seeds", "vinegar"],
    "stew": ["red wine", "tomato paste", "bay leaf", "thyme", "peas"],
    "rice": ["peas", "lemon", "zucchini", "spinach", "chicken stock"],
    "taco": ["avocado", "sour cream", "pico de gallo", "cotija cheese", "jalapeno"],
    "pizza": ["pepperoni", "bell pepper", "onion", "olives", "oregano"],
    "baked": ["walnuts", "vanilla", "nutmeg", "chocolate chips", "lemon zest"],
    "breakfast": ["maple syrup", "berries", "yogurt", "butter", "banana"],
    "seafood": ["white wine", "butter", "garlic", "lemon", "capers"],
    "roast": ["potatoes", "carrots", "thyme", "butter", "garlic"],
    "noodle": ["nori", "sesame oil", "bok choy", "scallions", "mushrooms"],
    "dessert": ["whipped cream", "vanilla", "powdered sugar", "nuts", "butter"],
    "dip": ["paprika", "olive oil", "pita bread", "cucumber", "tomato"],
}


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
    typ = base[2]

    extras = EXTRAS.get(typ, [])
    # Add a couple of extras, avoid duplicates
    picks = random.sample(extras, k=min(len(extras), num_extra)) if extras else []

    # Small chance to add a complementary item from other pools
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
    base_title, base_core, typ = base_entry
    title = f"{random.choice(ADJECTIVES)} {base_title}" if use_adjective else base_title
    ingredients = list(base_core)
    extras = EXTRAS.get(typ, [])
    picks = random.sample(extras, k=min(len(extras), num_extra)) if extras else []
    # maybe swap one core with a vegetarian alternative
    if typ in ("pasta", "stirfry", "taco") and random.random() < 0.15:
        # replace meat with tofu or chickpeas
        ingredients = [
            "tofu" if x in ("pancetta", "ground beef", "chicken breast") else x
            for x in ingredients
        ]

    # ensure uniqueness and sensible ordering
    for p in picks:
        if p not in ingredients:
            ingredients.append(p)

    return {"title": title, "ingredients": ingredients, "type": typ}


def generate_recipes(
    n: int = 10, use_adjective: bool = True, num_extra: int = 2
) -> List[Dict[str, Any]]:
    """Generate multiple recipes."""
    return [
        generate_recipe(use_adjective=use_adjective, num_extra=num_extra)
        for _ in range(n)
    ]
