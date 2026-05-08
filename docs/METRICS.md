# Przemielimy Raid Analyzer - Dokumentacja metryk

## Wspólne kolumny (wszystkie arkusze)

| Kolumna | Opis |
|---------|------|
| Report | Kod raportu z Warcraft Logs (np. w4RzL9h6ZCyGpJNd) |
| Date | Data i godzina rozpoczęcia raportu |
| Boss | Nazwa bossa |
| Pull # | Numer pulla na danego bossa w ramach raportu (1, 2, 3...) |
| Result | Wynik walki: "Kill" lub "Wipe (XX%)" |
| Boss HP % | Procent HP bossa na koniec walki. 0 = kill, np. 45.2 = wipe na 45.2% |
| Duration (s) | Czas trwania walki w sekundach |

---

## Performance (DPS / HPS)

**Źródło danych:** WCL API `table(dataType: DamageDone)` i `table(dataType: Healing)`

| Kolumna | Opis |
|---------|------|
| Player | Nazwa postaci |
| Class | Klasa postaci (Warrior, Mage, itp.) |
| Spec | Specjalizacja (Frost, Fire, itp.) |
| Type | "DPS" lub "HPS" |
| Total | Łączny damage/healing w walce (surowa wartość) |
| Per Second | Damage/healing per second (Total / czas walki) |
| Active % | Procent czasu walki w którym gracz aktywnie zadawał obrażenia/leczył |

### Jak DPS/HPS jest liczone?

**DPS (Damage Done):**
- To **sumaryczny damage gracza** przypisany do niego w logach
- **Tak, uwzględnia korzyści z zewnętrznych buffów** (Power Infusion, Bloodlust, itp.) - ale damage jest przypisany do gracza który go zadał, nie do buffującego
- Obejmuje: bezpośredni damage, DoTy, damage z petów (przypisany do ownera)
- Nie obejmuje: damage z augmentation evokerów (ten jest osobną kategorią)

**HPS (Healing Done):**
- Sumaryczny healing gracza
- Obejmuje: bezpośredni heal, HoTy, absorb shieldy (np. Power Word: Shield)
- **Overheal NIE jest wliczany** - to effective healing
- Heale z petów/tottemów są przypisane do ownera

### Ograniczenia
- Active % może być mylący dla klas z DoTami (mają wysoki active% nawet przy ruchu)
- DPS na wipe'ach krócej niż ~30s może być zawyżony (burst na pullu)

---

## Deaths

**Źródło danych:** WCL API `table(dataType: Deaths)`

| Kolumna | Opis |
|---------|------|
| Player | Nazwa postaci która zginęła |
| Class | Klasa postaci |
| Death Time (s) | Sekunda walki w której nastąpiła śmierć (liczbowo, do wykresów) |
| Death Time | Czas śmierci w formacie M:SS (czytelny) |
| Killing Blow | Nazwa umiejętności która zadała ostatni cios |

### Zastosowania
- Kto umiera najczęściej per boss?
- Kiedy w walce ludzie umierają? (faza 1 vs faza 3)
- Od czego umierają? (mechanika bossa vs brak healingu)

---

## Interrupts

**Źródło danych:** WCL API `table(dataType: Interrupts)`

| Kolumna | Opis |
|---------|------|
| Player | Gracz który przerwał cast |
| Class | Klasa postaci |
| Type | Zawsze "Interrupt" |
| Count | Ilość udanych interruptów w walce |

### Uwagi
- Zliczane są TYLKO udane interrupty (nie próby)
- Obejmuje wszystkie umiejętności przerywające (kick, pummel, wind shear, itp.)
- Nie rozróżnia które caste zostały przerwane

---

## Dispels

**Źródło danych:** WCL API `table(dataType: Dispels)`

| Kolumna | Opis |
|---------|------|
| Player | Gracz który zdispellował |
| Class | Klasa postaci |
| Type | Zawsze "Dispel" |
| Count | Ilość udanych dispelli w walce |

### Uwagi
- Obejmuje dispelle offensywne (purge) i defensywne (decurse)
- Nie rozróżnia co zostało zdispellowane

---

## Consumables

**Źródło danych:** WCL API `events(dataType: Casts)` z filtrem na spell ID

Kolumny kategorii (Combat Pot, Health Pot, itp.) są **dynamiczne** - generowane z zakładki "Config: Consumables".

| Kolumna | Opis |
|---------|------|
| Player | Nazwa postaci |
| Class | Klasa postaci |
| Combat Pot | Ilość użytych combat potionów (DPS potki) |
| Health Pot | Ilość użytych healing potionów |
| Healthstone | Ilość użytych healthstone'ów |
| Mana Pot | Ilość użytych mana potionów |

### Jak to działa?
- Spell ID consumabli są zdefiniowane w zakładce **Config: Consumables** w arkuszu
- Każdy spell ID ma przypisaną kategorię (Combat Pot, Health Pot, itp.)
- Skrypt zlicza casty per gracz per kategoria per fight
- Żeby dodać nowy consumable: edytuj zakładkę Config, dodaj wiersz z Spell ID, Name, Category

### Ograniczenia
- Zlicza TYLKO casty ze znanych spell ID - jeśli brakuje ID w configu, cast nie będzie policzony
- Oba ranki jakości (Tier 1 / Tier 2) mają ten sam spell ID w Midnight
- Healthstone (spell 6262) jest uniwersalny niezależnie od talentów warlocka

---

## Defensives

**Źródło danych:** WCL API `events(dataType: Casts)` z filtrem na spell ID

| Kolumna | Opis |
|---------|------|
| Player | Gracz który użył defensywnego cooldownu |
| Class | Klasa postaci |
| Ability | Nazwa użytej umiejętności (np. "Ice Block", "Pain Suppression") |
| Count | Ilość użyć w walce |

### Kategorie (w Config: Defensives)
- **External** - defensywne umiejętności rzucane NA innych (Pain Suppression, Ironbark, itp.)
- **Personal** - osobiste defensywne (Ice Block, Barkskin, itp.)

### Ograniczenia
- Zlicza casty, nie czas trwania buffa
- Żeby dodać nowy defensywny cooldown: edytuj zakładkę Config: Defensives

---

## Attendance

**Źródło danych:** WCL API `guild.attendance`

| Kolumna | Opis |
|---------|------|
| Report | Kod raportu |
| Date | Data raportu |
| Zone | Nazwa raidu/instancji |
| Player | Nazwa postaci |
| Class | Klasa |
| Presence | Wartość obecności (0-1 lub inna skala z API) |
| Presence % | Procent obecności w raporcie |

### Uwagi
- Wymaga flagi `--attendance` przy uruchomieniu
- Dane pochodzą z endpointu gildii, nie z poszczególnych raportów

---

## Config: Consumables

Zakładka konfiguracyjna - edytowalna w Google Sheets.

| Kolumna | Opis |
|---------|------|
| Spell ID | ID zaklęcia z WoW (widoczne w Warcraft Logs / Wowhead) |
| Name | Nazwa przedmiotu/zaklęcia (informacyjna) |
| Category | Kategoria do grupowania (np. "Combat Pot", "Healthstone") |

Dodanie nowego wiersza = skrypt automatycznie zacznie śledzić ten consumable.

---

## Config: Defensives

Identyczna struktura jak Config: Consumables.

| Kolumna | Opis |
|---------|------|
| Spell ID | ID zaklęcia defensywnego |
| Name | Nazwa umiejętności |
| Category | "External" lub "Personal" (lub dowolna inna kategoria) |

---

## Źródła danych i tokeny API

### Koszt per fight (7 queries):
1. DamageDone table (~1-3 pkt)
2. Healing table (~1-3 pkt)
3. Interrupts table (~1-3 pkt)
4. Dispels table (~1-3 pkt)
5. Deaths table (~1-3 pkt)
6. Consumable events (~1-3 pkt)
7. Defensive events (~1-3 pkt)

### Limit API: 3600 punktów/godzinę
- 1 raport z 20 fightami ≈ ~200-350 punktów
- 5 raportów ≈ ~1000-1750 punktów
- Bezpiecznie: do ~10 raportów na godzinę
