# TerraWatch 🌍

**Dati ambientali in tempo reale per ogni comune italiano.**

Piattaforma pubblica e gratuita che aggrega dati satellite, qualità dell'aria, rischio idrogeologico e temperatura per tutti i 7.899 comuni italiani.

---

## Layer dati

| Layer | Fonte | Aggiornamento |
|---|---|---|
| 🌊 Rischio frana/alluvione | ISPRA Dissesto 2021 | Annuale |
| 🌬️ Qualità aria (AQI, PM2.5) | AQICN | Ogni 6 ore |
| 🌡️ Temperatura | ERA5 — Copernicus | Ogni 24 ore |
| 🛰️ Vegetazione NDVI | Sentinel-2 L2A | Ogni 5 giorni |

---

## Setup locale

### 1. Clona il repository
```bash
git clone https://github.com/Ale2588/TerraWatch.git
cd TerraWatch
```

### 2. Installa dipendenze
```bash
pip install -r requirements.txt
```

### 3. Configura credenziali
Crea un file `.env` nella root (non committarlo mai):
```
AQICN_TOKEN=il_tuo_token
COPERNICUS_USER=tua_email
COPERNICUS_PASS=tua_password
```

Poi esporta le variabili:
```bash
export $(cat .env | xargs)
```

### 4. Setup iniziale metadati comuni
```bash
python pipeline/setup_meta.py
```

### 5. Esegui la pipeline
```bash
# Tutti i layer
python pipeline/run.py --layer all

# Solo qualità aria (test rapido)
python pipeline/run.py --layer air
```

---

## Setup GitHub Actions (deploy automatico)

### Aggiungi i secrets nel repository
Vai su **Settings → Secrets and variables → Actions** e aggiungi:

| Secret | Valore |
|---|---|
| `AQICN_TOKEN` | Token da aqicn.org |
| `COPERNICUS_USER` | Email Copernicus Data Space |
| `COPERNICUS_PASS` | Password Copernicus Data Space |

### Abilita GitHub Pages
Vai su **Settings → Pages** e imposta:
- Source: **GitHub Actions**

Il sito sarà disponibile su:
`https://ale2588.github.io/TerraWatch`

---

## Struttura del progetto

```
TerraWatch/
├── pipeline/
│   ├── sources/
│   │   ├── air_quality.py    ← AQICN
│   │   ├── temperature.py    ← ERA5 Copernicus
│   │   ├── sentinel.py       ← Sentinel-2
│   │   └── hydro_risk.py     ← ISPRA
│   ├── output/
│   │   └── writer.py         ← merge layer → JSON
│   ├── run.py                ← entry point pipeline
│   └── setup_meta.py         ← genera comuni.json
├── data/
│   ├── meta/
│   │   └── comuni.json       ← anagrafica 7.899 comuni
│   └── current/
│       ├── air_quality.json
│       ├── temperature.json
│       ├── sentinel.json
│       ├── hydro_risk.json
│       └── teri_full.json    ← merge finale per il sito
├── site/                     ← frontend statico
│   ├── index.html
│   ├── css/
│   └── js/
└── .github/
    └── workflows/
        ├── pipeline.yml      ← aggiornamento dati
        └── deploy.yml        ← deploy GitHub Pages
```

---

## Fonti e licenze

- **ISPRA** — dati pubblici, licenza CC BY 3.0 IT
- **AQICN** — dati pubblici con API token gratuito
- **ERA5 (Copernicus)** — dati pubblici, licenza Copernicus
- **Sentinel-2 (ESA/Copernicus)** — dati pubblici, licenza Copernicus
- **ISTAT** — confini comunali, licenza CC BY 3.0 IT

---

## Roadmap

- [ ] MVP: 4 layer, tutti i comuni
- [ ] Serie storica per comune (grafici trend)
- [ ] Alert su variazioni anomale
- [ ] Layer subsidenza (InSAR)
- [ ] Layer prezzi immobili OMI
- [ ] API pubblica

---

*Progetto open source — contribuzioni benvenute.*
