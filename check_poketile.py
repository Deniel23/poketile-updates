import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import requests

URL = "https://poketile.com/"
STATE_FILE = Path("state.json")
WEBHOOK = os.environ["DISCORD_WEBHOOK"]


def read_updates():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="es-ES")
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        # The visible game button usually includes the current version.
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
            # Fallback for a clickable element that is not a native button.
            try:
                page.get_by_text(re.compile("Novedades", re.I)).first.click(timeout=7000)
                clicked = True
            except Exception:
                pass

        if not clicked:
            browser.close()
            raise RuntimeError("No he encontrado el botón «Novedades» en PokéTile.")

        page.wait_for_timeout(1500)
        body = page.locator("body").inner_text(timeout=10000)
        browser.close()

    versions = re.findall(r"\bv\s*(\d+)\b", body, flags=re.I)
    if not versions:
        raise RuntimeError("No he podido detectar el número de versión en la página.")

    version = int(versions[-1])

    # The modal title is the last occurrence of «Novedades» in the visible page text.
    marker = body.lower().rfind("novedades")
    if marker < 0:
        raise RuntimeError("No he podido localizar el contenido de Novedades.")

    notes = body[marker + len("novedades"):].strip()
    for stop_text in ("Tienes ideas o dudas", "Únete al Discord", "\nCerrar"):
        pos = notes.lower().find(stop_text.lower())
        if pos >= 0:
            notes = notes[:pos].strip()

    # Remove a version label if it was included immediately after the heading.
    notes = re.sub(r"^[\s·|—-]*v\s*\d+.*?\n", "", notes, count=1, flags=re.I)
    notes = re.sub(r"\n{3,}", "\n\n", notes).strip()

    if len(notes) < 20:
        raise RuntimeError("El contenido extraído parece incompleto; no publicaré nada.")

    date_match = re.search(
        r"\b\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}\b|\b\d{1,2}\s+[a-záéíóú]+\s+\d{4}\b",
        body, flags=re.I
    )
    date = date_match.group(0) if date_match else "Fecha indicada en el juego"
    return version, date, notes


def send_discord(version, date, notes):
    # Discord embed descriptions have a 4096-character limit.
    chunks = [notes[i:i + 3900] for i in range(0, len(notes), 3900)]
    for index, chunk in enumerate(chunks, start=1):
        title = f"✨ PokéTile v{version}" if index == 1 else f"PokéTile v{version} · continuación"
        payload = {
            "username": "PokéTile Updates",
            "embeds": [{
                "title": title,
                "url": URL,
                "description": chunk,
                "color": 0x5865F2,
                "footer": {"text": f"{date} · Novedades oficiales de PokéTile"}
            }]
        }
        response = requests.post(WEBHOOK, json=payload, timeout=30)
        response.raise_for_status()


def main():
    version, date, notes = read_updates()
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    previous = state.get("version")
    if previous is None:
        print(f"Primera ejecución: guardo v{version} como referencia sin publicar el parche antiguo.")
    elif int(previous) != version:
        print(f"Nueva versión detectada: v{previous} -> v{version}.")
        send_discord(version, date, notes)
    else:
        print(f"Sin cambios: PokéTile sigue en v{version}.")

    STATE_FILE.write_text(
        json.dumps({"version": version}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
