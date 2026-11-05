ERROR_PAGE_CONTENT = {
    400: ("Ongeldige aanvraag", "De aanvraag kon niet worden verwerkt."),
    403: ("Geen toegang", "Je hebt geen toestemming om deze pagina te bekijken."),
    404: ("Pagina niet gevonden", "De pagina die je zoekt bestaat niet of is verplaatst."),
    405: ("Actie niet beschikbaar", "Deze actie is niet beschikbaar op deze pagina."),
    429: ("Te veel aanvragen", "Er zijn te veel aanvragen achter elkaar gedaan. Probeer het later opnieuw."),
    500: ("Er ging iets mis", "Er is iets misgegaan. Probeer het opnieuw."),
}


def error_page_context(status_code: int, message: str | None = None) -> dict[str, object]:
    title, default_message = ERROR_PAGE_CONTENT.get(status_code, ERROR_PAGE_CONTENT[500])
    return {
        "error_code": status_code,
        "error_title": title,
        "error_message": message or default_message,
    }
