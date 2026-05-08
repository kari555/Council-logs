# Looker Studio Dashboard Setup

## Krok 1: Przygotuj dane
Uruchom skrypt z kilkoma raportami żeby mieć dane do pracy:
```
python main.py --reports 5
```

## Krok 2: Utwórz raport w Looker Studio
1. Wejdź na https://lookerstudio.google.com
2. Kliknij **Create → Report**
3. **Add data source → Google Sheets**
4. Wybierz swój arkusz → zakładkę **Performance**
5. Kliknij **Add** → **Add to report**

## Krok 3: Dodaj pozostałe źródła danych
1. **Resource → Manage added data sources → Add a data source**
2. Powtórz dla zakładek: **Interrupts**, **Dispels**, **Consumables**, **Defensives**
3. Każda zakładka = osobne źródło danych

## Krok 4: Konfiguracja typów kolumn
Dla każdego źródła danych (Resource → Manage added data sources → Edit):

### Performance
| Kolumna | Typ |
|---------|-----|
| Report | Text |
| Date | Date & Time |
| Boss | Text |
| Pull # | Number |
| Result | Text |
| Boss HP % | Number |
| Duration (s) | Number |
| Player | Text |
| Class | Text |
| Spec | Text |
| Type | Text (DPS/HPS) |
| Total | Number |
| Per Second | Number |
| Active % | Number (Percent) |

### Interrupts / Dispels
| Kolumna | Typ |
|---------|-----|
| Report | Text |
| Date | Date & Time |
| Boss | Text |
| Pull # | Number |
| Result | Text |
| Boss HP % | Number |
| Duration (s) | Number |
| Player | Text |
| Class | Text |
| Type | Text |
| Count | Number |

### Consumables
| Kolumna | Typ |
|---------|-----|
| Report | Text |
| Date | Date & Time |
| Boss | Text |
| Pull # | Number |
| Result | Text |
| Boss HP % | Number |
| Duration (s) | Number |
| Player | Text |
| Class | Text |
| Combat Pot | Number |
| Health Pot | Number |
| Healthstone | Number |
| Mana Pot | Number |

### Defensives
| Kolumna | Typ |
|---------|-----|
| Report | Text |
| Date | Date & Time |
| Boss | Text |
| Pull # | Number |
| Result | Text |
| Boss HP % | Number |
| Duration (s) | Number |
| Player | Text |
| Class | Text |
| Ability | Text |
| Count | Number |

---

# STRONA 1: Raid Analysis

## Filtry (góra strony)
Dodaj kontrolki filtrów (Add a control → Drop-down list):
1. **Date range** - Add a control → Date range control
2. **Boss** - Drop-down, Dimension: Boss (z Performance)
3. **Result** - Drop-down, Dimension: Result
4. **Player** - Drop-down, Dimension: Player (multi-select)

## Wykresy

### 1. DPS Ranking (Bar chart)
- Chart type: **Bar chart (horizontal)**
- Data source: Performance
- Dimension: Player
- Metric: Per Second (AVG)
- Filter: Type = "DPS"
- Sort: Per Second DESC

### 2. HPS Ranking (Bar chart)
- Chart type: **Bar chart (horizontal)**
- Data source: Performance
- Dimension: Player
- Metric: Per Second (AVG)
- Filter: Type = "HPS"
- Sort: Per Second DESC

### 3. Interrupts per Player (Bar chart)
- Chart type: **Bar chart (horizontal)**
- Data source: Interrupts
- Dimension: Player
- Metric: Count (SUM)
- Sort: Count DESC

### 4. Dispels per Player (Bar chart)
- Chart type: **Bar chart (horizontal)**
- Data source: Dispels
- Dimension: Player
- Metric: Count (SUM)
- Sort: Count DESC

### 5. Consumable Usage (Table with heatmap)
- Chart type: **Table with heatmap**
- Data source: Consumables
- Dimensions: Player, Class
- Metrics: Combat Pot (SUM), Health Pot (SUM), Healthstone (SUM), Mana Pot (SUM)
- Conditional formatting: 0 = red, >0 = green

### 6. Defensive Usage (Table)
- Chart type: **Table**
- Data source: Defensives
- Dimensions: Player, Class, Ability
- Metric: Count (SUM)
- Sort: Player ASC

---

# STRONA 2: Guild Progress

Dodaj nową stronę: Page → New page

## Filtry
1. **Boss** - Drop-down (single select)
2. **Date range** - Date range control

## Wykresy

### 1. Boss Progress Timeline (Scatter / Combo chart)
- Chart type: **Combo chart** (line + points)
- Data source: Performance
- Dimension: Date
- Breakdown dimension: Boss
- Metric: Boss HP % (MIN per pull - najlepszy wynik sesji)
- Pokaż trend spadający HP% = postęp na bossie
- Dodaj adnotację na Kill (Boss HP % = 0)

### 2. Best Wipe % per Session (Line chart)
- Chart type: **Line chart**
- Data source: Performance
- Dimension: Date
- Metric: Boss HP % (MIN)
- Filter: Result contains "Wipe"
- Trend powinien spadać w kierunku 0

### 3. Pull Count per Boss (Bar chart)
- Chart type: **Bar chart (vertical)**
- Data source: Performance
- Dimension: Boss
- Metric: Pull # (MAX) - ile pullów na bossa
- Filter: Type = "DPS" (żeby nie dubować z HPS)
- Sort: Pull # DESC

### 4. Average Raid DPS Trend (Line chart)
- Chart type: **Line chart**
- Data source: Performance
- Dimension: Date
- Metric: Per Second (AVG)
- Filter: Type = "DPS"
- Breakdown: Boss (opcjonalnie)

### 5. Fight Duration Trend (Line chart)
- Chart type: **Line chart**
- Data source: Performance
- Dimension: Pull #
- Metric: Duration (s) (AVG)
- Filter: Boss = wybrany boss
- Trend: powinien rosnąć (dłuższe fighty = dalej w mechanikach)

### 6. Kill Times Comparison (Bar chart)
- Chart type: **Bar chart**
- Data source: Performance
- Dimension: Boss
- Metric: Duration (s) (AVG)
- Filter: Result = "Kill"

---

# Tips
- Ustaw theme ciemny (Theme → Customize → Dark)
- Dodaj logo gildii jako obrazek
- Udostępnij dashboard gildii: Share → Get link → Anyone with link can view
- Dane odświeżają się automatycznie co 15 minut (lub ręcznie: Data → Refresh)
