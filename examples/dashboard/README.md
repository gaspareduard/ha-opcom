# Dashboard „Prețuri OPCOM”

[Documentația principală](../../README.md) · [Configurare YellowGrid](../../docs/tariffs.md)

Exemplu opțional, separat de instalarea integrării: trei prețuri curente și două grafice, **Astăzi** și **Mâine**. Importul este reprezentat prin bare turcoaz deschis, exportul prin bare turcoaz închis, iar OPCOM angro printr-o linie mov. Toate folosesc lei/kWh.

## Instalare

1. Configurează integrarea **OPCOM Energy v1.2.2+**, salvează tariful YellowGrid și activează modul Componente. Activează și senzorul de export.
2. Instalează **ApexCharts Card** din HACS dacă nu este deja disponibil și verifică înregistrarea resursei sale ca modul JavaScript.
3. Copiază [opcom-price-bars-card.js](opcom-price-bars-card.js) în `/config/www/opcom-price-bars-card.js` pe HA. Creează directorul `www` dacă lipsește.
4. În **Setări → Dashboarduri → Resurse**, adaugă `/local/opcom-price-bars-card.js?v=1`, tip **JavaScript module**. Lista de resurse poate necesita activarea modului avansat în profilul HA.
5. Creează un dashboard gol în modul stocare, cu titlul **Prețuri OPCOM** și o adresă precum `opcom-prices`. Deschide editorul configurației brute și copiază conținutul din [dashboard.json](dashboard.json). JSON este acceptat ca sintaxă YAML.
6. Verifică ID-urile entităților de mai jos și adaptează-le instalării tale. Reîncarcă pagina și verifică cele două grafice.

Exemplul folosește ID-urile generate într-un HA configurat inițial în engleză:

- `sensor.opcom_energy_estimated_import_price`
- `sensor.opcom_energy_estimated_export_price`
- `sensor.opcom_energy_spot_price`
- `sensor.opcom_energy_last_successful_fetch`
- `binary_sensor.opcom_energy_source_available`
- `binary_sensor.opcom_energy_tomorrow_schedule_complete`

Înlocuiește ID-urile din JSON dacă diferă. Pentru ID-urile folosite de adaptorul graficului, adaugă opțiunea `entities` la fiecare dintre cele două carduri, cu valorile reale:

```yaml
type: custom:opcom-price-bars-card
title: Astăzi
day_offset: 0
entities:
  spot: sensor.opcom_energy_spot_price
  import: sensor.opcom_energy_estimated_import_price
  last_fetch: sensor.opcom_energy_last_successful_fetch
```

Pentru mâine, folosește `day_offset: 1`. Numele vizibile din dashboard sunt în română chiar dacă HA are interfața în engleză. Identificatorii și unitatea standard a senzorilor nu sunt redenumite.

## Cum funcționează

Cardul citește `opcom_energy.get_prices` pentru tipurile `import`, `export` și `spot`. Folosește prețurile calculate de integrare, nu o formulă duplicată în JavaScript. Modificările tarifare viitoare, TVA și plafoanele rămân astfel în responsabilitatea integrării.

Graficul folosește fusul orar HA, nu fusul orar al telefonului. Limitele zilei sunt calculate separat, inclusiv la trecerile la ora de vară/iarnă. Valorile lipsă rămân nule; un program parțial este etichetat explicit. Lipsa publicării pentru mâine nu este înlocuită cu prețurile de azi.

Actualizarea are loc la schimbarea datelor relevante și cel puțin o dată la aproximativ cinci minute cât pagina este deschisă. Datele provin din cache-ul validat al integrării; cardul nu contactează OPCOM, nu stochează credențiale și nu comandă echipamente.

După modificarea fișierului JavaScript, schimbă versiunea din adresa resursei, de exemplu `?v=2`, și reîncarcă pagina. Pentru probleme de încărcare, verifică resursele și disponibilitatea acțiunii `opcom_energy.get_prices`.

## English quick start

Install OPCOM Energy v1.2.2+ and ApexCharts Card. Copy the JavaScript file to `/config/www/`, register `/local/opcom-price-bars-card.js?v=1` as a module, create a storage dashboard and paste `dashboard.json` into its raw configuration editor. Replace entity IDs if your installation uses different ones; each chart supports an optional `entities` map as shown above. The dashboard reads authoritative backend schedules for today and tomorrow; it does not recalculate tariffs or issue equipment commands.
