import os
from pathlib import Path
import unittest
from app import (
    AirQualityClient,
    CityNotFoundError,
    AuthenticationError,
    get_aqi_info,
    parse_local_env,
    resolve_api_key,
)

class TestAirQualityApp(unittest.TestCase):
    def test_parse_local_env_empty(self):
        result = parse_local_env(Path("non_existent_file.env"))
        self.assertEqual(result, {})

    def test_get_aqi_info(self):
        label_none, _, _ = get_aqi_info(None)
        self.assertEqual(label_none, "-")

        label_baik, bg_baik, _ = get_aqi_info(40)
        self.assertEqual(label_baik, "Baik")
        self.assertEqual(bg_baik, "#10b981")

        label_sedang, _, _ = get_aqi_info(80)
        self.assertEqual(label_sedang, "Sedang")

        label_sensitif, _, _ = get_aqi_info(120)
        self.assertEqual(label_sensitif, "Tidak Sehat (Sensitif)")

        label_tdk_sehat, _, _ = get_aqi_info(180)
        self.assertEqual(label_tdk_sehat, "Tidak Sehat")

        label_sgt_tdk_sehat, _, _ = get_aqi_info(250)
        self.assertEqual(label_sgt_tdk_sehat, "Sangat Tidak Sehat")

        label_bahaya, _, _ = get_aqi_info(450)
        self.assertEqual(label_bahaya, "Berbahaya")

    def test_resolve_api_key(self):
        key = resolve_api_key()
        self.assertTrue(len(key) > 10)

    def test_client_fetch_empty_city(self):
        client = AirQualityClient()
        with self.assertRaises(ValueError):
            client.fetch("   ")

    def test_client_fetch_valid_city(self):
        client = AirQualityClient()
        report = client.fetch("Jakarta")
        self.assertEqual(report.city, "Jakarta")
        self.assertIsInstance(report.overall_aqi, (int, type(None)))
        self.assertEqual(len(report.pollutants), 6)
        codes = [p.code for p in report.pollutants]
        self.assertIn("PM2.5", codes)
        self.assertIn("CO", codes)

    def test_client_fetch_invalid_city(self):
        client = AirQualityClient()
        with self.assertRaises(CityNotFoundError):
            client.fetch("kota_yang_sangat_fiktif_123456")

    def test_client_fetch_invalid_key(self):
        client = AirQualityClient(api_key="KUNCI_PALSU_12345")
        with self.assertRaises(AuthenticationError):
            client.fetch("Jakarta")

    def test_client_fetch_unconfigured_key(self):
        client = AirQualityClient(api_key="")
        with self.assertRaises(AuthenticationError) as ctx:
            client.fetch("Jakarta")
        self.assertIn("https://api-ninjas.com/", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
