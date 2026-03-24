"""
Recipe scrapers for importing from external sources.
"""

import re

import requests
from bs4 import BeautifulSoup

from app.models import KitchenMachine


def fetch_html(url):
    """Fetch HTML from a URL with appropriate headers."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def flatten_html_text(html: str) -> str:
    """Flatten HTML into a single text string with normalized whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove header/footer/nav/aside and common non-content tags
    for tag in soup.find_all(
        [
            "head",
            "header",
            "footer",
            "nav",
            "aside",
            "script",
            "style",
            "noscript",
            "next-route-announcer",
            "iframe",
            "button",
            "a",
            "form",
            "meta",
            "img",
            "svg",
            "video",
            "picture",
            "figure",
            "figcaption",
            "link",
        ]
    ):
        tag.decompose()

    # Also remove elements with header/footer classes or ids
    pattern_list = [
        "footer",
        "site-header",
        "site-footer",
        "related",
        "gerelateerd",
        "nutrition",
        "energy",
        "energie",
        "voedingswaarde",
        "rating",
        "score",
        "review",
        "image",
        "logo",
    ]
    pattern = r"(" + "|".join(pattern_list) + r")"
    for tag in soup.find_all(True):
        attrs = tag.attrs or {}
        class_attr = " ".join(attrs.get("class", [])) if attrs.get("class") else ""
        tag_id = attrs.get("id", "") or ""
        if re.search(pattern, class_attr, re.I):
            tag.decompose()
            continue
        if re.search(pattern, tag_id, re.I):  # type: ignore
            tag.decompose()

    # Collapse whitespace to single spaces
    blocks = []
    for elem in soup.find_all(["p", "span", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        text = elem.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if len(text) >= 1:
            blocks.append(text)

    seen = set()
    deduplicated = []

    for block in blocks:
        key = re.sub(r"\W+", "", block.lower())
        if key not in seen:
            seen.add(key)
            deduplicated.append(block)

    return " ".join(deduplicated)


def _normalize_qty(qty_raw: str):
    """Normalize quantities with fraction glyphs to float-compatible values."""
    if not qty_raw:
        return ""

    fraction_map = {
        "¼": 0.25,
        "½": 0.5,
        "¾": 0.75,
        "⅓": 1 / 3,
        "⅔": 2 / 3,
        "⅛": 0.125,
    }

    tokens = re.findall(r"(\d+(?:[.,]\d+)?)|([¼½¾⅓⅔⅛])", qty_raw)
    if not tokens:
        return qty_raw

    total = 0.0
    for num, frac in tokens:
        if num:
            total += float(num.replace(",", "."))
        elif frac:
            total += fraction_map.get(frac, 0)

    return total


def _find_list_by_class(soup, patterns, attr_patterns=None):
    """Find ul/ol elements whose class or attributes match regex patterns."""
    for list_elem in soup.find_all(["ul", "ol"]):
        class_attr = list_elem.get("class", [])
        if class_attr:
            class_str = (
                " ".join(class_attr)
                if isinstance(class_attr, list)
                else str(class_attr)
            )
            for pattern in patterns:
                if re.search(pattern, class_str, re.I):
                    return list_elem

        if attr_patterns:
            for attr_name, attr_val in list_elem.attrs.items():
                attr_val_str = (
                    " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val)
                )
                for pattern in attr_patterns:
                    if re.search(pattern, str(attr_name), re.I) or re.search(
                        pattern, attr_val_str, re.I
                    ):
                        return list_elem
    return None


def extract_recipe_from_html(html):
    """Extract recipe data directly from HTML elements."""
    soup = BeautifulSoup(html, "html.parser")

    # Define class/attribute patterns for ingredients and steps lists
    INGREDIENT_PATTERNS = [
        r"ingredient",
        r"recipe-ingredient",
        r"recipe_ingredient",
        r"ingredien",
        r"ing-list",
    ]

    STEP_PATTERNS = [
        r"step",
        r"instruction",
        r"preparation",
        r"direction",
        r"method",
        r"recipe-step",
        r"recipe_step",
    ]

    # Patterns for finding serving-related elements
    SERVING_ELEMENT_PATTERNS = [r"serving", r"yield", r"portion", r"recipe-yield"]

    # Patterns for extracting serving counts from text
    SERVING_TEXT_PATTERNS = [
        r"voor\s+(\d+)\s+personen",  # Dutch: "voor 4 personen"
        r"(\d+)\s*(?:serving|portion|personen|porties|people|pers\.?)",  # General patterns
        r"(\d+)\s+(?:porties|personen|servings?|portions?|people)",  # Alternative patterns
    ]

    # Pattern for description class matching
    DESCRIPTION_CLASS_PATTERN = r"intro|description"

    COOK_TIME_PATTERNS = [
        r"cook\s*time",
        r"cooking\s*time",
        r"bak\s*tijd",
        r"kooktijd",
    ]

    # Extract title
    title = None
    # Try h1 first
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    # Try data-testid
    if not title:
        title_elem = soup.find(attrs={"data-testid": "header-title"})
        if title_elem:
            title = title_elem.get_text(strip=True)

    if not title:
        raise ValueError("Recepttitel niet gevonden op de pagina.")

    # Extract description
    description = ""
    desc_elem = soup.find("p", attrs={"data-testid": "header-subtitle"})
    if not desc_elem:
        # Fallback: look for p with class containing intro or description
        desc_elem = soup.find("p", class_=re.compile(DESCRIPTION_CLASS_PATTERN, re.I))
    if desc_elem:
        description = desc_elem.get_text(strip=True)

    # Extract servings
    servings = None
    serving_elem = soup.find(attrs={"data-testid": "recipe-servings"})

    if not serving_elem:
        # Try to find element with servings/yield class or attribute patterns
        for elem in soup.find_all(["span", "div", "p", "li"]):
            class_attr = elem.get("class", [])
            if class_attr:
                class_str = (
                    " ".join(class_attr)
                    if isinstance(class_attr, list)
                    else str(class_attr)
                )
                if any(
                    re.search(pattern, class_str, re.I)
                    for pattern in SERVING_ELEMENT_PATTERNS
                ):
                    serving_elem = elem
                    break
            # Check attributes
            for attr_name in elem.attrs.keys():
                if any(
                    re.search(pattern, str(attr_name), re.I)
                    for pattern in SERVING_ELEMENT_PATTERNS
                ):
                    serving_elem = elem
                    break
            if serving_elem:
                break

    if serving_elem:
        # Extract number from element - use separator and strip to ensure nested elements are captured
        text = serving_elem.get_text(separator=" ", strip=True)
        # Try each pattern to extract serving count
        for pattern in SERVING_TEXT_PATTERNS:
            match = re.search(pattern, text, re.I)
            if match:
                servings = int(match.group(1))
                break

        # Fallback: just extract any number
        if not servings:
            match = re.search(r"(\d+)", text)
            if match:
                servings = int(match.group(1))

    if not servings:
        # Final fallback: search entire page text
        text_content = soup.get_text()
        for pattern in SERVING_TEXT_PATTERNS:
            match = re.search(pattern, text_content, re.I)
            if match:
                servings = int(match.group(1))
                break

    if servings and servings > 8:
        # Cap at 8 servings to avoid misinterpretation
        servings = None

    # Extract ingredients
    ingredients = []
    # Try AH-specific data-testid first
    ingredients_section = soup.find("ul", attrs={"data-testid": "ingredients"})

    # Try class/attribute-based matching
    if not ingredients_section:
        ingredients_section = _find_list_by_class(
            soup, INGREDIENT_PATTERNS, INGREDIENT_PATTERNS
        )

    # Fallback: look for section with ingredients heading
    if not ingredients_section:
        for heading in soup.find_all(["h2", "h3"]):
            if (
                "ingrediënten" in heading.get_text().lower()
                or "ingredients" in heading.get_text().lower()
            ):
                # Find the next ul or ol after this heading
                siblings = heading.find_next_siblings()
                for sibling in siblings:
                    if sibling.name in ["ul", "ol"]:
                        ingredients_section = sibling
                        break
                break

    if ingredients_section:
        for li in ingredients_section.find_all("li"):
            # Try to extract quantity from a separate span element first
            qty_span = li.find("span")
            qty_str = None

            if qty_span:
                qty_text = qty_span.get_text(strip=True)
                # Check if span contains a quantity (number with optional fractions)
                qty_match = re.match(r"^[\d,.¼½¾⅓⅔⅛]+", qty_text)
                if qty_match:
                    qty_str = qty_match.group(0)
                    # Remove the span from consideration when getting ingredient text
                    qty_span.decompose()

            # Flatten all text content from the li element
            ingredient_text = li.get_text(separator=" ", strip=True)
            if not ingredient_text:
                continue

            # If we already extracted qty from span, prepend it back for regex matching
            if qty_str:
                ingredient_text = f"{qty_str} {ingredient_text}"

            # Parse quantity, unit, and name from flattened ingredient text
            # Pattern: "123,5 g ingredient name" or "2 el zout" or "½ tl zout" or "1 limoen" or "0.5 rode peper"
            match = re.match(
                r"^([\d,.¼½¾⅓⅔⅛]+(?:\s*-\s*[\d,.¼½¾⅓⅔⅛]+)?)\s*(?:x\s+)?([a-z]+)?\s+(.+)$",
                ingredient_text,
                re.I,
            )

            if match:
                qty_str = match.group(1)
                unit = match.group(2)
                name = match.group(3).strip()

                # Remove everything within parentheses from ingredient name
                name = re.sub(r"\([^)]*\)", "", name).strip()

                # Map unit aliases
                unit_mapping = {
                    "gr": "g",
                    "gram": "g",
                    "grams": "g",
                    "kilogram": "kg",
                    "kilograms": "kg",
                    "liter": "l",
                    "liters": "l",
                    "milliliter": "ml",
                    "milliliters": "ml",
                    "tablespoon": "el",
                    "tablespoons": "el",
                    "eetlepel": "el",
                    "tbsp": "el",
                    "teaspoon": "tl",
                    "teaspoons": "tl",
                    "theelepel": "tl",
                    "tsp": "tl",
                    "pieces": "stuks",
                    "piece": "stuks",
                    "stuk": "stuks",
                }

                # If no unit is specified, default to "stuks"
                if not unit:
                    unit = "stuks"
                else:
                    # Apply unit mapping
                    unit = unit_mapping.get(unit.lower(), unit)

                try:
                    qty_val = _normalize_qty(qty_str.split("-")[0])
                    qty = float(qty_val) if qty_val != "" else ""
                    ingredients.append(
                        {
                            "name_": name,
                            "quantity": str(int(qty))
                            if isinstance(qty, float) and qty.is_integer()
                            else (qty if qty != "" else ""),
                            "measurement": unit,
                        }
                    )
                except Exception:
                    ingredients.append(
                        {
                            "name_": ingredient_text,
                            "quantity": "",
                            "measurement": unit,
                        }
                    )
            else:
                # No quantity found, default to 1 stuks
                name = ingredient_text
                # Remove everything within parentheses from ingredient name
                name = re.sub(r"\([^)]*\)", "", name).strip()
                ingredients.append(
                    {"name_": name, "quantity": "1", "measurement": "stuks"}
                )

    # Extract instructions/steps
    steps = []
    # Try AH-specific data-testid first
    instructions_section = soup.find("ol", attrs={"data-testid": "preparation-steps"})

    # Try class/attribute-based matching
    if not instructions_section:
        instructions_section = _find_list_by_class(soup, STEP_PATTERNS, STEP_PATTERNS)

    # Fallback: look for section with instructions heading
    if not instructions_section:
        for heading in soup.find_all(["h2", "h3"]):
            heading_text = heading.get_text().lower()
            if any(
                keyword in heading_text
                for keyword in [
                    "bereiding",
                    "instructies",
                    "instructions",
                    "steps",
                    "directions",
                    "method",
                ]
            ):
                siblings = heading.find_next_siblings()
                for sibling in siblings:
                    if sibling.name in ["ul", "ol"]:
                        instructions_section = sibling
                        break
                break

    if instructions_section:
        for li in instructions_section.find_all("li"):
            # Flatten all text content from the li element
            step_text = li.get_text(separator=" ", strip=True)
            # Remove leading step numbers (e.g., "1.", "2", "10.") to avoid interference with time extraction
            step_text = re.sub(r"^\d+\.?\s*", "", step_text)
            if step_text:
                steps.append(step_text)

    # Extract prep and cook times (in minutes)
    prep_time = None
    cook_time = None

    # Look for time elements with data-testid first
    prep_elem = soup.find(attrs={"data-testid": "header-prep-time"})
    if prep_elem:
        text = prep_elem.get_text(strip=True)
        match = re.search(r"(\d+)", text)
        if match:
            prep_time = int(match.group(1))

    cook_elem = soup.find(attrs={"data-testid": "header-time"})
    if cook_elem:
        text = cook_elem.get_text(strip=True)
        match = re.search(r"(\d+)", text)
        if match:
            cook_time = int(match.group(1))

    # Fallback: search for cook time by class or attribute patterns
    if not cook_time:
        # Try div with specific class like "bereidingstijd" or "kooktijd"
        cook_div = soup.find("div", class_=re.compile(r"kooktijd|cook|cooking", re.I))
        if cook_div:
            text = cook_div.get_text(strip=True)
            match = re.search(r"(\d+)", text)
            if match:
                cook_time = int(match.group(1))

        # Try finding by span siblings (label + time pattern)
        if not cook_time:
            for span in soup.find_all("span"):
                if any(
                    re.search(pattern, span.get_text(), re.I)
                    for pattern in COOK_TIME_PATTERNS
                ):
                    # Found a label span, look for sibling with time
                    next_sibling = span.find_next_sibling()
                    if next_sibling:
                        text = next_sibling.get_text(strip=True)
                        match = re.search(r"(\d+)", text)
                        if match and match.group(1) != (prep_time and str(prep_time)):
                            # Avoid selecting the same value as prep time
                            cook_time = int(match.group(1))
                            break

    # Try to infer oven/airfryer time
    oven_time = None
    # Check page elements first (classes/labels likely indicating oven/airfryer time)
    oven_div = soup.find(
        "div", class_=re.compile(r"oven|airfryer|baktijd|bak\s*tijd", re.I)
    )
    if oven_div:
        text = oven_div.get_text(strip=True)
        m = re.search(r"(\d+)\s*(?:min|minute|minuten)", text, re.I)
        if m:
            oven_time = int(m.group(1))
        else:
            m = re.search(r"(\d+)\s*(?:uur|hours?)", text, re.I)
            if m:
                oven_time = int(m.group(1)) * 60

    # If not found, scan instructions for oven/airfryer mentions + duration
    if not oven_time and steps:
        for step in steps:
            lower = step.lower()
            if re.search(r"oven|airfryer|hetelucht|bak", lower):
                m = re.search(r"(\d+)\s*(?:min|minute|minuten)", step, re.I)
                if m:
                    oven_time = int(m.group(1))
                    break
                m = re.search(r"(\d+)\s*(?:uur|hours?)", step, re.I)
                if m:
                    oven_time = int(m.group(1)) * 60
                    break

    # Determine category from breadcrumb or other meta info
    category = "Overig"
    breadcrumb = soup.find(attrs={"data-testid": "breadcrumb"})
    if breadcrumb:
        category_map = {
            "voorgerecht": "Voorgerecht",
            "ontbijt": "Ontbijt",
            "lunch": "Lunch",
            "hoofdgerecht": "Diner",
            "diner": "Diner",
            "nagerecht": "Nagerecht",
            "dessert": "Nagerecht",
            "snack": "Snack",
            "tussendoortje": "Snack",
            "drank": "Drank",
        }
        breadcrumb_text = breadcrumb.get_text().lower()
        for key, val in category_map.items():
            if key in breadcrumb_text:
                category = val
                break

    return {
        "title": title,
        "description": description,
        "servings": servings,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "oven_time": oven_time,
        "category": category,
        "ingredients": ingredients,
        "steps": steps,
    }


def infer_cookware(steps):
    """Infer required cookware from instruction steps."""
    text = " ".join(steps).lower()
    tools = set()

    # Map Dutch keywords to machine names (matching database names)
    rules = {
        "Oven": ["oven", "bakoven"],
        "Magnetron": ["magnetron", "microgolf"],
        "Airfryer": ["airfryer", "hetelucht"],
        "Blender": ["blender", "pureer", "mixen"],
        "Mixer": ["mixer", "garde", "kloppen"],
        "Slowcooker": ["slowcooker", "slow cooker"],
        "Grillplaat": ["grill", "bakplaat"],
        "Keukenmachine": ["keukenmachine", "foodprocessor"],
        "Staafmixer": ["staafmixer", "staaf mixer"],
        "Deegmachine": ["deegmachine", "deeg mixer", "kneden"],
        "Frituurpan": ["frituur", "frituren", "friteuse"],
        "Panini ijzer": [
            "panini",
            "tosti",
            "contactgrill",
            "grill",
        ],
        "Sous-vide": ["sous-vide", "sous vide"],
        "kookplaat": ["kookplaat", "fornuis", "koken op", "sudderen", "roerbak"],
    }

    for tool, keywords in rules.items():
        # Use word-boundary regex to ensure full-word matches
        for k in keywords:
            pattern = r"\b" + re.escape(k).replace(r"\ ", r"\s+") + r"\b"
            if re.search(pattern, text):
                tools.add(tool)
                break

    return sorted(tools)


def scrape_ah_recipe(url):
    """
    Scrape an Albert Heijn recipe and return structured data.

    Returns a dict with keys matching the Recipe model structure.
    """
    html = fetch_html(url)
    recipe_data = extract_recipe_from_html(html)

    # Infer cookware and map to database IDs
    cookware_names = infer_cookware(recipe_data["steps"])
    machine_ids = []
    if cookware_names:
        machines = KitchenMachine.query.filter(
            KitchenMachine.name.in_(cookware_names)
        ).all()
        machine_ids = [m.id for m in machines]

    return {
        "title": recipe_data["title"],
        "description": recipe_data["description"],
        "servings": recipe_data["servings"],
        "prep_time": recipe_data["prep_time"],
        "cook_time": recipe_data["cook_time"],
        "oven_time": recipe_data.get("oven_time"),
        "category": recipe_data["category"],
        "ingredients": recipe_data["ingredients"],
        "instructions": recipe_data["steps"],
        "required_machines": machine_ids,
        "source_url": url,
    }
