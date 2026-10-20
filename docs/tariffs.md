# Tarife editabile, TVA și configurare YellowGrid

[Înapoi la documentația principală](../README.md) · [English](tariffs.en.md)

## Alegerea modului de calcul

**Simplu** păstrează multiplicatorii și adaosurile originale. **Componente** folosește versiuni cu dată de intrare în vigoare, energie înainte de TVA, tarife individuale și TVA pentru fiecare. Setările celor două moduri sunt independente; un multiplicator simplu care include deja TVA nu trebuie copiat ca multiplicator de energie înainte de TVA.

Adaugă și salvează versiunea prin **Configurează → Versiuni tarifare și componente**, apoi activează **Componente** din meniul modului de calcul. Într-un HA în engleză: **Configure → Tariff versions and components**, apoi **Import pricing mode → Components**.

## Presetul YellowGrid

La adăugarea unei versiuni, alegerea inițială este **YellowGrid — estimare grafic 20 octombrie (editabil)**. Este necesară salvarea explicită a unei date și activarea modului Componente. Modurile goale și pe baza facturii rămân disponibile; versiunile existente nu sunt înlocuite automat.

| Câmp | Valoare inițială |
| --- | ---: |
| Plafon final import, cu tarife și TVA (`final_import_cap`) | `1.31` lei/kWh |
| Plafon energie importată înainte de TVA (`import_cap`) | `0.55` lei/kWh |
| Prag minim export (`export_floor`) | `0.50` lei/kWh |
| Comision (`commission`) | `25` % |
| Multiplicator / adaos energie | `1` / `0` |
| TVA energie | `21` % |

Plafonul final de **1,31 lei/kWh** și minimul de export de **0,50 lei/kWh** sunt parametrii confirmați de utilizator pentru configurația sa. Plafonul energiei active de 0,55 și comisionul de 25% pornesc din [oferta publică YellowGrid](https://www.yellowgrid.ro/legislatie-si-contracte), valabilă 1 septembrie–30 noiembrie 2026. Contractele pot avea alte condiții; toate valorile sunt editabile.

Cu `s = OPCOM lei/MWh / 1000` și `c = comision / 100`:

```text
energie importată = min(plafon_energie, s + (plafon_energie - s) × c)
bază înainte de TVA = energie importată × multiplicator + adaos
tarife suplimentare = suma componentelor activate
TVA = TVA bazei + TVA componentelor activate
total neplafonat = bază + tarife suplimentare + TVA
preț import = min(total neplafonat, plafon_final_import)
ajustare plafon = preț import - total neplafonat
preț export = max(prag_minim_export, prag_minim_export + (s - prag_minim_export) × (1 - c))
```

La setările inițiale, exportul peste prag este `0.75 × s + 0.125`. Exportul nu primește tarifele de rețea sau TVA ale importului. Plafonul final de import se aplică după calcularea tarifelor și taxelor; senzorii componentelor păstrează valorile configurate, iar ajustarea plafonului este afișată separat, fără inventarea unei repartizări fiscale a discountului furnizorului.

Versiunile YellowGrid salvate în v1.2.0 nu au plafon final. Pentru a-l aplica, editează versiunea, setează câmpul **Final import cap, including charges and VAT** la `1.31` și salvează; alternativ, adaugă o versiune nouă cu data potrivită.

## Componente și ipoteze

Fiecare componentă are nume, rată înainte de TVA în lei/kWh, TVA procentual, activare și marcaj de verificare a tratamentului TVA. Poți adăuga, edita sau elimina componente înainte de **Salvează versiunea**. Componentele dezactivate nu adaugă nici rată, nici TVA. Sunt acceptate TVA zero și rate negative pentru situațiile contractuale corespunzătoare.

Numele trebuie să fie distincte și necompletate cu spații goale. Sunt acceptate cel mult 100 de versiuni, fiecare cu maximum 50 de componente. Valorile trebuie să fie finite: TVA și multiplicatorii sunt între 0 și 100, ratele/adaosurile între -10000 și 10000, iar plafoanele și pragurile YellowGrid între 0 și 10000. Introdu `21` pentru TVA de 21%, nu `1.21`.

Presetul pe baza facturii din septembrie 2026 conține nouă componente, în total **0,4648832 lei/kWh înainte de TVA**. Distribuția IT/MT/JT însumează **0,31739**. Presetul pentru grafic folosește în schimb o singură componentă **Distribuție Delgaz (estimare grafic)** de **0,38791**, iar totalul componentelor sale este **0,5354032**. Acestea sunt două configurații alternative, nu tarife care se adună între ele.

Operatorul Delgaz este **neconfirmat pentru contract**. Un preț final plafonat nu permite deducerea operatorului sau a tuturor tarifelor subiacente. Alege ratele din contractul tău. Ambele exemple pornesc cu TVA de 21%; **TVA CfD este marcat neverificat**. O valoare rotunjită la zero pe factură nu dovedește o scutire. Nu sunt incluse facturi private, date de cont ori identificatori de contor.

## Date de intrare în vigoare

O versiune începe la miezul nopții în fusul orar HA și continuă până la următoarea versiune. Fiecare interval folosește versiunea aplicabilă la începutul său. Datele viitoare folosesc versiunile programate pentru viitor, inclusiv parametrii de export YellowGrid.

Pentru o perioadă nouă, adaugă o versiune; editarea unei versiuni îi schimbă configurația pentru perioada respectivă. Ștergerea salvează imediat eliminarea versiunii selectate și poate elimina acoperirea anterioară. Istoricul deja înregistrat în HA nu este rescris.

Fără o versiune aplicabilă, importul și defalcarea sunt indisponibile. În modul Componente, dacă există versiuni YellowGrid, exportul necesită de asemenea o versiune care acoperă intervalul; o versiune liniară aplicabilă folosește formula simplă de export. Dacă sunt configurate numai versiuni liniare, exportul păstrează formula simplă independentă. OPCOM angro rămâne disponibil separat. Planificarea exclude ferestrele neacoperite; nu le evaluează la zero.

## Defalcare și acțiuni

Senzorii separă baza înainte de TVA, tarifele suplimentare și TVA. Senzorul importului include `tariff_effective_from`, `energy_model`, `components`, `unverified_vat_components`, `uncapped_total`, `final_import_cap` dacă este configurat și `cap_adjustment`.

```text
base_energy + additional_charges + vat_amount + cap_adjustment = estimated_total
```

În exemplul Delgaz, cu energia plafonată la 0,55 și TVA de 21%, totalul neplafonat este **1,313337872**; plafonul final produce **1,31**, iar ajustarea este **-0,003337872 lei/kWh**. Cu componentele exemplului de factură, același plafon de energie produce un total neplafonat de **1,228008672**. Aceste rezultate explică de ce plafonul energiei active și plafonul total sunt câmpuri distincte.

`opcom_energy.get_prices` cu `price_type: import` returnează aceeași defalcare pe interval. Un interval neacoperit are `price: null`, `unavailable_reason: no_tariff` și contribuie la `complete: false`. Consumatorii trebuie să verifice atât completitudinea, cât și valorile nule. Graficele exemplului citesc direct aceste acțiuni, fără recalcularea tarifelor în browser.

## Comparația cu graficul din 20 octombrie 2026

Cele 96 de intervale ale zilei locale au fost comparate cu barele YellowGrid. Importul configurat rămâne **1,31 lei/kWh**. Exportul are maximul de **2,00** la 09:00 și minimul de **0,9259925** la 16:00, în `Europe/Bucharest`. Diferența aproximativă dintre exportul calculat și citirea pixelilor din ultima captură a fost 0,0034 lei/kWh RMS, cu maximum 0,009; imaginea nu confirmă egalitatea dincolo de precizia vizibilă.

Acestea sunt estimări marginale pe kWh. Abonamentele fixe, energia efectiv măsurată, decontarea lunară, descoperirea automată a tarifelor și comanda echipamentelor nu fac parte din acest calcul.
