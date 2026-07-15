import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone

import pandas as pd
import requests

URL = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
CABECERAS = {
    "Accept": "application/json",
    "User-Agent": "precios-carburantes-etl (https://github.com/IvanAraque/precios-carburantes)",
}

PRODUCTOS = {
    "Precio Gasolina 95 E5": "gasolina_95_e5",
    "Precio Gasolina 98 E5": "gasolina_98_e5",
    "Precio Gasoleo A": "gasoleo_a",
    "Precio Gasoleo Premium": "gasoleo_premium",
    "Precio Gases licuados del petróleo": "glp",
}

COLUMNAS = {
    "IDEESS": "id",
    "Rótulo": "rotulo",
    "Provincia": "provincia",
    "Municipio": "municipio",
    "Localidad": "localidad",
    "Dirección": "direccion",
    "C.P.": "cp",
    "Latitud": "lat",
    "Longitud (WGS84)": "lon",
    "Horario": "horario",
    **PRODUCTOS,
}


def descargar_requests():
    r = requests.get(URL, headers=CABECERAS, timeout=60)
    r.raise_for_status()
    return r.json()


def descargar_curl():
    # curl presenta otra huella tls: a veces pasa donde requests es rechazado
    orden = ["curl", "-sS", "--fail", "--max-time", "120"]
    for clave, valor in CABECERAS.items():
        orden += ["-H", f"{clave}: {valor}"]
    salida = subprocess.run(orden + [URL], capture_output=True, check=True)
    return json.loads(salida.stdout)


def descargar(intentos=4, espera=90):
    metodos = [descargar_requests]
    if shutil.which("curl"):
        metodos.append(descargar_curl)
    for i in range(intentos):
        metodo = metodos[i % len(metodos)]
        try:
            return pd.DataFrame(metodo()["ListaEESSPrecio"])
        except Exception as e:
            if i == intentos - 1:
                raise
            print(f"intento {i + 1} ({metodo.__name__}) fallido ({type(e).__name__}), reintento en {espera}s")
            time.sleep(espera)


def limpiar(df):
    # la api ha usado ambas variantes del nombre de la longitud
    df = df.rename(columns={"Longitud (WGS 84)": "Longitud (WGS84)"})
    df = df[list(COLUMNAS)].rename(columns=COLUMNAS)
    numericas = list(PRODUCTOS.values()) + ["lat", "lon"]
    for col in numericas:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce"
        )
    df["rotulo"] = df["rotulo"].astype(str).str.strip().str.upper()
    df["provincia"] = df["provincia"].astype(str).str.strip().str.title()
    return df


def agregar(df, fecha):
    largo = df.melt(
        id_vars=["provincia", "rotulo"],
        value_vars=list(PRODUCTOS.values()),
        var_name="producto",
        value_name="precio",
    ).dropna(subset=["precio"])

    nacional = (
        largo.groupby("producto")["precio"]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", n="count")
        .round(4)
        .reset_index()
    )
    nacional.insert(0, "fecha", fecha)

    provincias = (
        largo.groupby(["provincia", "producto"])["precio"]
        .agg(media="mean", n="count")
        .round(4)
        .reset_index()
    )
    provincias.insert(0, "fecha", fecha)

    top_marcas = largo["rotulo"].value_counts().head(15).index
    marcas = (
        largo[largo["rotulo"].isin(top_marcas)]
        .groupby(["rotulo", "producto"])["precio"]
        .agg(media="mean", n="count")
        .round(4)
        .reset_index()
    )
    marcas.insert(0, "fecha", fecha)

    return nacional, provincias, marcas


def exportar_municipios(df, fecha, ruta):
    # json compacto para el buscador de la web: solo columnas necesarias,
    # una entrada por municipio, estaciones como listas posicionales
    precios = list(PRODUCTOS.values())
    df = df.dropna(subset=["lat", "lon"]).copy()
    df["clave"] = df["municipio"].str.strip() + " (" + df["provincia"] + ")"

    municipios = {}
    for clave, grupo in df.groupby("clave", sort=True):
        municipios[clave] = [
            [
                fila.rotulo,
                fila.direccion,
                round(fila.lat, 5),
                round(fila.lon, 5),
                *[None if pd.isna(v) else round(v, 3) for v in [getattr(fila, p) for p in precios]],
                None if pd.isna(fila.horario) else str(fila.horario).strip(),
            ]
            for fila in grupo.itertuples()
        ]

    salida = {
        "actualizado": fecha,
        "columnas": ["rotulo", "direccion", "lat", "lon", *precios, "horario"],
        "municipios": municipios,
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))


def anexar(df, ruta):
    # acumula histórico, reemplaza la fecha de hoy si ya existe
    if os.path.exists(ruta):
        hist = pd.read_csv(ruta)
        hist = hist[hist["fecha"] != df["fecha"].iloc[0]]
        df = pd.concat([hist, df], ignore_index=True)
    df.to_csv(ruta, index=False)


def main():
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = limpiar(descargar())

    os.makedirs("data/latest", exist_ok=True)
    os.makedirs("docs/data", exist_ok=True)

    df.to_csv("data/latest/estaciones.csv", index=False)

    nacional, provincias, marcas = agregar(df, fecha)
    anexar(nacional, "docs/data/nacional.csv")
    anexar(provincias, "docs/data/provincias.csv")
    anexar(marcas, "docs/data/marcas.csv")

    exportar_municipios(df, fecha, "docs/data/estaciones.json")

    print(f"ok: {len(df)} estaciones procesadas ({fecha})")


if __name__ == "__main__":
    main()
