"""Run the Duel Masters Advisor web application."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "duel_masters"))

from duel_masters.app import app

if __name__ == "__main__":
    print("=" * 50)
    print(" Duel Masters Advisor")
    print("=" * 50)
    print("Buka browser di: http://localhost:5000")
    print("Tekan Ctrl+C untuk berhenti")
    print("=" * 50)
    app.run(debug=True, port=5000)
