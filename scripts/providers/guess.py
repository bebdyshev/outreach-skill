"""Default provider: free pattern guessing + MX check."""
import email_guess


def enrich(company: str, domain: str, person: str, known: list[dict]) -> dict:
    first, last = email_guess.split_name(person)
    result = email_guess.guess(first, last, domain, known)
    return {
        "email": result["email"],
        "confidence": result["confidence"],
        "source": "guess",
        "candidates": result["candidates"],
    }
