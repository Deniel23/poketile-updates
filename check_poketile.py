
import json
import os
import re
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = "https://poketile.com/"
STATE_FILE = Path("state.json")
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

DATE_PATTERN = (
    r"\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}"
    r"|\d{1,2}\s+[a-záéíóú]+\s+\d{4}"
)

# Detecta encabezados como:
# Torre Desafío y chapas v86 · 11 nov 2026
HEADING_PATTERN = re.compile(
    rf"^(?P<title>.{{1,180}}?)\s+"
    rf"v\s*(?P<version>\d+)\s*[·|—-]\s*"
    rf"(?P<date>{DATE_PATTERN})\s*$",
    re.IGNORECASE | re.MULTILINE
)


def read_updates():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="es-ES")
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        buttons = page.locator("button")
        clicked = False

        for i in range(min(buttons.count(), 100)):
            button = buttons.nth(i)
            try:
                label = button.inner_text(timeout=1000).strip()
                if "novedades" in label.lower():
                    button.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            try:
                page.get_by_text(
                    re.compile("Novedades", re.I)
                ).first.click(timeout=7000)
                clicked = True
            except Exception:
                pass

        if not clicked:
            browser.close()
            raise RuntimeError(
                "No he encontrado el botón Novedades."
            )

        page.wait_for_timeout(1500)
        body = page.locator("body").inner_text(timeout=10000)
        browser.close()

    marker = body.lower().rfind("novedades")
    if marker < 0:
        raise RuntimeError("No he encontrado el contenido de Novedades.")

    notes = body[marker + len("novedades"):].strip()

    for stop_text in (
        "Tienes ideas o dudas",
        "Únete al Discord",
        "\nCerrar"
    ):
        pos = notes.lower().find(stop_text.lower())
        if pos >= 0:
            notes = notes[:pos].strip()

    notes = re.sub(r"\n{3,}", "\n\n", notes).strip()

    headings = list(HEADING_PATTERN.finditer(notes))

    if not headings:
        raise RuntimeError(
            "No he podido separar las novedades por versión. "
            "No publicaré un mensaje mezclado."
        )

    updates = []

    for index, heading in enumerate(headings):
        version = int(heading.group("version"))
        title = heading.group("title").strip()
        date = heading.group("date").strip()

        start = heading.end()
        end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(notes)
        )

        description = notes[start:end].strip()

        # Limpieza de posibles separadores.
        description = re.sub(
            r"^[\s·|—-]+", "", description
        ).strip()

        description = re.sub(
            r"\n{3,}", "\n\n", description
        ).strip()

        if len(description) < 10:
            raise RuntimeError(
                f"El contenido de la versión {version} parece incompleto."
            )

        updates.append({
            "version": version,
            "title": title,
            "date": date,
            "notes": description
        })

    # Evita versiones repetidas y ordena de más antigua a más reciente.
    unique = {item["version"]: item for item in updates}
    updates = sorted(unique.values(), key=lambda x: x["version"])

    return updates


def send_discord(update):
    version = update["version"]
    title = update["title"]
    date = update["date"]
    notes = update["notes"]

    # Discord admite hasta 4096 caracteres por descripción.
    chunks = [
        notes[i:i + 3900]
        for i in range(0, len(notes), 3900)
    ]

    for index, chunk in enumerate(chunks, start=1):
        embed_title = (
            f"✨ PokéTile v{version} · {title}"
            if index == 1
            else f"✨ PokéTile v{version} · continuación"
        )

        payload = {
            "username": "PokéTile Updates",
            "embeds": [{
                "title": embed_title[:256],
                "url": URL,
                "description": chunk,
                "color": 0x5865F2,
                "footer": {
                    "text": f"{date} · Novedades oficiales de PokéTile"
                }
            }]
        }

        response = requests.post(
            WEBHOOK,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

    print(f"Publicado correctamente PokéTile v{version}.")


def main():
    updates = read_updates()

    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            raise RuntimeError(
                "No puedo leer state.json. No modificaré el estado."
            )

    previous = state.get("version")

    if previous is None:
        latest = max(item["version"] for item in updates)
        print(
            f"Primera ejecución: guardo v{latest} "
            "como referencia sin publicar parches antiguos."
        )

    else:
        previous = int(previous)

        new_updates = [
            item for item in updates
            if item["version"] > previous
        ]

        if not new_updates:
            print(
                f"Sin cambios nuevos. Última versión conocida: v{previous}."
            )
        else:
            print(
                f"Detectadas {len(new_updates)} versiones nuevas."
            )

            for update in new_updates:
                send_discord(update)

    latest = max(item["version"] for item in updates)

    STATE_FILE.write_text(
        json.dumps(
            {"version": latest},
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
