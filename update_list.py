import requests
import time
import json
import re
from datetime import datetime
import sys

# --- CONFIGURACIÓN ---
LOCAL_FILE = 'prr.txt'

URLS_REMOTAS = [
    'https://raw.githubusercontent.com/678190/mysky.w3u/3b4b7637ad3c82016d78c8f6720366c8d7ce8a2f/senial1.w3u',
    'https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/mx.m3u',
    'https://raw.githubusercontent.com/678190/RIK/refs/heads/main/AIR.w3u'
]

EPG_URL = 'https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml'
OUTPUT_FILE = 'android.m3u'
HEADERS = {'User-Agent': 'VLC/3.0.20 LibVLC/3.0.20'}
INTERVALO_HORAS = 6


def limpiar_texto(txt):
    if not txt:
        return ""
    return str(txt).replace("\n", " ").replace("\r", " ").strip()


def url_es_stream(url):
    u = url.lower()
    return any(x in u for x in [
        ".m3u8", ".ts", ".mp4", ".mkv", ".avi",
        "/playlist", "/live/", "/livetv/", "hls"
    ])


def agregar_output_ts(url):
    if not url:
        return url

    u = url.lower()

    if any(ext in u for ext in [".m3u8", ".ts", ".mp4"]):
        return url

    if not url_es_stream(url):
        return url

    sep = "&" if "?" in url else "?"
    return f"{url}{sep}output=ts"


def procesar_m3u(texto_m3u, es_remoto=False):
    if not texto_m3u or not isinstance(texto_m3u, str):
        return []

    lineas = texto_m3u.splitlines()
    resultado = []

    for i, raw in enumerate(lineas):
        try:
            linea = raw.strip()

            if not linea:
                continue

            if linea.startswith("#EXTINF"):
                extinf = linea
                extras = []

                j = i + 1
                while j < len(lineas):
                    siguiente = lineas[j].strip()

                    if not siguiente:
                        j += 1
                        continue

                    if siguiente.startswith("#"):
                        extras.append(siguiente)
                        j += 1
                        continue

                    if siguiente.startswith("http"):
                        url = siguiente

                        if es_remoto:
                            url = agregar_output_ts(url)

                        resultado.append(extinf)
                        resultado.extend(extras)
                        resultado.append(url)
                        break

                    break

        except Exception:
            continue

    return resultado


def sacar_objetos_w3u_regex(texto):
    objetos = []
    patron = re.compile(r'\{[^{}]*"url"\s*:\s*"[^"]+"[^{}]*\}', re.I | re.S)

    for m in patron.finditer(texto):
        bloque = m.group(0)

        def sacar(campo):
            r = re.search(rf'"{campo}"\s*:\s*"([^"]*)"', bloque, re.I | re.S)
            return limpiar_texto(r.group(1)) if r else ""

        name = sacar("name")
        url = sacar("url")
        image = sacar("image")
        referer = sacar("referer")
        user_agent = sacar("userAgent")

        embed = bool(
            re.search(r'"embed"\s*:\s*true', bloque, re.I) or
            re.search(r'"EMBED"\s*:\s*true', bloque, re.I)
        )

        if name and url:
            objetos.append({
                "name": name,
                "url": url,
                "image": image,
                "referer": referer,
                "userAgent": user_agent,
                "embed": embed
            })

    return objetos


def recorrer_estaciones_w3u(data):
    estaciones = []

    def walk(obj, grupo="W3U"):
        if isinstance(obj, dict):
            nombre_grupo = obj.get("name", grupo)

            if "stations" in obj and isinstance(obj["stations"], list):
                for st in obj["stations"]:
                    if isinstance(st, dict):
                        st["_group"] = nombre_grupo
                        estaciones.append(st)

            for v in obj.values():
                walk(v, nombre_grupo)

        elif isinstance(obj, list):
            for item in obj:
                walk(item, grupo)

    walk(data)
    return estaciones


def procesar_w3u(texto_w3u, es_remoto=True):
    resultado = []
    estaciones = []

    try:
        data = json.loads(texto_w3u)
        estaciones = recorrer_estaciones_w3u(data)
    except Exception:
        estaciones = sacar_objetos_w3u_regex(texto_w3u)

    omitidos_embed = 0

    for st in estaciones:
        try:
            embed = bool(st.get("embed") or st.get("EMBED"))

            # OMITIR EMBEDS
            if embed:
                omitidos_embed += 1
                continue

            nombre = limpiar_texto(st.get("name", "Sin nombre"))
            url = limpiar_texto(st.get("url", ""))
            logo = limpiar_texto(st.get("image", ""))
            grupo = limpiar_texto(st.get("_group", "W3U"))
            referer = limpiar_texto(st.get("referer", ""))
            user_agent = limpiar_texto(st.get("userAgent", ""))

            if not url.startswith("http"):
                continue

            if es_remoto:
                url = agregar_output_ts(url)

            attrs = [
                'tvg-id=""',
                f'tvg-name="{nombre}"',
                f'tvg-logo="{logo}"',
                f'group-title="{grupo}"'
            ]

            resultado.append(f'#EXTINF:-1 {" ".join(attrs)},{nombre}')

            if referer:
                resultado.append(f'#EXTVLCOPT:http-referrer={referer}')
                resultado.append(f'#KODIPROP:inputstream.adaptive.stream_headers=Referer={referer}')

            if user_agent:
                resultado.append(f'#EXTVLCOPT:http-user-agent={user_agent}')

            resultado.append(url)

        except Exception:
            continue

    if omitidos_embed:
        print(f"🧹 W3U embeds omitidos: {omitidos_embed}")

    return resultado


def procesar_canales(texto, es_remoto=False):
    if not texto or not isinstance(texto, str):
        return []

    t = texto.strip()

    if t.startswith("{") or '"stations"' in t or '"groups"' in t:
        return procesar_w3u(t, es_remoto=es_remoto)

    return procesar_m3u(t, es_remoto=es_remoto)


def ejecutar_actualizacion():
    ahora = datetime.now().strftime('%H:%M:%S')
    print(f"[{ahora}] 🔄 Iniciando ciclo de limpieza...")

    final_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

    try:
        with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
            canales_locales = procesar_canales(f.read(), es_remoto=False)
            final_lines.extend(canales_locales)
            print(f"✅ Local OK: {len(canales_locales)//2} aprox.")
    except Exception as e:
        print(f"⚠️ Aviso: Saltando local ({e})")

    for url_fuente in URLS_REMOTAS:
        try:
            r = requests.get(url_fuente, headers=HEADERS, timeout=30)

            if r.status_code == 200:
                texto = r.text

                if "#EXT" in texto or '"stations"' in texto or '"groups"' in texto:
                    nuevos = procesar_canales(texto, es_remoto=True)
                    final_lines.extend(nuevos)
                    print(f"✅ Cargada: {url_fuente[-18:]} | +{len(nuevos)//2} aprox.")
                else:
                    print(f"⚠️ No parece lista válida: {url_fuente[-18:]}")
            else:
                print(f"❌ Error {r.status_code}: {url_fuente[-18:]}")

        except Exception as e:
            print(f"🚫 Error de red en {url_fuente[-18:]}: {e}")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(final_lines))

        print(f"🚀 Archivo '{OUTPUT_FILE}' actualizado con éxito.")
        print(f"📺 Total líneas: {len(final_lines)}")

    except Exception as e:
        print(f"🚨 Error al guardar archivo: {e}")


def main():
    while True:
        try:
            ejecutar_actualizacion()
        except Exception as e:
            print(f"🔥 Error inesperado en el bucle: {e}")

        print(f"⏳ Esperando {INTERVALO_HORAS} horas...")
        time.sleep(INTERVALO_HORAS * 3600)


if __name__ == "__main__":
    try:
        ejecutar_actualizacion()
    except Exception as e:
        print(f"🔥 Falló todo: {e}")
        sys.exit(1)
