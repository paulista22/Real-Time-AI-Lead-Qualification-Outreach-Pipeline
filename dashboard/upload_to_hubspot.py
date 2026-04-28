"""
upload_to_hubspot.py

Uploads contacts and call activities from a CSV into HubSpot.

Input CSV expected columns:
- name
- email
- phone_number
- country_region
- state
- agent
- call_outcome
- conversation_notes

Behavior:
1) Upsert contact by email.
2) Create call activity using conversation notes and call outcome.
3) Associate the call with the contact.

Usage examples (PowerShell):
  $env:HUBSPOT_ACCESS_TOKEN="your_token_here"
    python upload_to_hubspot.py --csv leads_export.csv --dry-run --limit 20
    python upload_to_hubspot.py --csv leads_export.csv --limit 100
    python upload_to_hubspot.py --csv leads_export.csv
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import requests


BASE_URL = "https://api.hubapi.com"
REQUIRED_COLUMNS = [
    "name",
    "email",
    "phone_number",
    "country_region",
    "state",
    "agent",
    "call_outcome",
    "conversation_notes",
]

REQUIRED_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.calls.write",
    "crm.objects.owners.read",
]


class HubSpotClient:
    def __init__(self, token: str, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        url = f"{BASE_URL}{path}"
        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            json=json,
            params=params,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")

        if not response.text:
            return {}

        return response.json()

    def get_token_metadata(self, token: str) -> dict:
        # HubSpot exposes token scopes via this endpoint.
        url = f"{BASE_URL}/oauth/v1/access-tokens/{token}"
        response = requests.get(url, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(
                f"GET /oauth/v1/access-tokens/<token> -> {response.status_code}: {response.text}"
            )
        return response.json()


def normalize(value: str) -> str:
    if value is None:
        return ""
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def split_name(full_name: str) -> Tuple[str, str]:
    parts = str(full_name).strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def get_owner_map(client: HubSpotClient) -> Dict[str, str]:
    owner_map: Dict[str, str] = {}
    after = None

    while True:
        params = {"limit": 200, "archived": "false"}
        if after:
            params["after"] = after

        data = client.request("GET", "/crm/v3/owners/", params=params)

        for owner in data.get("results", []):
            full_name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip()
            if full_name:
                owner_map[normalize(full_name)] = str(owner["id"])

            email = owner.get("email")
            if email:
                owner_map[normalize(email)] = str(owner["id"])

        next_after = data.get("paging", {}).get("next", {}).get("after")
        if not next_after:
            break
        after = next_after

    return owner_map


def get_disposition_map(client: HubSpotClient) -> Dict[str, str]:
    data = client.request("GET", "/crm/v3/properties/calls/hs_call_disposition")
    disposition_map: Dict[str, str] = {}

    for option in data.get("options", []):
        label = option.get("label", "")
        value = option.get("value", "")
        if label and value:
            disposition_map[normalize(label)] = value

    return disposition_map


def resolve_disposition(outcome_label: str, disposition_map: Dict[str, str]) -> Optional[str]:
    direct_key = normalize(outcome_label)
    if direct_key in disposition_map:
        return disposition_map[direct_key]

    synonyms = {
        "connected": ["connected"],
        "leftlivemessage": ["leftlivemessage", "livemessage"],
        "leftvoicemail": ["leftvoicemail", "voicemail", "leftvoicemessage"],
        "noanswer": ["noanswer", "noresponse"],
        "wrongnumber": ["wrongnumber"],
    }

    for target, aliases in synonyms.items():
        if direct_key in aliases:
            for existing_key, internal_value in disposition_map.items():
                if target in existing_key:
                    return internal_value

    return None


def find_contact_id_by_email(client: HubSpotClient, email: str) -> Optional[str]:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }
                ]
            }
        ],
        "properties": ["email"],
        "limit": 1,
    }

    result = client.request("POST", "/crm/v3/objects/contacts/search", json=payload)
    matches = result.get("results", [])
    if not matches:
        return None

    return str(matches[0]["id"])


def upsert_contact(
    client: HubSpotClient,
    row: pd.Series,
    owner_id: Optional[str],
    dry_run: bool,
) -> Tuple[str, str]:
    first_name, last_name = split_name(row["name"])

    properties = {
        "email": str(row["email"]),
        "firstname": first_name,
        "lastname": last_name,
        "phone": str(row.get("phone_number", "")),
        "country": str(row.get("country_region", "")),
        "state": str(row.get("state", "")),
    }

    if owner_id:
        properties["hubspot_owner_id"] = owner_id

    existing_id = find_contact_id_by_email(client, str(row["email"]))

    if existing_id:
        if not dry_run:
            client.request("PATCH", f"/crm/v3/objects/contacts/{existing_id}", json={"properties": properties})
        return existing_id, "updated"

    if dry_run:
        return "dry-contact-id", "created"

    created = client.request("POST", "/crm/v3/objects/contacts", json={"properties": properties})
    return str(created["id"]), "created"


def create_call(
    client: HubSpotClient,
    row: pd.Series,
    owner_id: Optional[str],
    disposition_value: Optional[str],
    call_datetime: datetime,
    dry_run: bool,
) -> str:
    properties = {
        "hs_timestamp": str(int(call_datetime.timestamp() * 1000)),
        "hs_call_title": f"Call with {row['name']}",
        "hs_call_body": str(row.get("conversation_notes", "")),
    }

    if owner_id:
        properties["hubspot_owner_id"] = owner_id

    if disposition_value:
        properties["hs_call_disposition"] = disposition_value

    if dry_run:
        return "dry-call-id"

    created = client.request("POST", "/crm/v3/objects/calls", json={"properties": properties})
    return str(created["id"])


def associate_call_to_contact(client: HubSpotClient, call_id: str, contact_id: str, dry_run: bool) -> None:
    if dry_run:
        return
    client.request("PUT", f"/crm/v4/objects/calls/{call_id}/associations/default/contacts/{contact_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload contacts and calls from CSV to HubSpot")
    parser.add_argument("--csv", default="leads_export.csv", help="Path to source CSV")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of rows to upload (0 means all rows)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and simulate upload without writing to HubSpot",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=80,
        help="Delay between rows in milliseconds to reduce rate-limit risk",
    )
    return parser.parse_args()


def validate_required_scopes(client: HubSpotClient, token: str) -> None:
    metadata = client.get_token_metadata(token)
    granted_scopes = set(metadata.get("scopes", []))
    missing = [scope for scope in REQUIRED_SCOPES if scope not in granted_scopes]

    if missing:
        print("\nERROR: Missing required HubSpot scopes for this script.")
        print("Required scopes missing:")
        for scope in missing:
            print(f"  - {scope}")
        print("\nHow to fix:")
        print("1) HubSpot -> Settings -> Integrations -> Private Apps -> your app")
        print("2) Add missing scopes listed above")
        print("3) Reinstall/update app and copy the NEW access token")
        print("4) Set it again in PowerShell:")
        print('   $env:HUBSPOT_ACCESS_TOKEN="NEW_TOKEN"')
        print("5) Re-run the script")
        raise SystemExit(2)


def main() -> None:
    args = parse_args()

    token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise ValueError("Missing HUBSPOT_ACCESS_TOKEN environment variable")

    df = pd.read_csv(args.csv)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required CSV columns: {missing_cols}")

    if args.limit < 0:
        raise ValueError("--limit must be >= 0")

    if args.limit > 0:
        df = df.head(args.limit)

    client = HubSpotClient(token=token)
    validate_required_scopes(client, token)
    owner_map = get_owner_map(client)
    disposition_map = get_disposition_map(client)

    created_contacts = 0
    updated_contacts = 0
    created_calls = 0
    errors = 0

    # Assign timestamps to look like sequential calls from the previous day.
    base_dt = datetime.now() - timedelta(days=1)

    print(f"Rows to process: {len(df)}")
    print(f"Dry run: {args.dry_run}")

    for idx, row in df.iterrows():
        try:
            owner_name = str(row.get("agent", "")).strip()
            owner_id = owner_map.get(normalize(owner_name))

            contact_id, contact_action = upsert_contact(
                client=client,
                row=row,
                owner_id=owner_id,
                dry_run=args.dry_run,
            )

            if contact_action == "created":
                created_contacts += 1
            else:
                updated_contacts += 1

            disposition_value = resolve_disposition(str(row.get("call_outcome", "")), disposition_map)
            call_dt = base_dt + timedelta(minutes=idx * 2)

            call_id = create_call(
                client=client,
                row=row,
                owner_id=owner_id,
                disposition_value=disposition_value,
                call_datetime=call_dt,
                dry_run=args.dry_run,
            )

            associate_call_to_contact(
                client=client,
                call_id=call_id,
                contact_id=contact_id,
                dry_run=args.dry_run,
            )

            created_calls += 1

            if idx % 50 == 0:
                print(f"Processed {idx + 1}/{len(df)}")

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000)

        except Exception as exc:
            errors += 1
            print(f"[Row {idx + 1}] ERROR: {exc}")
            if "MISSING_SCOPES" in str(exc):
                print("Stopping early because token is missing required scopes.")
                break

    print("\n---- FINISHED ----")
    print(f"Contacts created: {created_contacts}")
    print(f"Contacts updated: {updated_contacts}")
    print(f"Calls created: {created_calls}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
