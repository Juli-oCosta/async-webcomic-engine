"""Dados sintéticos locais. Só escreve em um banco tgi_demo_* identificado."""
import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re

from bson import ObjectId
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
SEED_KEY = "entre-quadros-demo-v1"
COMIC_ID = ObjectId("710000000000000000000001")
EMPTY_COMIC_ID = ObjectId("710000000000000000000002")
CHAPTER_IDS = [ObjectId(f"{0x720000000000000000000000 + n:024x}") for n in (1, 2, 3)]
CREATED_AT = datetime(2026, 10, 24, tzinfo=timezone.utc)
PANELS = [
    ("O começo da maré", "Toda manhã, Lia contava os barcos.", "Naquela manhã, faltava um."),
    ("Uma luz na distância", "No alto da ilha, o farol esperava.", "Lia decidiu subir antes da chuva."),
    ("O caminho de pedra", "O vento conhecia cada curva.", "Ela conhecia o som do mar."),
    ("A pequena chave", "Debaixo da porta, um envelope.", "Dentro dele, a chave de sempre."),
    ("Uma janela acesa", "O horizonte começava a desaparecer.", "Era hora de acender a luz."),
    ("Entre ondas", "O primeiro clarão atravessou a neblina.", "O segundo encontrou uma vela."),
    ("De volta à costa", "Devagar, o barco virou para a ilha.", "A vila ainda estava acordada."),
    ("Um novo amanhecer", "Lia voltou a contar os barcos.", "Dessa vez, estavam todos lá."),
    ("Depois da chuva", "As pedras guardavam o cheiro do mar.", "O céu tinha espaço para outra história."),
    ("O mapa dobrado", "No bolso do casaco, um velho mapa.", "Havia uma ilha que ela não conhecia."),
    ("Uma linha no horizonte", "O barco seguiu a luz da manhã.", "O farol ficou pequeno, bem devagar."),
    ("A próxima página", "Lia abriu o mapa mais uma vez.", "Toda viagem começa com uma pergunta."),
]


def page_svg(number, title, first_line, second_line):
    sun_x = 180 + (number % 5) * 110
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200">
<title>O farol e a maré — página {number}</title>
<rect width="900" height="1200" fill="#f7f1df"/>
<text x="58" y="61" font-family="Georgia,serif" font-size="15" letter-spacing="4" fill="#738474">O FAROL E A MARÉ</text>
<text x="58" y="113" font-family="Georgia,serif" font-size="37" fill="#29483f">{escape(title)}</text>
<rect x="55" y="154" width="790" height="455" rx="4" fill="#c3d2b9" stroke="#29483f" stroke-width="3"/>
<circle cx="{sun_x}" cy="285" r="67" fill="#e7ad71"/>
<path d="M56 455 Q210 405 380 460 T845 450 V608 H56Z" fill="#8fae9f"/>
<path d="M56 525 Q240 480 430 535 T845 510 V608 H56Z" fill="#547b70"/>
<path d="M510 545 L580 430 L750 430 L808 545Z" fill="#687b58"/>
<path d="M624 432 L638 275 L684 275 L699 432Z" fill="#f9efcf" stroke="#29483f" stroke-width="4"/>
<path d="M632 277 L662 245 L692 277Z" fill="#a66243" stroke="#29483f" stroke-width="4"/>
<rect x="636" y="279" width="51" height="32" fill="#eac17c" stroke="#29483f" stroke-width="3"/>
<path d="M636 312 L688 335 M632 360 L692 383" stroke="#a66243" stroke-width="15"/>
<path d="M300 510 L365 510 L348 532 L315 532Z" fill="#243e38"/>
<path d="M336 504 L336 440 L370 497Z" fill="#f4e5c4" stroke="#29483f" stroke-width="2"/>
<rect x="55" y="635" width="790" height="330" rx="4" fill="#e8d6ac" stroke="#29483f" stroke-width="3"/>
<path d="M56 890 Q300 770 490 850 T845 825 V964 H56Z" fill="#99ad87"/>
<path d="M430 964 Q470 850 580 812" stroke="#d9cba8" stroke-width="60" fill="none"/>
<circle cx="445" cy="774" r="27" fill="#d7a77d" stroke="#29483f" stroke-width="3"/>
<path d="M415 762 Q440 720 474 760" fill="#314b41"/>
<path d="M415 805 L475 805 L486 896 L405 896Z" fill="#b96e48" stroke="#29483f" stroke-width="4"/>
<path d="M422 896 L418 943 M469 896 L478 943" stroke="#29483f" stroke-width="13"/>
<path d="M413 821 L381 861 M478 823 L514 850" stroke="#29483f" stroke-width="9"/>
<text x="65" y="1033" font-family="Georgia,serif" font-size="25" fill="#29483f">{escape(first_line)}</text>
<text x="65" y="1075" font-family="Georgia,serif" font-size="25" fill="#29483f">{escape(second_line)}</text>
<path d="M65 1120 H835" stroke="#d2d1bc"/>
<text x="65" y="1155" font-family="sans-serif" font-size="12" letter-spacing="2" fill="#87907c">HISTÓRIA SINTÉTICA PARA DEMONSTRAÇÃO LOCAL</text>
<text x="808" y="1155" font-family="Georgia,serif" font-size="20" fill="#29483f">{number:02}</text>
</svg>'''


def generate_assets():
    target = ROOT / "frontend" / "demo"
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"dataset": SEED_KEY, "synthetic": True, "width": 900, "height": 1200, "files": []}
    for number, lines in enumerate(PANELS, 1):
        data = page_svg(number, *lines).encode("utf-8")
        name = f"page-{number:02}.svg"
        (target / name).write_bytes(data)
        manifest["files"].append({"path": f"/static/demo/{name}", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def seed_demo(database_name):
    if not re.fullmatch(r"tgi_demo_[a-z0-9_]{1,48}", database_name):
        raise ValueError("Escolha um banco de demonstração com prefixo tgi_demo_; bancos permanentes são recusados.")
    with MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000) as client:
        client.admin.command("ping")
        database = client[database_name]
        marker = database.demo_metadata.find_one({"_id": SEED_KEY})
        if database.list_collection_names() and marker is None:
            raise ValueError("O banco já contém dados sem identificação desta demonstração; nada foi alterado.")
        database.demo_metadata.update_one({"_id": SEED_KEY}, {"$setOnInsert": {"synthetic": True, "version": 1}}, upsert=True)
        assets = generate_assets()
        database.chapters.create_index([("comic_id", 1), ("chapter_number", 1)], unique=True, name="comic_chapter_number_unique")
        database.pages.create_index([("chapter_id", 1), ("page_number", 1)], unique=True, name="chapter_page_number_unique")
        for identifier, title, description in (
            (COMIC_ID, "O farol e a maré", "Lia, uma ilha e uma luz que atravessa a neblina. Uma história sintética em doze páginas."),
            (EMPTY_COMIC_ID, "Caderno em branco", "Um espaço para uma história que ainda vai começar."),
        ):
            database.catalogs.replace_one({"_id": identifier}, {
                "_id": identifier, "title": title, "author": "Acervo de demonstração", "description": description,
                "tags": ["demonstração", "sintético"], "cover_url": None,
            }, upsert=True)
        for number, title in enumerate(("A luz da ilha", "Pausa entre as marés", "Depois da chuva"), 1):
            identifier = CHAPTER_IDS[number - 1]
            database.chapters.replace_one({"_id": identifier}, {
                "_id": identifier, "comic_id": str(COMIC_ID), "chapter_number": number, "title": title,
                "initial_pages": [], "created_at": CREATED_AT,
            }, upsert=True)
        for number in range(1, len(PANELS) + 1):
            chapter_index = 0 if number <= 8 else 2
            page_number = number if number <= 8 else number - 8
            identifier = ObjectId(f"{0x730000000000000000000000 + number:024x}")
            database.pages.replace_one({"_id": identifier}, {
                "_id": identifier, "chapter_id": str(CHAPTER_IDS[chapter_index]), "page_number": page_number,
                "image_url": f"/static/demo/page-{number:02}.svg", "width": 900, "height": 1200,
            }, upsert=True)
        return {"database": database_name, "dataset": SEED_KEY, "comics": 2, "chapters": 3, "pages": 12,
                "image_bytes": sum(item["size_bytes"] for item in assets["files"]), "synthetic": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="tgi_demo_local", help="Banco local isolado com prefixo tgi_demo_")
    args = parser.parse_args()
    try:
        print(json.dumps(seed_demo(args.database), ensure_ascii=False, indent=2))
    except Exception as error:
        parser.exit(1, f"Não foi possível preparar a demonstração ({type(error).__name__}). Confira o MongoDB local e o banco escolhido.\n")
