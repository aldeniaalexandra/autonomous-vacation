import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from tabulate import tabulate


EXCHANGE_API = "https://api.exchangerate.host/latest"
RESTCOUNTRIES_API = "https://restcountries.com/v3.1/name/{country}?fields=name,currencies"


class RateLimitError(Exception):
    pass


def format_currency(amount: float) -> str:
    return f"{amount:,.2f}"


def format_duration(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_currency_code(code: str) -> str:
    return code.strip().upper()


def validate_amount(value: str) -> float:
    try:
        amt = float(value.strip())
        if amt < 0:
            raise ValueError("Amount cannot be negative.")
        return amt
    except ValueError:
        raise ValueError("Invalid amount. Please enter a valid number (e.g., 125000.50).")


def resolve_currency_from_country(country_name: str, timeout: int = 10) -> Tuple[str, str]:
    """Resolve currency code and name from a given country using RestCountries API."""
    try:
        resp = requests.get(RESTCOUNTRIES_API.format(country=country_name), timeout=timeout)
    except requests.RequestException as e:
        raise ConnectionError(f"Network error while resolving country currency: {e}")

    if resp.status_code == 429:
        raise RateLimitError("Rate limit reached when calling RestCountries API. Try again later.")
    if resp.status_code >= 400:
        raise ValueError(f"Error resolving country '{country_name}': HTTP {resp.status_code}")

    data = resp.json()
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"Country '{country_name}' not found.")
    entry = data[0]
    currencies = entry.get("currencies") or {}
    if not currencies:
        raise ValueError(f"No currency information for '{country_name}'.")

    # Pick the first currency
    code = next(iter(currencies.keys()))
    name = currencies[code].get("name", "Unknown")
    return code, name


def fetch_exchange_rates(base: str, symbols: List[str], timeout: int = 12) -> Dict[str, float]:
    """Fetch latest exchange rates for given symbols with a base currency."""
    params = {"base": base, "symbols": ",".join(symbols)}
    try:
        resp = requests.get(EXCHANGE_API, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise ConnectionError(f"Network error while fetching exchange rates: {e}")

    if resp.status_code == 429:
        raise RateLimitError("Rate limit reached when calling exchange rate API. Try again later.")
    if resp.status_code >= 400:
        raise ValueError(f"Exchange rate API returned HTTP {resp.status_code}")

    payload = resp.json()
    rates = payload.get("rates")
    if not isinstance(rates, dict) or not rates:
        raise ValueError("Invalid response: no 'rates' found.")

    # Ensure all requested symbols are present
    missing = [s for s in symbols if s not in rates]
    if missing:
        raise ValueError(f"Missing rates for symbols: {', '.join(missing)}. Check currency codes.")
    return rates


def build_markdown_report(
    start_time: datetime,
    end_time: datetime,
    base_currency: str,
    base_amount: float,
    conversions: List[Tuple[str, str, float, float]],
    output_path: Optional[str] = None,
) -> str:
    """Build a Markdown report and optionally save it to disk."""
    duration = end_time - start_time

    headers = ["Currency", "Currency Name", f"Rate (1 {base_currency})", f"Converted Amount"]
    rows = [
        [code, name, f"{rate:.6f}", f"{format_currency(converted)}"]
        for (code, name, rate, converted) in conversions
    ]
    table_md = tabulate(rows, headers, tablefmt="github")

    meta_md = "\n".join([
        f"# Currency Conversion Report",
        "",
        f"**Start Time:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**End Time:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {format_duration(duration)}",
        "",
        f"**Base Amount:** {format_currency(base_amount)} {base_currency}",
        "",
        table_md,
        "",
    ])
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(meta_md)
    return meta_md


def main():
    print("=== Currency Conversion Program (Live Rates) ===")
    try:
        amount_str = input("Enter base amount (e.g., 125000.50): ").strip()
        base_amount = validate_amount(amount_str)

        base_currency = normalize_currency_code(input("Enter base currency code (e.g., USD, JPY): ").strip())
        if len(base_currency) != 3:
            raise ValueError("Base currency code must be 3 letters (e.g., USD, EUR, JPY).")

        mode = input("Do you want to choose user country? (y/n): ").strip().lower()
        target_currency_code = ""
        target_currency_name = ""
        extra_codes: List[str] = []

        if mode == "y":
            country_name = input("Enter user country name (e.g., Indonesia): ").strip()
            target_currency_code, target_currency_name = resolve_currency_from_country(country_name)
            print(f"Country '{country_name}' -> User currency: {target_currency_code} ({target_currency_name})")
        else:
            target_currency_code = normalize_currency_code(input("Enter target currency code (e.g., IDR): ").strip())
            if len(target_currency_code) != 3:
                raise ValueError("Target currency code must be 3 letters.")
            target_currency_name = target_currency_code  # placeholder; name not provided by the exchange API

        extra_str = input("Additional currencies (optional, comma-separated, e.g., EUR,GBP,JPY): ").strip()
        if extra_str:
            extra_codes = [normalize_currency_code(x) for x in extra_str.split(",") if x.strip()]
            for c in extra_codes:
                if len(c) != 3:
                    raise ValueError(f"Invalid currency code: {c}")

        # Prepare symbols list for API call
        symbols = [target_currency_code] + [c for c in extra_codes if c != target_currency_code]
        start_time = datetime.now()

        rates = fetch_exchange_rates(base_currency, symbols)

        # Build conversions list: (code, name, rate, converted_amount)
        conversions: List[Tuple[str, str, float, float]] = []
        for code in symbols:
            rate = float(rates[code])
            converted = base_amount * rate
            name = target_currency_name if code == target_currency_code else code
            conversions.append((code, name, rate, converted))

        end_time = datetime.now()

        # Build Markdown and save to output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), "output")
        output_path = os.path.join(output_dir, f"currency_conversion_{timestamp}.md")
        markdown = build_markdown_report(
            start_time=start_time,
            end_time=end_time,
            base_currency=base_currency,
            base_amount=base_amount,
            conversions=conversions,
            output_path=output_path,
        )

        print("\n=== Markdown Report ===\n")
        print(markdown)
        print(f"\nReport saved to: {output_path}")

    except RateLimitError as e:
        print(f"[Rate Limit] {e}")
        print("Please try again in a few minutes.")
        sys.exit(1)
    except ConnectionError as e:
        print(f"[Connection] {e}")
        print("Check your internet connection and try again.")
        sys.exit(1)
    except ValueError as e:
        print(f"[Input/API] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[Unexpected Error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()