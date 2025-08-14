from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
from tqdm import tqdm
import time
import os
import shutil
import requests

DELAY = 0.7  # délai entre traductions
TEMP_DIR = "temp_chapitres"
os.makedirs(TEMP_DIR, exist_ok=True)

DEEPL_API_KEY = "7d0ebf6f-1cb2-40db-8522-4adbe6aa46e3:fx"  # <-- Mets ta clé ici

def translate_text(text):
    try:
        tqdm.write(f"  → Traduction du texte (extrait) : {text[:60]}...")
        response = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={
                "auth_key": DEEPL_API_KEY,
                "text": text,
                "target_lang": "FR"
            }
        )
        result = response.json()
        translated = result["translations"][0]["text"]
        tqdm.write(f"    → Traduit en : {translated[:60]}...")
        return translated
    except Exception as e:
        tqdm.write(f"Erreur traduction: {e}")
        raise  # <-- Ajoute ceci pour arrêter le script dès la première erreur

def translate_soup(soup):
    for element in soup.find_all(text=True):
        if element.parent.name not in ['style', 'script', 'head', 'title', 'meta', '[document]']:
            text = element.strip()
            if text:
                translated = translate_text(text)
                element.replace_with(translated)
                time.sleep(DELAY)
    return soup

def translate_epub(input_path, output_path):
    tqdm.write("Lecture du fichier EPUB...")
    book = epub.read_epub(input_path)
    new_book = epub.EpubBook()

    # Métadonnées
    title = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else "Titre inconnu"
    meta_authors = book.get_metadata('DC', 'creator')
    authors = [a[0] for a in meta_authors] if meta_authors else []
    new_book.set_title(title + " (traduit)")
    new_book.set_language('fr')
    for author in authors:
        new_book.add_author(author)
    new_book.add_author("Traduction automatique DeepL")

    items = list(book.items)
    tqdm.write(f"Nombre total d'items dans le livre : {len(items)}")

    old_to_new = {}
    new_doc_items = []

    for idx, item in enumerate(tqdm(items, desc="Traduction EPUB", leave=True, dynamic_ncols=True)):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            temp_path = os.path.join(TEMP_DIR, f"{item.get_id()}.xhtml")
            if os.path.exists(temp_path):
                tqdm.write(f"⏩ Chapitre déjà traduit, chargement : {item.get_name()}")
                with open(temp_path, "rb") as f:
                    content = f.read()
            else:
                tqdm.write(f"⏳ Traduction du chapitre : {item.get_name()}")
                soup = BeautifulSoup(item.content, 'html.parser')
                soup = translate_soup(soup)
                content = str(soup).encode('utf-8')
                with open(temp_path, "wb") as f:
                    f.write(content)
            new_item = epub.EpubHtml(
                uid=item.get_id(),
                file_name=item.file_name,
                media_type=item.media_type,
                content=content
            )
            new_book.add_item(new_item)
            old_to_new[item.get_id()] = new_item
            new_doc_items.append(new_item)
        else:
            new_book.add_item(item)

    if hasattr(book, 'toc') and book.toc:
        def map_toc(toc):
            if isinstance(toc, list):
                return [map_toc(i) for i in toc]
            elif isinstance(toc, tuple):
                return tuple(map_toc(i) for i in toc)
            elif hasattr(toc, 'get_id') and toc.get_id() in old_to_new:
                return old_to_new[toc.get_id()]
            else:
                return toc
        new_book.toc = map_toc(book.toc)
    else:
        new_book.toc = tuple(new_doc_items)

    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())
    new_book.spine = ['nav'] + new_doc_items

    epub.write_epub(output_path, new_book)
    tqdm.write(f"\n✅ EPUB traduit sauvegardé : {output_path}")

    shutil.rmtree(TEMP_DIR)

if __name__ == "__main__":
    input_file = "Clown_LotM_Vol1.epub"  # Mets ton fichier ici
    output_file = "Clown_LotM_Vol1_FR.epub"
    translate_epub(input_file, output_file)