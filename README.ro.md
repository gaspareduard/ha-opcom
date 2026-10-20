# OPCOM Energy pentru Home Assistant

Integrare independentă pentru prețurile angro PZU din România, descărcate direct de la OPCOM. Gratuită, cu cod sursă sub licență MIT. Fără cont, cheie de activare sau server de licențiere. Necesită **Home Assistant 2026.10.0+**.

## Instalare HACS

1. HACS → ⋮ → Custom repositories.
2. Adaugă `https://github.com/gaspareduard/ha-opcom`, categoria **Integration**.
3. Descarcă **OPCOM Energy** și repornește Home Assistant.
4. Settings → Devices & services → Add integration → **OPCOM Energy**.
5. Folosește **Configure → Setări simple și planificare** pentru formulele originale. Modul opțional pe componente se configurează separat.

Este disponibilă tuturor prin repository personalizat HACS. Includerea în catalogul implicit depinde separat de evaluarea HACS. Poate coexista cu integrarea `opcom`; nu îi schimbă senzorii sau setările.

## Senzori și tarife

Oferă prețul spot curent/următor, preț estimat import/export, media/minimul/maximul zilei locale, media de mâine, percentila, cea mai ieftină fereastră viitoare și diagnostice. Prețul de export și prețul în RON/MWh sunt dezactivate implicit și pot fi activate din lista entităților.

```text
spot RON/kWh = OPCOM RON/MWh / 1000
preț import = spot × multiplicator import + adaos import
preț export = spot × multiplicator export + adaos export
```

Adaosurile sunt în RON/kWh. Implicit multiplicatorul este 1, iar adaosul 0. Nu se presupun TVA, tarife de distribuție, marje, plafonări sau condiții de compensare. Introdu parametrii contractului tău. Prețul angro negativ nu înseamnă automat preț final negativ. Integrarea nu transformă un contract fix într-un contract dinamic.

Ziua de piață este CET/CEST; ziua locală este cea din setările HA. Sunt păstrate corect toate cele 92/96/100 de intervale de 15 minute. Programul de mâine este marcat complet doar când acoperă integral ziua locală. Lipsa publicării nu afectează datele de azi.

Datele validate sunt păstrate între reporniri. Senzorii se actualizează la fiecare sfert de oră independent de descărcare. La întreruperea conexiunii se folosesc doar intervalele originale încă valabile; datele expirate nu sunt prelungite.

## Acțiuni

- `opcom_energy.get_prices`: intervalele unei zile locale; acceptă `date` și `price_type` (`spot`, `import`, `export`). Verifică întotdeauna câmpul `complete`.
- `opcom_energy.get_cheapest_window`: cea mai ieftină fereastră continuă viitoare. Acceptă durata în multipli de 15 minute, tipul prețului și opțional început/sfârșit ISO cu fus orar. Nu unește intervale lipsă și nu comandă echipamente.

Ferestrele senzorilor folosesc formula de import; acțiunea folosește implicit prețul spot. Pierderile/degradarea bateriei, prognoza solară și confortul termic nu sunt incluse în optimizarea după preț.

Pentru exemple, diagnosticare, semantica fiecărui senzor și dezvoltare, consultă [documentația completă în engleză](README.md). Configurarea și numele entităților sunt disponibile și în română.

Autor: **Eduard Gaspar** — [gaspareduard](https://github.com/gaspareduard). Proiect neafiliat OPCOM. Sursa datelor: [OPCOM](https://www.opcom.ro).

## Tarife pe componente în v1.1

Modul simplu rămâne implicit, cu aceleași rezultate și setări. Pentru tarife editabile, alege **Configure → Versiuni tarifare și componente → Adaugă versiune**. Alege explicit data de început și valori inițiale goale sau modelul facturii din septembrie 2026. Setează energia înainte de TVA, editează componentele și TVA pentru fiecare, apoi **Salvează versiunea**. Activează calculul prin **Modul de calcul al importului → Componente**.

Energia înainte de TVA este OPCOM × multiplicator + adaos. La aceasta se adaugă componentele active și TVA aferentă energiei și fiecărei componente. Setările sunt separate de modul simplu, astfel încât TVA să nu fie aplicată de două ori. Importul, exportul și prețul angro rămân distincte.

Fiecare versiune intră în vigoare la miezul nopții în fusul orar HA și se aplică la începutul fiecărui interval, până la următoarea versiune. Poți programa modificări viitoare. Fără o versiune aplicabilă, totalul estimat este indisponibil; prețul OPCOM rămâne disponibil.

Modelul facturii are componente de 0.4648832 RON/kWh înainte de TVA și TVA inițială editabilă de 21%. TVA CfD este marcată neverificată. Valorile sunt orientative, nu un tarif universal YellowGrid. Nu se aplică automat plafoane sau comisioane specifice contractului.

Senzorii suplimentari afișează energia înainte de TVA, tarifele suplimentare și TVA. Atributele totalului și răspunsurile acțiunii `get_prices` pentru import includ defalcarea. Intervalele fără acoperire tarifară au `price: null`, motivul `no_tariff` și `complete: false`. Planificarea nu le tratează drept zero și nu le unește peste goluri.
