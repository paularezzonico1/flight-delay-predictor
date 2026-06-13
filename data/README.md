# Data

The model trains on the US DOT / Bureau of Transportation Statistics
"On-Time Performance" dataset — the canonical public flight-delay source:
https://www.transtats.bts.gov/ot_delay/OT_Delay.aspx

Drop a CSV here as `data/flights.csv` (standard BTS columns) and the training
pipeline will use it automatically. With no CSV present, a realistic synthetic
dataset is generated so the project runs end-to-end out of the box.

Expected BTS columns (subset): `OP_UNIQUE_CARRIER`, `ORIGIN`, `DEST`, `MONTH`,
`DAY_OF_WEEK`, `CRS_DEP_TIME`, `DEP_DELAY`.
