import re
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup


CALENDAR_NAME = "Saints Lunch Menu"

URLS = [
    "https://services.stgeorges.bc.ca/school_website/menu.php?m=Lunch",
    "https://services.stgeorges.bc.ca/school_website/menu.php?m=Lunch&week=next",
]

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

date_pattern = re.compile(
    r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})\b",
    re.IGNORECASE,
)


def clean_cell(cell):
    text = cell.get_text("\n", strip=True)
    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def get_date(month, day):
    today = date.today()
    month = MONTHS[month.upper()]
    day = int(day)

    choices = []

    for year in [today.year - 1, today.year, today.year + 1]:
        try:
            choices.append(date(year, month, day))
        except ValueError:
            pass

    return min(choices, key=lambda d: abs((d - today).days))


def remove_headings(text):
    text = re.sub(
        r"\b(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = date_pattern.sub("", text)

    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip(" |-")
        if line:
            lines.append(line)

    return "\n".join(lines)


def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def fold_line(line):
    result = []
    current = ""

    for char in line:
        if len((current + char).encode("utf-8")) > 73:
            result.append(current)
            current = " " + char
        else:
            current += char

    if current:
        result.append(current)

    return "\r\n".join(result)


def read_menu(url):
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    best_row = None

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for row_number, row in enumerate(rows):
            cells = row.find_all(["td", "th"], recursive=False)

            if not cells:
                continue

            texts = [clean_cell(cell) for cell in cells]
            matches = [date_pattern.search(text) for text in texts]
            count = sum(match is not None for match in matches)

            if count >= 3:
                if best_row is None or count > best_row[0]:
                    best_row = (count, rows, row_number, cells, texts)

    if best_row is None:
        raise RuntimeError("Could not find the lunch menu")

    _, rows, row_number, cells, texts = best_row

    dates = []

    for text in texts:
        match = date_pattern.search(text)

        if match:
            dates.append(get_date(match.group(1), match.group(2)))
        else:
            dates.append(None)

    menu_parts = [[] for _ in cells]

    for i, text in enumerate(texts):
        extra = remove_headings(text)
        if extra:
            menu_parts[i].append(extra)

    for row in rows[row_number + 1:]:
        row_cells = row.find_all(["td", "th"], recursive=False)

        if len(row_cells) != len(cells):
            continue

        for i, cell in enumerate(row_cells):
            text = remove_headings(clean_cell(cell))

            if text:
                menu_parts[i].append(text)

    events = {}

    for i, menu_date in enumerate(dates):
        if menu_date is None:
            continue

        menu = "\n".join(menu_parts[i]).strip()

        if menu:
            events[menu_date] = menu

    return events


events = {}

for url in URLS:
    events.update(read_menu(url))


timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Saints Lunch Menu//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    f"NAME:{CALENDAR_NAME}",
    f"X-WR-CALNAME:{CALENDAR_NAME}",
    "X-WR-TIMEZONE:America/Vancouver",
    "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    "X-PUBLISHED-TTL:PT1H",
]

for menu_date in sorted(events):
    menu = events[menu_date]

    lines = [line.strip() for line in menu.splitlines() if line.strip()]

    if not lines:
        continue

    summary = " • ".join(lines)

    start = menu_date.strftime("%Y%m%d")
    end = (menu_date + timedelta(days=1)).strftime("%Y%m%d")

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:saints-lunch-{start}@stgeorges.bc.ca",
        f"DTSTAMP:{timestamp}",
        f"LAST-MODIFIED:{timestamp}",
        f"DTSTART;VALUE=DATE:{start}",
        f"DTEND;VALUE=DATE:{end}",
        f"SUMMARY:🍽 {escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(menu)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

ics.append("END:VCALENDAR")

with open("lunch.ics", "w", encoding="utf-8", newline="") as file:
    for line in ics:
        file.write(fold_line(line) + "\r\n")

print(f"Updated {len(events)} lunch events")
