import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

URLS = [
    "https://services.stgeorges.bc.ca/school_website/menu.php?m=Lunch",
    "https://services.stgeorges.bc.ca/school_website/menu.php?m=Lunch&week=next"
]

events = []

for url in URLS:
    html = requests.get(url, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n", strip=True)

    # Find dates such as AUG 17
    dates = re.findall(
        r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})",
        text
    )

    # Get table cells
    cells = [
        cell.get_text(" ", strip=True)
        for cell in soup.find_all(["td", "th"])
    ]

    # Remove headings/date cells and keep likely menu cells
    menu_cells = []

    for cell in cells:
        cleaned = cell.strip()

        if not cleaned:
            continue

        if cleaned.upper() in [
            "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY",
            "THIS WEEK", "NEXT WEEK"
        ]:
            continue

        if re.fullmatch(
            r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}",
            cleaned.upper()
        ):
            continue

        menu_cells.append(cleaned)

    # Only create events if actual menu content exists
    for i, (month, day) in enumerate(dates[:5]):

        if i >= len(menu_cells):
            continue

        menu = menu_cells[i].strip()

        if not menu:
            continue

        month_number = datetime.strptime(month, "%b").month

        now = datetime.now()
        year = now.year

        date = datetime(year, month_number, int(day))

        # Handle December -> January
        if now.month == 12 and month_number == 1:
            date = date.replace(year=year + 1)

        events.append((date, menu))


def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Saints Lunch//EN",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Saints Lunch",
    "X-WR-TIMEZONE:America/Vancouver"
]

for date, menu in events:

    datestr = date.strftime("%Y%m%d")

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:saints-lunch-{datestr}@stgeorges",
        f"DTSTART;VALUE=DATE:{datestr}",
        f"DTEND;VALUE=DATE:{(date.replace(hour=0)).strftime('%Y%m%d')}",
        f"SUMMARY:🍽 {escape_ics(menu)}",
        f"DESCRIPTION:{escape_ics(menu)}",
        "END:VEVENT"
    ])

ics.append("END:VCALENDAR")

with open("lunch.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(ics))
