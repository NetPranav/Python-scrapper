import os
import sys
import urllib.request
import urllib.error

# Ensure UTF-8 stdout/stderr on Windows to avoid UnicodeEncodeError in cp1252
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# mapping of Font Name to GitHub raw URL for the TTF
FONTS = {
    "Pacifico": "https://raw.githubusercontent.com/google/fonts/main/ofl/pacifico/Pacifico-Regular.ttf",
    "Righteous": "https://raw.githubusercontent.com/google/fonts/main/ofl/righteous/Righteous-Regular.ttf",
    "Creepster": "https://raw.githubusercontent.com/google/fonts/main/ofl/creepster/Creepster-Regular.ttf",
    "Lobster": "https://raw.githubusercontent.com/google/fonts/main/ofl/lobster/Lobster-Regular.ttf",
    "Permanent Marker": "https://raw.githubusercontent.com/google/fonts/main/apache/permanentmarker/PermanentMarker-Regular.ttf",
    "Orbitron": "https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
    "Cinzel": "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    "Bangers": "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "Caveat": "https://raw.githubusercontent.com/google/fonts/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Playfair Display": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bital,wght%5D.ttf",
    "Russo One": "https://raw.githubusercontent.com/google/fonts/main/ofl/russoone/RussoOne-Regular.ttf",
    "Black Ops One": "https://raw.githubusercontent.com/google/fonts/main/ofl/blackopsone/BlackOpsOne-Regular.ttf",
    "Montserrat": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Oswald": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "Bebas Neue": "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf",
    "Dancing Script": "https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
    "Amatic SC": "https://raw.githubusercontent.com/google/fonts/main/ofl/amaticsc/AmaticSC-Regular.ttf"
}

def download_fonts():
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    for font_name, url in FONTS.items():
        print(f"Downloading {font_name}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                out_path = os.path.join(fonts_dir, f"{font_name}.ttf")
                with open(out_path, 'wb') as f:
                    f.write(response.read())
            print(f"  Successfully downloaded {font_name}")
        except Exception as e:
            print(f"  Failed to download {font_name} from {url}: {e}")
            
if __name__ == "__main__":
    download_fonts()
