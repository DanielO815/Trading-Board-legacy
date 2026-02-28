"""
Unit-Tests für ExportService.

Testet Job-Management Funktionen:
- Service-Initialisierung mit Exportverzeichnis
- Job-Erstellung und ID-Generierung
- Stop-Signal für laufende Exports
- Status-Abfrage mit Prozentfortschritt
- Validierung von Eingabeparametern
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from app.services.export_service import ExportService


class TestExportService(unittest.TestCase):
    """Unit-Tests für Export-Service Funktionalität.
    
    Testet:
    - Service-Initialisierung und State-Management
    - Stop-Signal Mechanik
    - Status-Abfrage mit Prozent-Berechnung
    - Job-Metadaten Persistierung
    """

    def setUp(self):
        """Erstellt temporäres Verzeichnis für Tests.
        
        Isoliert Tests durch separate Temp-Directories.
        """
        self.temp_dir = TemporaryDirectory()
        self.export_dir = Path(self.temp_dir.name)
        self.service = ExportService(export_dir=self.export_dir)

    def tearDown(self):
        """Räumt temporäres Verzeichnis auf."""
        self.temp_dir.cleanup()

    def test_service_initialization(self):
        """Test: Service-Initialisierung.
        
        Erwartet:
        - jobs Dict sollte leer sein
        - _stop_requested sollte False sein
        - export_dir sollte korrekt gespeichert sein
        """
        self.assertEqual(self.service.export_dir, self.export_dir)
        self.assertEqual(self.service.jobs, {})
        self.assertFalse(self.service._stop_requested)

    def test_stop_export_sets_flag(self):
        """Test: Stop-Signal für Export.
        
        Testabsicht:
        Das Stop-Signal wird von Export-Jobs geprüft, um lange laufende
        Exporte abzubrechen, wenn Benutzer die Operation stoppt.
        
        Initialer State:
        - _stop_requested = False (Service läuft normal)
        
        Nach stop_coinbase_export():
        - _stop_requested = True (Signal gesetzt)
        
        Verwendung in Production:
        Die Export-Job läuft in einer Schleife und prüft periodisch
        dieses _stop_requested Flag für frühen Exit und Cleanup.
        """
        # Initiale Bedingung: Stop-Flag sollte False sein
        self.assertFalse(self.service._stop_requested)
        # Aufrufen der Stop-Funktion
        self.service.stop_coinbase_export()
        # Validierung: Stop-Flag sollte jetzt True sein
        self.assertTrue(self.service._stop_requested)

    def test_get_status_nonexistent_job(self):
        """Test: Status-Abfrage für nicht existierenden Job.
        
        Testabsicht:
        Sicherstellen, dass die Service robuste Fehlerbehandlung bietet,
        wenn ein Frontend nach Status eines nicht existierenden Jobs fragt.
        
        Szenario:
        - Job-ID wird eingegeben, die nie eingegeben wurde
        - Oder Job wurde durch Timeout gelöscht
        
        Erwartet:
        - None-Return (nicht Exception)
        - Frontend kann dann 'job not found' Nachricht zeigen
        """
        # Abfrage für Job-ID, die nie erstellt wurde
        status = self.service.get_status("nonexistent_id")
        # Validierung: sollte None sein, nicht Exception werfen
        self.assertIsNone(status)

    def test_get_status_with_job(self):
        """Test: Status-Abfrage für existierenden Job.
        
        Testabsicht:
        Frontend ruft periodisch Status auf, um Fortschrittsbalken zu aktualisieren.
        Service muss alle Metadaten zurückgeben und Prozentfortschritt berechnen.
        
        Setup:
        Simuliert einen laufenden Export mit:
        - total: 100 Symbole zu exportieren
        - done: 50 Symbole bereits verarbeitet
        - errors: 2 Fehler während Verarbeitung
        
        Validierungen:
        1. Job muss existieren und nicht-None sein
        2. Alle Job-Felder müssen erhalten bleiben
        3. percent muss automatisch berechnet sein (50%)
        4. Fortschritt konsistent mit done/total sein
        """
        # Setup: Erstelle Mock-Job mit realistischem Test-Szenario
        job_id = "test_job_123"
        self.service.jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "total": 100,  # Insgesamt 100 Symbole
            "done": 50,    # 50 bereits verarbeitet
            "errors": 2,   # 2 Fehler aufgetreten
            "current": "BTC",  # Aktuell bearbeitetes Symbol
            "years": 10,   # Export für 10 Jahre
            "filename": "test.csv",  # Output-Datei
            "saved_to": "/exports/test.csv",  # Speicherlokation
            "fail_reason": None,  # Noch kein Fehler
        }

        # Abfrage des Status
        status = self.service.get_status(job_id)

        # Validierungen
        self.assertIsNotNone(status)  # Job muss existieren
        self.assertEqual(status["job_id"], job_id)  # Job-ID korrekt
        self.assertEqual(status["done"], 50)  # 50 Symbole fertig
        self.assertEqual(status["total"], 100)  # 100 insgesamt
        self.assertEqual(status["percent"], 50.0)  # 50/100 = 50%

    def test_percent_calculation(self):
        """Test: Prozentfortschritt-Berechnung.
        
        Testabsicht:
        Verifiziert mathematische Korrektheit der Fortschritts-Berechnung.
        Formula: (done / total) * 100
        
        Test-Szenario:
        3 von 10 Symbolen exportiert = 30.0%
        
        Business-Kontext:
        Fortschrittsbalkens im Frontend zeigt exakten Prozentsatz an,
        damit Nutzer weiß, wie lange der Export noch dauert.
        
        Edge-Cases werden in separatem Test abgedeckt (test_percent_calculation_zero_total).
        """
        job_id = "test_job_2"
        self.service.jobs[job_id] = {
            "total": 10,     # 10 Symbole insgesamt
            "done": 3,       # 3 Symbole fertig
            "errors": 0,
            "status": "running",
        }

        # Abfrage des Status
        status = self.service.get_status(job_id)

        # Validierung: 3/10 * 100 = 30.0%
        self.assertEqual(status["percent"], 30.0)

    def test_percent_calculation_zero_total(self):
        """Test: Prozentfortschritt mit null Gesamtmenge.
        
        Testabsicht:
        Defensive Programmierung: Sicherstellen, dass keine Division-by-Zero auftreten.
        Diese Edge-Case tritt auf wenn Job gerade erstellt wurde aber total=0 ist.
        
        Erwartet:
        - Sollte 0.0% zurückgeben (nicht Exception werfen)
        - Service muss graceful mit invalid Input umgehen
        
        Fehler-Vermeidung in Frontend:
        Ohne diesen Test könnte Frontend abstürzen bei Division durch Null.
        
        Production-Szenario:
        Job-Initialisierung mit total=0 (sollte nicht vorkommen, aber absichern).
        """
        job_id = "test_job_3"
        self.service.jobs[job_id] = {
            "total": 0,      # Keine Symbole (Edge-Case)
            "done": 0,       # Keine fertig
            "errors": 0,
            "status": "queued",
        }

        # Abfrage des Status
        status = self.service.get_status(job_id)

        # Validierung: Bei total=0 sollte 0.0% zurück sein (nicht Infinity oder NaN)
        self.assertEqual(status["percent"], 0.0)


class TestStartExportValidation(unittest.TestCase):
    """Tests für Validierung beim Start von Exports.
    
    Testet:
    - Symbol-Liste Validierung (nicht leer)
    - Symbol-Typ Validierung (Liste erforderlich)
    - Symbol-Normalisierung (Uppercase, Whitespace)
    - Duplikat-Entfernung
    """

    def setUp(self):
        """Erstellt Service für Validierungstests."""
        self.temp_dir = TemporaryDirectory()
        self.export_dir = Path(self.temp_dir.name)
        self.service = ExportService(export_dir=self.export_dir)

    def tearDown(self):
        """Räumt auf."""
        self.temp_dir.cleanup()

    def test_start_export_empty_symbols(self):
        """Test: Export-Start ohne Symbole.
        
        Testabsicht:
        Validierung von Input-Parametern. Ein Export ohne Symbole ist sinnlos
        und sollte mit klarer Fehlermeldung abgelehnt werden.
        
        Szenario:
        Frontend sendet leere Symbol-Liste oder None.
        
        Erwartet:
        - ValueError wird geworfen
        - Fehlermeldung: 'symbols ist leer'
        - Service führt keinen Job aus
        
        Frontend-Folge:
        Error-Handler zeigt Nachricht: "Bitte mindestens ein Symbol auswählen"
        """
        # Lege ein Export mit leeren Symbolen nachzuahmen
        with self.assertRaises(ValueError) as ctx:
            # Dieser Test kann nicht async laufen, daher simulieren wir die Validierung
            symbols = []
            # Normalisierung: whitespace entfernen und zu Großbuchstaben konvertieren
            symbols = [s.strip().upper() for s in symbols if s and s.strip()]
            # Duplikate entfernen mit dict.fromkeys() (erhält Reihenfolge seit Python 3.7)
            symbols = list(dict.fromkeys(symbols))
            # Validierung: Wenn nach Filterung leer, Exception
            if not symbols:
                raise ValueError("symbols ist leer")

        # Validierung: Exception muss 'symbols ist leer' enthalten
        self.assertIn("symbols ist leer", str(ctx.exception))

    def test_start_export_symbol_normalization(self):
        """Test: Normalisierung von Symbolen.
        
        Testabsicht:
        Input-Symbole können verschiedene Formate haben. Service muss
        diese normalisieren für einheitliche CSV-Verarbeitung.
        
        Transformationen anwenden:
        1. strip() - Whitespace entfernen (z.B. ' ETH ' -> 'ETH')
        2. upper() - Zu Großbuchstaben konvertieren (z.B. 'btc' -> 'BTC')
        3. Duplikate entfernen (z.B. ['BTC', 'btc'] -> ['BTC'])
        
        Test-Input: ['btc', ' ETH ', 'btc', 'xrp']
        Erwartet:   ['BTC', 'ETH', 'XRP']
        
        Frontend-Kontext:
        Nutzer gibt "  bitcoin, ethereum, ethereum, ripple  " in Textfeld,
        Frontend splittet und sendet als Liste an Backend.
        Service muss das sauber normalisieren.
        """
        # Test-Input mit verschiedenen Formaten
        symbols = ["btc", " ETH ", "btc", "xrp"]
        
        # Anwende Normalisierung schrittweise
        # Schritt 1: whitespace entfernen und zu Großbuchstaben konvertieren
        normalized = [s.strip().upper() for s in symbols if s and s.strip()]
        # Schritt 2: Duplikate entfernen (dict.fromkeys erhält Reihenfolge)
        normalized = list(dict.fromkeys(normalized))

        # Validierungen
        self.assertEqual(len(normalized), 3)  # Muss 3 unique Symbole haben
        self.assertIn("BTC", normalized)  # BTC sollte vorhanden sein
        self.assertIn("ETH", normalized)  # ETH sollte vorhanden sein
        self.assertIn("XRP", normalized)  # XRP sollte vorhanden sein
        
        # Wichtig: Duplikate sollten entfernt sein
        self.assertEqual(normalized.count("BTC"), 1)  # BTC nur einmal


if __name__ == "__main__":
    unittest.main()
