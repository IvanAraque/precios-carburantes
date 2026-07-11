# Precios de carburantes en España

Pipeline ETL automatizado que descarga a diario los precios de las ~12.000 estaciones de servicio de España desde la [API de datos abiertos del MITECO](https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/), los limpia, genera agregados históricos y los publica en un dashboard estático con GitHub Pages.

**Dashboard:** https://ivanaraque.github.io/precios-carburantes/

## Arquitectura

```
GitHub Actions (cron diario)
        │
        ▼
etl/fetch_prices.py ──► descarga API ──► limpieza (pandas)
        │
        ├──► data/latest/estaciones.csv      snapshot completo del día
        └──► docs/data/*.csv                 histórico agregado
                    │
                    ▼
            GitHub Pages (docs/)
            dashboard con Chart.js
```

- El snapshot completo (`data/latest/`) se sobreescribe cada día.
- El histórico (`docs/data/`) solo guarda agregados (media, mediana, min, max por producto, provincia y marca), así el repo se mantiene ligero aunque acumule años de datos.

## Datos generados

| Fichero | Contenido | Granularidad |
|---|---|---|
| `data/latest/estaciones.csv` | Snapshot con precios, coordenadas y datos de cada estación | estación |
| `docs/data/nacional.csv` | Media, mediana, min, max por producto y día | producto × día |
| `docs/data/provincias.csv` | Precio medio por provincia, producto y día | provincia × producto × día |
| `docs/data/marcas.csv` | Precio medio de las 15 marcas con más estaciones | marca × producto × día |
| `docs/data/estaciones.json` | Estaciones con dirección, coordenadas y precios, agrupadas por municipio; alimenta el buscador de la web (se sobreescribe, no acumula histórico) | municipio |

## Puesta en marcha

```bash
pip install -r requirements.txt
python etl/fetch_prices.py
```

En GitHub:

1. Settings → Pages → Source: `main`, carpeta `/docs`
2. Settings → Actions → General → Workflow permissions: "Read and write permissions"
3. Actions → "etl diario" → Run workflow (primer snapshot manual)

A partir de ahí el workflow corre solo cada mañana.

## Fuente de los datos

Precios remitidos por las estaciones de servicio en cumplimiento de la Orden ITC/2308/2007 y publicados por el Ministerio para la Transición Ecológica y el Reto Demográfico.
