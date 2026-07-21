import unittest

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("app_module", Path(__file__).resolve().parents[1] / "app.py")
app_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app_module)


class AppHelpersTests(unittest.TestCase):
    def test_parse_csv_to_rows_from_text(self):
        csv_text = "nombre,fecha_nacimiento,celular,es_nuevo\nAna Pérez,2008-01-10,3001112222,1\nLuis Gómez,2007-03-22,3013334444,0\n"
        rows = app_module.parse_csv_to_rows_from_text(csv_text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["nombre"], "Ana Pérez")
        self.assertEqual(rows[0]["es_nuevo"], 1)

    def test_build_urgency_summary_orders_by_priority(self):
        df_jovenes = app_module.pd.DataFrame(
            [
                {"id": 1, "nombre": "Ana", "activo": 1, "es_nuevo": 1},
                {"id": 2, "nombre": "Luis", "activo": 1, "es_nuevo": 0},
            ]
        )
        df_asistencia = app_module.pd.DataFrame(
            [
                {"joven_id": 1, "fecha": "2026-07-11", "asistio": 0},
                {"joven_id": 1, "fecha": "2026-07-04", "asistio": 0},
                {"joven_id": 1, "fecha": "2026-06-27", "asistio": 0},
                {"joven_id": 2, "fecha": "2026-07-11", "asistio": 0},
                {"joven_id": 2, "fecha": "2026-07-04", "asistio": 1},
            ]
        )
        summary = app_module.build_urgency_summary(df_jovenes, df_asistencia)
        self.assertEqual(summary[0]["nombre"], "Ana")
        self.assertEqual(summary[0]["urgencia"], 3)
        self.assertEqual(summary[1]["nombre"], "Luis")
        self.assertEqual(summary[1]["urgencia"], 1)


if __name__ == "__main__":
    unittest.main()
