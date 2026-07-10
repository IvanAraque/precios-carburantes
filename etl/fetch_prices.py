import os
from datetime import datetime, timezone

import pandas as pd
import requests

URL = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"

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
    "Longitud (WGS 84)": "lon",
    "Horario": "horario",
    **PRODUCTOS,
}


def descargar():
    r = requests.get(URL, headers={"Accept": "application/json"}, timeout=120)
    r.raise_for_status()
    data = r.json()
    return pd.DataFrame(data["ListaEESSPrecio"])


def limpiar(df):
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

    print(f"ok: {len(df)} estaciones procesadas ({fecha})")


if __name__ == "__main__":
    main()
