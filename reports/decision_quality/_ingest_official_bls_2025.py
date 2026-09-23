"""One-off ingest of official BLS archive page text retrieved 2026-09-23.

Direct requests to bls.gov returned Akamai 403. Official archive HTML was
retrieved via the Cursor official-page gateway and stored as converted text.
Those 403 bodies remain as blocked-fetch evidence and are not overwritten.
"""

from __future__ import annotations

from pathlib import Path

from forex_bot.decision_quality.macro_first_print.store import (
    DEFAULT_ROOT,
    looks_like_official_release,
    official_text_name,
    raw_dir,
    write_raw_release,
)

AGENT = Path(r"C:\Users\Brian\.cursor\projects\c-Users-Brian-OneDrive-Desktop-Forext-Trading-Bot-1st\agent-tools")

# Official archive URL stem -> retrieved converted-text file.
CPI = {
    "2025-01-15": "9e83c02e-0b6a-4c02-9ced-0da808efeef5.txt",
    "2025-02-12": "8a02924e-9fe6-42a1-a5bf-8cd9f1c86bc2.txt",
    "2025-03-12": "d6842ea3-4694-4384-8642-d0a4fa34e8f1.txt",
    "2025-04-10": "70e1e86a-9758-46d5-808a-53115e872854.txt",
    "2025-05-13": "875b3326-8dae-4c4d-8c0a-46cdb5665b40.txt",
    "2025-06-11": "4d6c5608-c81b-4443-af4f-9ccfbcf43ea1.txt",
    "2025-07-15": "e2c6992a-54ef-4a7b-97e9-3b3e234123c9.txt",
    "2025-08-12": "22b65e36-3672-44cb-ab89-f1017382b4dd.txt",
    "2025-09-11": "c3b402c2-2ac5-4326-8d62-ee0cd7ea0db9.txt",
    "2025-10-24": "7a226c49-5ba0-44fa-bb5e-35d72b784ac4.txt",
    "2025-12-18": "476c3547-4001-472d-8513-8a2184a713c8.txt",
}
EMP = {
    "2025-01-10": "1fadb494-a317-453b-8d9d-e79d37953b22.txt",
    "2025-02-07": "b6afc724-ee7e-4ade-bb07-20474ee23fcf.txt",
    "2025-03-07": "bdb109bd-86b5-4f21-9812-20d9ccc3e5a6.txt",
    "2025-04-04": "8a087171-cf3e-40ca-b5b2-d6cfaf1f3616.txt",
    "2025-05-02": "18ec9e77-49fa-49cf-b3c3-67b2ce3ead5f.txt",
    "2025-06-06": "b5743007-a131-4965-a7e0-729e52cd7516.txt",
    "2025-07-03": "3a9e3769-2280-4908-9cfe-5eb69816dff5.txt",
    "2025-08-01": "6307625b-c6bc-4104-b44f-5bed5a9455b8.txt",
    "2025-09-05": "d2878acb-ec4d-4935-a0ac-42550acd4104.txt",
    "2025-11-20": "c7df1ce1-86b5-4885-8b82-ebe1d79e0d1f.txt",
    "2025-12-16": "81e8ecd3-2c0d-466c-99c6-a6387270fb54.txt",
}


def _url(kind: str, release: str) -> str:
    from forex_bot.decision_quality.macro_first_print.catalog import archive_url

    return archive_url(kind, release)


def ingest(mapping: dict[str, str], event_type: str) -> None:
    dest = raw_dir(DEFAULT_ROOT, event_type)
    for release, fname in mapping.items():
        src = AGENT / fname
        body = src.read_bytes()
        if not looks_like_official_release(body):
            raise SystemExit(f"not an official release: {fname}")
        stored = write_raw_release(
            dest_dir=dest,
            filename=official_text_name(event_type, release),
            body=body,
            source_url=_url(event_type, release),
            http_status=200,
            content_type="text/plain; converted-from-official-bls-html",
            publication_date=release,
            release_number=None,
            retrieved_at="2026-09-23T22:50:00Z",
        )
        print(f"{event_type} {release} -> {stored.body_path.name} reused={stored.reused}")


if __name__ == "__main__":
    ingest(CPI, "CPI")
    ingest(EMP, "EMPLOYMENT_SITUATION")
