#!/usr/bin/env python3
"""Compile the production Bluetooth OPP URI predicate in a Java host harness.

Tests preserve the original logic and exercise a URI with null authority.
Does not compile or run Android Bluetooth framework/application code.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "android/app/src/com/android/bluetooth/opp/BluetoothOppUtility.java"
START = "    public static boolean isBluetoothShareUri(Uri uri) {"
END = "\n    public static BluetoothOppTransferInfo queryRecord("

PREFIX = r"""
import java.util.Objects;

class Uri {
    private final String text;
    private final String authority;
    Uri(String text, String authority) {
        this.text = text;
        this.authority = authority;
    }
    @Override public String toString() { return text; }
    public String getAuthority() { return authority; }
}

class BluetoothShare {
    public static final Uri CONTENT_URI = new Uri("content://bt.opp", "bt.opp");
}

class EventLog {
    static int count = 0;
    static void writeEvent(int tag, String issue, int uid, String text) {
        count++;
    }
}

class BluetoothOppUtility {
"""
SUFFIX = r"""
}

public class Main {
    public static void main(String[] args) {
        Uri valid = new Uri("content://bt.opp/5", "bt.opp");
        if (!BluetoothOppUtility.isBluetoothShareUri(valid) || EventLog.count != 0) {
            throw new AssertionError("Valid share URI rejected");
        }

        Uri mismatched = new Uri("content://bt.opp/5", "another.provider");
        if (BluetoothOppUtility.isBluetoothShareUri(mismatched) || EventLog.count != 1) {
            throw new AssertionError("Malformed share URI not logged and rejected");
        }

        Uri missingAuthority = new Uri("content://bt.opp/5", null);
        if (BluetoothOppUtility.isBluetoothShareUri(missingAuthority) || EventLog.count != 2) {
            throw new AssertionError("Missing authority must be rejected, without NPE");
        }

        Uri unrelated = new Uri("https://host/unknown", null);
        if (BluetoothOppUtility.isBluetoothShareUri(unrelated) || EventLog.count != 2) {
            throw new AssertionError("Unrelated URI should be rejected without logging");
        }
        System.out.println("PASS: source-extracted Bluetooth OPP authority checks");
    }
}
"""


class BluetoothOppUriTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = FILE.read_text()
        if text.count(START) != 1:
            raise AssertionError("Expected exactly one BluetoothOppUtility predicate")
        start = text.index(START)
        stop = text.index(END, start)
        cls.production = text[start:stop]

    def test_uses_null_safe_authority_comparison(self):
        self.assertIn(
            "!Objects.equals(uri.getAuthority(), BluetoothShare.CONTENT_URI.getAuthority())",
            self.production,
        )
        self.assertNotIn("!uri.getAuthority().equals(", self.production)

    def test_actual_predicate_compiles_and_handles_missing_authority(self):
        javac = shutil.which("javac")
        java = shutil.which("java")
        self.assertIsNotNone(javac, "A JDK is required")
        self.assertIsNotNone(java, "A Java runtime is required")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Main.java"
            source.write_text(PREFIX + self.production + SUFFIX)
            subprocess.run(
                [javac, "-d", tmp, str(source)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            run = subprocess.run(
                [java, "-cp", tmp, "Main"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("PASS:", run.stdout)


if __name__ == "__main__":
    unittest.main()
