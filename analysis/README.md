# analysis/ — Estudio de motivos (Micrositios Fase 1)

Scripts de análisis **solo lectura** para el proyecto Micrositios Aremko.
Ninguno escribe en la base de datos ni exporta datos personales: todas las
salidas son agregados (conteos, montos, porcentajes).

## Scripts

| Script | Dónde corre | Qué hace |
|---|---|---|
| `estudio_historico_csv.py` | Local (sin BD) | Agrega `data/servicios_historicos.csv` (2020-2024) por categoría, mes, día de semana y servicio. Salidas en `analysis/output/`. |
| `estudio_reservas_bd.py` | **Shell de Render** | Agregados de la BD viva: reservas por tipo/mes, anticipación de compra, día/hora, proxy de canal por método de pago, encuesta "cómo se enteró", leads Refugio por UTM, gift cards por mes. Imprime markdown a stdout. |
| `export_ads.py` | **Shell de Render** | Vía las APIs ya integradas (`google_ads_reporter`, `meta_reporter`): campañas, keywords y términos de búsqueda reales de Google Ads (12 meses) + rendimiento por campaña de Meta. Imprime markdown a stdout. |

## Cómo correr los de Render

En el shell del servicio web de Render (mismo entorno donde corre Django):

```bash
python analysis/estudio_reservas_bd.py > /tmp/estudio_reservas.md
python analysis/export_ads.py > /tmp/export_ads.md
cat /tmp/estudio_reservas.md
cat /tmp/export_ads.md
```

Copiar el contenido de ambos archivos y entregarlo para el análisis
(o adjuntarlos al PR). Si faltan credenciales de alguna API, la sección
correspondiente lo indica y el resto del informe se genera igual.

## Salidas locales (`analysis/output/`)

CSVs agregados y anónimos generados por `estudio_historico_csv.py`:
`historico_por_anio.csv`, `historico_por_mes_categoria.csv`,
`historico_estacionalidad.csv`, `historico_dia_semana.csv`,
`historico_top_servicios.csv`.
