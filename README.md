# OPCOM Energy — prețuri OPCOM și tarife YellowGrid pentru Home Assistant

[![Validare](https://github.com/gaspareduard/ha-opcom/actions/workflows/validate.yaml/badge.svg)](https://github.com/gaspareduard/ha-opcom/actions/workflows/validate.yaml)
[![Versiune](https://img.shields.io/github/v/release/gaspareduard/ha-opcom)](https://github.com/gaspareduard/ha-opcom/releases)
[![Licență MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<img src="custom_components/opcom_energy/brand/icon.png" alt="Grafic de prețuri și simbol electric OPCOM Energy" width="96">

Prețuri PZU din România, descărcate direct de la **OPCOM**, cu senzori pentru import/export, tarife editabile și planificarea celor mai ieftine intervale. Documentația principală este în română; [English documentation](README.en.md) este disponibilă separat.

**Necesită Home Assistant 2026.10.0 sau mai nou.** Gratuită, cu licență MIT, fără cont, activare, telemetrie sau server de licențiere. Proiect independent, neafiliat OPCOM sau YellowGrid.

## Instalare prin HACS

[![Deschide integrarea în HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gaspareduard&repository=ha-opcom&category=integration)

1. Deschide **HACS → ⋮ → Custom repositories**.
2. Adaugă `https://github.com/gaspareduard/ha-opcom`, categoria **Integration**.
3. Descarcă **OPCOM Energy** și repornește Home Assistant.
4. Deschide **Setări → Dispozitive și servicii → Adaugă integrare → OPCOM Energy**.
5. Configurează tariful prin **Configurează**. Într-o interfață HA în engleză, butoanele se numesc **Settings → Devices & services → Configure**.

Repository-ul personalizat HACS este public și poate fi folosit imediat. Includerea în catalogul implicit HACS este un proces separat. Pentru instalare manuală, copiază `custom_components/opcom_energy` în directorul `custom_components` al HA, apoi repornește și adaugă integrarea din interfață.

Identificatorul integrării este `opcom_energy`. Poate coexista cu alte integrări OPCOM, fără migrarea automată a entităților lor.

## Configurare YellowGrid

Începând cu v1.2.2, sunt disponibile modelul YellowGrid cu plafon și prag minim, precum și descărcări OPCOM fără reutilizarea cookie-urilor care pot provoca erori HTTP 403.

1. Deschide **Configurează → Versiuni tarifare și componente → Adaugă versiune tarifară**.
2. Alege explicit **data de început** și presetul **YellowGrid — estimare grafic 20 octombrie (editabil)**. În interfața engleză: **Tariff versions and components → Add tariff version → YellowGrid — 20 October chart estimate (editable)**.
3. Verifică parametrii de mai jos, apoi tarifele de rețea și TVA pentru fiecare componentă.
4. Alege **Salvează versiunea**. Redeschide configurarea și selectează **Modul de calcul al importului → Componente**; în engleză, **Import pricing mode → Components**.
5. Activează **Preț estimat export / Estimated export price** din lista entităților integrării: senzorul este dezactivat implicit.

| Parametru | Valoare inițială | Semnificație |
| --- | ---: | --- |
| Plafon final import | `1.31` lei/kWh | Limita totalului, după tarife și TVA |
| Prag minim export | `0.50` lei/kWh | Limita inferioară a prețului de export |
| Comision furnizor | `25` % | Folosit în modelul de import și export |
| Plafon energie importată înainte de TVA | `0.55` lei/kWh | Parametru separat al componentei de energie |
| Multiplicator / adaos energie | `1` / `0` | Ajustări înainte de TVA |
| TVA energie | `21` % | Editabil; componentele au fiecare propriul TVA |

**Plafonul de 1,31 se aplică prețului final, nu prețului OPCOM angro.** Pragul de 0,50 este un minim de export; prețul poate fi mai mare. La setările inițiale, exportul peste prag este `0.75 × OPCOM + 0.125` lei/kWh.

Presetul pentru grafic include o componentă **Distribuție Delgaz (estimare grafic)**, editabilă și neconfirmată pentru contractul utilizatorului. Un grafic plafonat nu identifică operatorul de distribuție. Presetul separat **factură septembrie 2026** păstrează ratele exemplului de factură. Verifică operatorul, tarifele și TVA aplicabile contractului; **TVA CfD rămâne marcat neverificat**.

Toate versiunile încep la **miezul nopții în fusul orar HA**, de exemplu `Europe/Bucharest`. Intervalele fără o versiune aplicabilă au preț estimat indisponibil. Datele OPCOM angro rămân separate. Pentru modificări viitoare, adaugă o versiune cu data nouă, păstrând perioadele anterioare.

Versiunile salvate în v1.2.0 nu primesc automat plafonul final: editează versiunea, setează **Final import cap, including charges and VAT** la `1.31` și salvează. Actualizările păstrează setările existente.

[Ghid complet: tarife, formule, TVA și date de intrare în vigoare](docs/tariffs.md).

## Senzori disponibili

| Senzor | Ce afișează |
| --- | --- |
| Preț spot / următorul preț spot | OPCOM angro în lei/kWh, fără ajustările furnizorului |
| Preț estimat import | Totalul calculat cu tarifele și plafonul configurate |
| Preț estimat export | Estimarea cu propriul comision și prag minim |
| Energie importată / tarife suplimentare / TVA | Defalcarea importului, disponibilă în modul Componente |
| Media / minimul / maximul de astăzi | Statistici OPCOM pentru ziua locală completă |
| Media de mâine | Statistici și programul publicat pentru ziua locală următoare |
| Percentila prețului | Poziția prețului spot curent în programul zilei |
| Cea mai ieftină fereastră viitoare | Începutul și prețul mediu al ferestrei continue de import |
| Ultima descărcare reușită | Diagnostic al sursei de date |

Senzorii binari indică disponibilitatea sursei, publicarea completă pentru mâine, prețul sub pragul configurat și intervalele ieftine după percentila spot. Prețul în lei/MWh este disponibil ca entitate dezactivată implicit.

Numele entităților urmează limba HA. ID-urile efective pot diferi: alege-le din lista entităților, în loc să presupui că un exemplu are aceleași ID-uri în orice instalare.

## Dashboard: bare YellowGrid și linie OPCOM

Exemplul [Prețuri OPCOM](examples/dashboard/README.md) afișează:

- prețurile curente de import, export și OPCOM angro;
- grafice separate **Astăzi** și **Mâine**, cu import/export ca bare și OPCOM ca linie;
- orele locale, starea publicării și intervalele de 15 minute;
- datele calculate de integrare, inclusiv versiunile tarifare viitoare, fără duplicarea formulelor în grafic.

Dashboardul este opțional și se instalează separat, cu **ApexCharts Card**. Nu este creat automat de instalarea integrării prin HACS. [Fișiere și instrucțiuni](examples/dashboard/README.md).

## Modul simplu

Modul **Simplu** rămâne implicit și păstrează formulele originale:

```text
spot = OPCOM lei/MWh / 1000
import = spot × multiplicator_import + adaos_import
export = spot × multiplicator_export + adaos_export
```

Implicit, multiplicatorii sunt 1 și adaosurile 0: prețurile sunt angro. Modul simplu nu adaugă automat TVA, tarife, plafonul YellowGrid sau pragul de export. Schimbarea modului nu șterge versiunile tarifare salvate.

## Acțiuni pentru programe și planificare

```yaml
action: opcom_energy.get_prices
data:
  date: "2026-10-20"
  price_type: import
response_variable: preturi
```

Acțiunea returnează intervalele din cache, cu marcaje temporale complete, unitate, monedă și `complete`. Tipul poate fi `spot`, `import` sau `export`; implicit este `spot`. Pentru importul pe componente, fiecare interval include `breakdown`. Lipsa acoperirii tarifare produce `price: null` și `unavailable_reason: no_tariff`; verifică întotdeauna `complete` și valorile nule.

```yaml
action: opcom_energy.get_cheapest_window
data:
  duration_minutes: 120
  price_type: import
response_variable: fereastra
```

Durata acceptată este 15–1440 minute, în multipli de 15. Opțional, `earliest_start` și `latest_end` sunt marcaje ISO cu fus orar; căutarea este limitată la 72 de ore. Fereastra trebuie să fie continuă și completă. La egalitate este aleasă prima. Senzorii de planificare folosesc importul; acțiunea folosește implicit spotul dacă nu specifici tipul.

Acțiunile citesc date validate deja disponibile. Integrarea nu comandă baterii sau consumatori și nu include pierderile bateriei, degradarea ori prognoza solară în optimizare.

## Fus orar, publicare și întreruperi

Ziua de piață OPCOM urmează CET/CEST (`Europe/Berlin`). Zilele afișate în HA sunt asamblate în fusul orar configurat în HA. În România, ziua de piață începe la 01:00 local. Schimbarea orei păstrează corect toate cele 92/96/100 de intervale distincte.

Senzorii se actualizează la fiecare sfert de oră. Descărcările sunt partajate între entități; zilele lipsă sunt reîncercate cu pauze progresive. Datele publicate sunt reverificate periodic și păstrate prin stocarea administrată de HA. O conexiune întreruptă nu extinde prețul unui interval expirat. „Mâine complet” se activează numai când este acoperită întreaga zi locală.

## Diagnosticare și dezvoltare

Din integrare poți descărca diagnostice și activa temporar jurnalizarea detaliată. Diagnosticele includ parametrii tarifari și starea sursei; nu publica date de cont, identificatori de contor sau tokenuri HA. Dacă folosești integrarea în panoul Energie, selectează prețul estimat doar după verificarea contractului configurat.

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=custom_components.opcom_energy --cov-report=term-missing
# Verificare opțională, care contactează OPCOM:
PYTHONPATH=. uv run python scripts/check_live_source.py
```

CI verifică testele, Ruff, Hassfest și HACS. Vezi [contribuții](CONTRIBUTING.md), [istoricul versiunilor](CHANGELOG.md) și [documentația completă în engleză](README.en.md). Pentru eliminare, șterge integrarea din Dispozitive și servicii, elimină descărcarea HACS și repornește HA.

Autor: **Eduard Gaspar** — [gaspareduard](https://github.com/gaspareduard). Sursa datelor: [OPCOM](https://www.opcom.ro); sursa modelului de ofertă: [YellowGrid](https://www.yellowgrid.ro/legislatie-si-contracte). Codul și grafica originală sunt publicate sub [licența MIT](LICENSE).
