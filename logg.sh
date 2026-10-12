#!/bin/zsh
# Visar loggen live. Avsluta visningen med Ctrl+C (bevakaren fortsätter köra).
cd "$(dirname "$0")"
tail -n 40 -f bevakare.log
