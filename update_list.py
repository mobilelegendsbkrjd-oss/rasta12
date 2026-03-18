import requests

# Configuración
LOCAL_FILE = 'prr.txt'

REMOTE_URL = 'http://tv.zeuspro.xyz:2052/get.php?username=arturo903&password=11HD4MrrPG&type=m3u_plus'

# 🔥 NUEVAS LISTAS
EXTRA_URLS = [
    'http://tecnotv.club/ma1003/lista.m3u',
    'http://tecnotv.club/ma1003/lista1.m3u',
    'http://tecnotv.club/ma1003/lista2.m3u',
    'http://tecnotv.club/ma1003/lista3.m3u',
    'http://tecnotv.club/ma1003/lista4.m3u',
    'http://tecnotv.club/ma1003/lista5.m3u',
    'http://tecnotv.club/ma1003/geomex.m3u',
    'http://tecnotv.club/ma1003/android.m3u'
]

EPG_URL = 'https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml'
OUTPUT_FILE = 'android.m3u'

HEADERS = {
    'User-Agent': 'VLC/3.0.12 LibVLC/3.0.12'
}

# Extensiones de películas/series que queremos ocultar
EXTENSIONES_PROHIBIDAS = ['.mkv', '.mp4', '.avi', '.mov', '.wmv']


def procesar_canales_vivo(texto_m3u):
    """Filtra el contenido eliminando formatos de video (VOD)"""
    lineas = texto_m3u.splitlines()
    resultado = []

    for i in range(len(lineas)):
        linea = lineas[i].strip()

        if linea.startswith("#EXTINF"):
            if i + 1 < len(lineas):
                url_siguiente = lineas[i + 1].strip().lower()

                es_pelicula = any(ext in url_siguiente for ext in EXTENSIONES_PROHIBIDAS)

                if not es_pelicula and url_siguiente.startswith("http"):
                    resultado.append(linea)
                    resultado.append(lineas[i + 1])

    return resultado


def fetch_m3u(url):
    """Descarga y procesa una lista M3U"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            canales = procesar_canales_vivo(r.text)
            print(f"✅ {url} -> {len(canales)//2} canales")
            return canales
        else:
            print(f"⚠️ Error {r.status_code} en {url}")
    except Exception as e:
        print(f"❌ Error en {url}: {e}")
    
    return []


def main():
    # Cabecera con EPG
    final_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

    # 1. Local
    try:
        with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
            canales_locales = procesar_canales_vivo(f.read())
            final_lines.extend(canales_locales)
        print(f"✅ Local: {len(canales_locales)//2} canales")
    except:
        print("⚠️ No se pudo leer archivo local")

    # 2. ZeusPro
    final_lines.extend(fetch_m3u(REMOTE_URL))

    # 3. 🔥 TecnoTV (múltiples listas)
    for url in EXTRA_URLS:
        final_lines.extend(fetch_m3u(url))

    # 4. Guardar
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(final_lines))

    print(f"\n🚀 Lista '{OUTPUT_FILE}' generada con éxito.")


if __name__ == "__main__":
    main()
