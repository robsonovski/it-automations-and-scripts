# 🛠 IT Automations & Production Scripts

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![n8n workflow](https://img.shields.io/badge/n8n-automation-orange.svg)](https://n8n.io/)
[![Cloud: OCI](https://img.shields.io/badge/cloud-Oracle%20OCI-red.svg)](https://www.oracle.com/cloud/)
[![OS: Linux](https://img.shields.io/badge/OS-Linux%20Mint%20%7C%20Ubuntu-brightgreen.svg)](https://linuxmint.com/)

Zbiór skryptów automatyzacyjnych, produkcyjnych pipeline'ów orkiestracji (n8n) oraz narzędzi infrastrukturalnych przygotowanych pod kątem niezawodności, eliminacji powtarzalnych zadań i monitoringu procesów w czasie rzeczywistym.

---

## 📁 Zawartość repozytorium

### 1. `cloud_instance_provisioner.py` (Python 3 + OCI SDK)
Autonomiczne narzędzie CLI do automatyzacji wdrożeń i provisioningu maszyn wirtualnych w chmurze Oracle Cloud Infrastructure (OCI):
* **Dynamiczny discovery zasobów:** automatycznie przeszukuje i mapuje dostępne wirtualne sieci chmurowe (VCN) oraz filtruje publiczne podsieci bez blokady IP (`prohibit_public_ip_on_vnic`).
* **Wyszukiwanie obrazów OS:** pobiera najnowszy stabilny obraz Canonical Ubuntu 22.04 LTS dedykowany dla architektury ARM (`aarch64` / VM.Standard.A1.Flex).
* **Odporność na "Out of host capacity":** implementuje mechanizm retry loop z konfigurowalnym interwałem czasowym, co pozwala na bezobsługowe oczekiwanie na zwolnienie zasobów w danym Availability Domain.
* **Weryfikacja cyklu życia:** odpytuje API o stan instancji (`lifecycle_state == 'RUNNING'`), weryfikuje przypisanie karty sieciowej (VNIC) i ekstrahuje publiczny adres IPv4.
* **Integracja z systemem hosta:** wysyła desktopowe powiadomienia w środowisku Linux (`notify-send`) z informacją o powodzeniu operacji.

#### Uruchomienie i log z wykonania:
```bash
# Instalacja zależności
pip install -r requirements.txt

# Sprawdzenie parametrów CLI
python cloud_instance_provisioner.py --help

# Uruchomienie z domyślną konfiguracją OCI (~/.oci/config)
python cloud_instance_provisioner.py --name "worker-node-01" --ocpus 4 --memory-in-gbs 24
```

![Log wykonania skryptu CLI](assets/python_cli_execution.png)

---

### 2. `n8n_error_alerting_workflow.json` (Orkiestracja integracji n8n)
Produkcyjny scenariusz centralnego monitoringu, obsługi wyjątków i powiadomień telemetrycznych:
* **Global Error Catching:** węzeł `Error Trigger` przechwytuje zdarzenia awarii z dowolnego aktywnego potoku danych w organizacji.
* **Sanityzacja & Formatowanie (JavaScript):** węzeł `Code` parsuje błąd (nazwa węzła, timestamp w strefie `Europe/Warsaw`, identyfikator egzekucji, skrócony stack trace oraz bezpośredni odnośnik do panelu n8n).
* **Natychmiastowe alertowanie:** przesyłanie ustrukturyzowanej wiadomości na kanał techniczny administratora (Telegram / Webhook) z automatycznym zapobieganiem pętli błędów.

![Wizualizacja Pipeline n8n](assets/n8n_workflow_showcase.png)

#### Import do instancji n8n:
1. Przejdź do panelu n8n i wybierz **Workflows** ➔ **Import from File**.
2. Wybierz plik `n8n_error_alerting_workflow.json`.
3. Ustaw zmienne środowiskowe dla bota Telegram (`CHAT_ID`, `BOT_TOKEN`).

---

### 3. ERP (Subiekt GT), Wsparcie Operacyjne & Baza Wiedzy SOP
* **Administracja ERP:** Nadzór nad bazą ponad **1 500 kartotek asortymentowych i kontrahentów** w systemie Subiekt GT (MSSQL), weryfikacja poprawności fakturowania, synchronizacja stanów magazynowych (WZ/PZ).
* **Standaryzacja procesów (SOP):** Wdrożenie cyfrowej bazy wiedzy i procedur wykonawczych w Notion (diagnostyka i ponad 80 rozpatrzonych reklamacji sprzętu ze wskaźnikiem terminowości >95%, procedury eskalacji incydentów do centralnego IT).

![Baza Wiedzy SOP i Procedury ERP](assets/erp_subiekt_sop_showcase.png)

---

## 🛠 Stack technologiczny
* **Języki i narzędzia:** Python 3, Bash, JavaScript (Code Nodes w n8n), SQL, Git
* **Integracje:** n8n, REST API, Webhooks (asynchroniczne potwierdzenia ACK 202)
* **Infrastruktura & Chmura:** Linux Mint / Ubuntu, Oracle Cloud Infrastructure (OCI), VirtualBox
* **Systemy operacyjne & ERP:** Subiekt GT (utrzymanie baz danych, procedury SOP w Notion)

---

## 👤 Autor
**Robert Kazienko**  
* Inżynier | Automatyzacja Procesów | IT Support & Wdrożenia
* 📍 Przemyśl, Polska
* ✉ [mr.robkaz@gmail.com](mailto:mr.robkaz@gmail.com)
* 💼 [LinkedIn](https://linkedin.com/in/robert-kazienko)
* 🐙 [GitHub](https://github.com/robsonovski)
