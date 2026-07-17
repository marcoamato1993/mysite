import json
import requests
import time
import re
from datetime import datetime, timezone

ORCID = "0000-0003-3764-3889"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Marco Amato Publication Updater (marco.amato@fsv.cvut.cz)"
}


def get(data, *keys):
    for k in keys:
        if not isinstance(data, dict):
            return ""
        data = data.get(k)
        if data is None:
            return ""
    return data


# ---------------------------------------------------------
# ORCID
# ---------------------------------------------------------

works = requests.get(
    f"https://pub.orcid.org/v3.0/{ORCID}/works",
    headers=HEADERS
).json()["group"]

publications = []

# ---------------------------------------------------------
# LOOP
# ---------------------------------------------------------

for group in works:

    put = group["work-summary"][0]["put-code"]

    work = requests.get(
        f"https://pub.orcid.org/v3.0/{ORCID}/work/{put}",
        headers=HEADERS
    ).json()

    # -----------------------------------------------------
    # DOI
    # -----------------------------------------------------

    doi = ""

    for ext in work.get("external-ids", {}).get("external-id", []):

        if ext["external-id-type"].lower() == "doi":

            doi = ext["external-id-value"]

            break

    # -----------------------------------------------------
    # Se manca DOI
    # -----------------------------------------------------

    if doi == "":

        publications.append({

            "id": "",
            "type": work.get("type", ""),
            "title": get(work, "title", "title", "value"),
            "authors": "",
            "journal": get(work, "journal-title", "value"),
            "book_title": "",
            "series": "",
            "editors": "",
            "year": get(work, "publication-date", "year", "value"),
            "month": get(work, "publication-date", "month", "value"),
            "day": get(work, "publication-date", "day", "value"),
            "volume": "",
            "issue": "",
            "pages": "",
            "publisher": "",
            "doi": "",
            "url": ""
        })

        continue

    # -----------------------------------------------------
    # Crossref
    # -----------------------------------------------------

    r = requests.get(
        f"https://api.crossref.org/works/{doi}",
        headers=HEADERS
    )

    if r.status_code != 200:

        print("Errore Crossref:", doi)

        continue

    cross = r.json()["message"]

    pub_type = work.get("type", "")

    # -----------------------------------------------------
    # Authors
    # -----------------------------------------------------

    author_names = []

    for a in cross.get("author", []):

        given = a.get("given", "")
        family = a.get("family", "")

        initials = " ".join(n[0] + "." for n in given.split())

        author_names.append(f"{family}, {initials}")

    if len(author_names) == 0:
        authors = ""

    elif len(author_names) == 1:
        authors = author_names[0]

    elif len(author_names) == 2:
        authors = " & ".join(author_names)

    else:
        authors = ", ".join(author_names[:-1]) + " & " + author_names[-1]

    # -----------------------------------------------------
    # Editors
    # -----------------------------------------------------

    editor_names = []

    for e in cross.get("editor", []):

        given = e.get("given", "")
        family = e.get("family", "")

        initials = " ".join(n[0] + "." for n in given.split())

        editor_names.append(f"{family}, {initials}")

    if len(editor_names) == 0:
        editors = ""

    elif len(editor_names) == 1:
        editors = editor_names[0]

    elif len(editor_names) == 2:
        editors = " & ".join(editor_names)

    else:
        editors = ", ".join(editor_names[:-1]) + " & " + editor_names[-1]

    # -----------------------------------------------------
    # Date
    # -----------------------------------------------------

    year = ""
    month = ""
    day = ""

    if "published-print" in cross:

        parts = cross["published-print"]["date-parts"][0]

    elif "published-online" in cross:

        parts = cross["published-online"]["date-parts"][0]

    else:

        parts = []

    if len(parts) > 0:
        year = str(parts[0])

    if len(parts) > 1:
        month = str(parts[1])

    if len(parts) > 2:
        day = str(parts[2])

    # -----------------------------------------------------
    # Titles
    # -----------------------------------------------------

    title = cross.get("title", [""])[0]

    journal = ""
    book_title = ""
    book_subtitle = ""
    series = ""

    container = cross.get("container-title", [])

    if pub_type == "book-chapter":

        # Crossref del capitolo
        if len(container) > 0:
            series = container[0]          # Collana

        if len(container) > 1:
            book_title = container[1]      # Titolo del libro

        # -------------------------------------------------
        # Recupera il sottotitolo del libro tramite ISBN
        # -------------------------------------------------

        isbn_list = cross.get("ISBN", [])

        if isbn_list:

            isbn = isbn_list[-1]

            r_book = requests.get(
                f"https://api.crossref.org/works?filter=isbn:{isbn}",
                headers=HEADERS
            )

            if r_book.status_code == 200:

                items = r_book.json()["message"].get("items", [])

                # Cerca il record del libro, non dei capitoli
                for item in items:

                    if item.get("type") in ["book", "edited-book", "monograph", "reference-book"]:

                        if item.get("title"):
                            book_title = item["title"][0]

                        if item.get("subtitle"):
                            book_subtitle = item["subtitle"][0]

                        break

    else:

        if len(container) > 0:
            journal = container[0]

    # -----------------------------------------------------
    # Other fields
    # -----------------------------------------------------

    volume = cross.get("volume", "")

    issue = cross.get("issue", "")

    pages = cross.get("page", "")

    publisher = cross.get("publisher", "").rstrip(".")

    url = cross.get("URL", "")

    # -----------------------------------------------------
    # Identifier
    # -----------------------------------------------------

    if cross.get("author"):
        first_author = cross["author"][0].get("family", "Unknown")
    else:
        first_author = "Unknown"

    # Rimuove tutto tranne lettere e numeri
    # Esempio:
    # "Dal Corso" -> "DalCorso"
    # "García-López" -> "GarcíaLópez"
    # "O'Connor" -> "OConnor"
    first_author = re.sub(r"[^\w]", "", first_author, flags=re.UNICODE)

    # Prima parola significativa del titolo
    if title:
        first_word = re.sub(r"[^\w]", "", title.split()[0], flags=re.UNICODE)
    else:
        first_word = ""

    identifier = f"{first_author}{year}{first_word}"

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    publications.append({

        "id": identifier,

        "type": pub_type,

        "title": title,

        "authors": authors,

        "journal": journal,

        "book_title": book_title,

        "book_subtitle": book_subtitle,

        "series": series,

        "editors": editors,

        "year": year,

        "month": month,

        "day": day,

        "volume": volume,

        "issue": issue,

        "pages": pages,

        "publisher": publisher,

        "doi": doi,

        "url": url

    })

    time.sleep(0.2)

# ---------------------------------------------------------
# Sort
# ---------------------------------------------------------

publications.sort(

    key=lambda x: (

        int(x["year"] or 0),

        int(x["month"] or 0),

        int(x["day"] or 0)

    ),

    reverse=True

)

# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

output = {
    "last_update": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "publications": publications
}

with open("publications.json","w",encoding="utf8") as f:
    json.dump(output,f,indent=4,ensure_ascii=False)

print("Pubblicazioni trovate:", len(publications))